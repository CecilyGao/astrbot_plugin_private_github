import asyncio
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import aiohttp
import json

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event import MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# GitHub API
REST_API_BASE = "https://api.github.com"
GRAPHQL_API = "https://api.github.com/graphql"

# 游标存储前缀
KV_LAST_CURSOR_PREFIX = "ghp_cursor_"
KV_INITIALIZED_PREFIX = "ghp_initialized_"

# 扫描窗口硬上限
MAX_SCAN_ENTRIES = 50

# 仓库名校验
RE_REPO = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")
# 监听项格式: owner/repo:type
RE_WATCH_ITEM = re.compile(r"^([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+):(issues|commits|releases)$")
# 组织项目监听项格式: org/project_number
RE_PROJECT_ITEM = re.compile(r"^([a-zA-Z0-9._-]+)/(\d+)$")


@register(
    "astrbot_plugin_private_github",
    "CecilyGao",
    "通过 GitHub API 定时获取私有仓库动态（Issues/Commits/Releases/Projects）并推送到聊天会话",
    "1.0.0",
    "https://github.com/CecilyGao/astrbot_plugin_private_github",
)
class GitHubPrivateListenPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.github_token: str = config.get("github_token", "")
        if not self.github_token:
            logger.warning("[Private GitHub] 未配置 github_token，插件将无法访问私有数据")

        self.poll_interval: int = max(config.get("poll_interval", 1800), 60)
        self.max_entries: int = max(config.get("max_entries", 5), 0)
        self.cfg_bound_sessions: List[str] = config.get("bound_sessions", [])
        self.cfg_timezone: str = config.get("timezone", "Asia/Shanghai")

        # 解析仓库监听项: List[(repo_full, event_type)]
        self.watch_repos: List[Tuple[str, str]] = self._parse_watch_repos(config.get("watch_repos", []))
        # 解析组织项目监听项: List[(org, project_number)]
        self.watch_projects: List[Tuple[str, int]] = self._parse_watch_projects(config.get("watch_org_projects", []))

        self._poll_task: Optional[asyncio.Task] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._initialized_keys: set = set()
        self._config_lock = asyncio.Lock()

    # ==================== 配置解析 ====================

    def _parse_watch_repos(self, raw_items: List[str]) -> List[Tuple[str, str]]:
        """解析仓库监听项"""
        result = []
        seen = set()
        for item in raw_items:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item:
                continue
            match = RE_WATCH_ITEM.match(item)
            if not match:
                logger.warning(f"[Private GitHub] 跳过非法仓库监听项: {item}")
                continue
            repo = match.group(1)
            event_type = match.group(2)
            key = f"{repo}:{event_type}"
            if key in seen:
                continue
            seen.add(key)
            result.append((repo, event_type))
        return result

    def _parse_watch_projects(self, raw_items: List[str]) -> List[Tuple[str, int]]:
        """解析组织项目监听项"""
        result = []
        seen = set()
        for item in raw_items:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item:
                continue
            match = RE_PROJECT_ITEM.match(item)
            if not match:
                logger.warning(f"[Private GitHub] 跳过非法项目监听项: {item}，应为 org/number")
                continue
            org = match.group(1)
            number = int(match.group(2))
            key = f"{org}/{number}"
            if key in seen:
                continue
            seen.add(key)
            result.append((org, number))
        return result

    # ==================== 初始化 & 生命周期 ====================

    async def initialize(self):
        if not self.github_token:
            logger.error("[Private GitHub] github_token 未配置，插件将无法正常工作")
        logger.info(
            f"[Private GitHub] 插件初始化，轮询间隔: {self.poll_interval} 秒，"
            f"仓库监听项: {self.watch_repos}，项目监听项: {self.watch_projects}，"
            f"绑定会话数: {len(self.cfg_bound_sessions)}"
        )
        self._http_session = aiohttp.ClientSession(
            headers={
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        await self._init_cursors()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _init_cursors(self):
        """初始化所有监听项的游标"""
        # 仓库监听项
        for repo, event_type in self.watch_repos:
            kv_key = self._get_repo_kv_key(repo, event_type)
            await self._init_cursor(kv_key, repo, event_type)
        # 项目监听项
        for org, number in self.watch_projects:
            kv_key = self._get_project_kv_key(org, number)
            await self._init_cursor(kv_key, f"{org}/{number}", "project")

    async def _init_cursor(self, kv_key: str, identifier: str, item_type: str):
        if kv_key in self._initialized_keys:
            return
        init_flag = f"{KV_INITIALIZED_PREFIX}{kv_key}"
        if await self.get_kv_data(init_flag, ""):
            self._initialized_keys.add(kv_key)
            return

        # 尝试获取最新一条动态
        if item_type == "project":
            latest = await self._fetch_latest_project_item(identifier.split("/")[0], int(identifier.split("/")[1]))
        else:
            # 仓库监听: identifier 是 repo, item_type 是 event_type
            latest = await self._fetch_latest_repo_entry(identifier, item_type)

        if latest:
            cursor = self._extract_cursor_from_entry(latest, item_type)
            if cursor:
                await self.put_kv_data(f"{KV_LAST_CURSOR_PREFIX}{kv_key}", cursor)
                await self.put_kv_data(init_flag, "1")
                self._initialized_keys.add(kv_key)
                logger.info(f"[Private GitHub] 已初始化游标: {kv_key} -> {cursor[:20]}...")
        else:
            logger.warning(f"[Private GitHub] 初始化游标失败，将在下次重试: {identifier} ({item_type})")

    async def terminate(self):
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        logger.info("[Private GitHub] 插件已卸载")

    # ==================== 辅助函数 ====================

    @staticmethod
    def _get_repo_kv_key(repo: str, event_type: str) -> str:
        return f"{repo.replace('/', '_')}_{event_type}"

    @staticmethod
    def _get_project_kv_key(org: str, number: int) -> str:
        return f"project_{org}_{number}"

    @staticmethod
    def _extract_cursor_from_entry(entry: Dict[str, Any], item_type: str) -> str:
        if item_type == "issue" or item_type == "issues":
            return str(entry.get("id", ""))
        elif item_type == "commit" or item_type == "commits":
            return entry.get("sha", "")
        elif item_type == "release" or item_type == "releases":
            return str(entry.get("id", ""))
        elif item_type == "project":
            # 对于项目，使用 item 的 id 作为游标
            return entry.get("id", "")
        return ""

    def _convert_time(self, time_str: str) -> str:
        if not time_str:
            return ""
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo(self.cfg_timezone)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return time_str

    @staticmethod
    def _extract_content(entry: Dict[str, Any], event_type: str, max_len: int = 200) -> str:
        if event_type == "issue":
            body = entry.get("body", "") or ""
            title = entry.get("title", "")
            return f"{title}: {body[:max_len]}".strip()
        elif event_type == "commit":
            commit = entry.get("commit", {})
            message = commit.get("message", "")
            return message.split("\n")[0][:max_len]
        elif event_type == "release":
            name = entry.get("name", "") or entry.get("tag_name", "")
            body = entry.get("body", "") or ""
            return f"{name}: {body[:max_len]}".strip()
        elif event_type == "project":
            # 项目项暂不提取详细内容，避免 GraphQL 复杂结构
            return ""
        return ""

    # ==================== GitHub API 请求 ====================

    async def _rest_api_get(self, url: str) -> Optional[List[Dict]]:
        """REST API GET 请求"""
        if not self._http_session or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                headers={"Authorization": f"token {self.github_token}"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        try:
            async with self._http_session.get(url) as resp:
                if resp.status == 404:
                    logger.warning(f"[Private GitHub] API 404: {url}")
                    return None
                if resp.status != 200:
                    logger.warning(f"[Private GitHub] API 请求失败: {url} -> HTTP {resp.status}")
                    return None
                data = await resp.json()
                if isinstance(data, list):
                    return data
                else:
                    return [data]
        except Exception as e:
            logger.error(f"[Private GitHub] API 请求异常: {url} -> {e}")
            return None

    async def _graphql_request(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """GraphQL 请求"""
        if not self._http_session or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                headers={"Authorization": f"token {self.github_token}"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            async with self._http_session.post(GRAPHQL_API, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"[Private GitHub] GraphQL 请求失败: HTTP {resp.status}")
                    return None
                data = await resp.json()
                if "errors" in data:
                    logger.warning(f"[Private GitHub] GraphQL 错误: {data['errors']}")
                    return None
                return data.get("data")
        except Exception as e:
            logger.error(f"[Private GitHub] GraphQL 请求异常: {e}")
            return None

    # ==================== 仓库监听 (REST) ====================

    async def _fetch_latest_repo_entry(self, repo: str, event_type: str) -> Optional[Dict]:
        url = self._build_repo_api_url(repo, event_type, per_page=1)
        data = await self._rest_api_get(url)
        if data and len(data) > 0:
            return data[0]
        return None

    async def _fetch_new_repo_entries(self, repo: str, event_type: str) -> List[Dict]:
        kv_key = self._get_repo_kv_key(repo, event_type)
        full_cursor_key = f"{KV_LAST_CURSOR_PREFIX}{kv_key}"
        last_cursor = await self.get_kv_data(full_cursor_key, "")

        per_page = MAX_SCAN_ENTRIES
        url = self._build_repo_api_url(repo, event_type, per_page=per_page)
        items = await self._rest_api_get(url)
        if not items:
            return []

        new_entries = []
        for item in items:
            cursor = self._extract_cursor_from_entry(item, event_type)
            if cursor == last_cursor:
                break
            entry = self._build_repo_entry_dict(item, event_type)
            if entry:
                new_entries.append(entry)

        if self.max_entries > 0 and len(new_entries) > self.max_entries:
            new_entries = new_entries[:self.max_entries]

        if new_entries and items:
            latest_cursor = self._extract_cursor_from_entry(items[0], event_type)
            await self.put_kv_data(full_cursor_key, latest_cursor)
        return new_entries

    def _build_repo_api_url(self, repo: str, event_type: str, per_page: int = 30) -> str:
        base = f"{REST_API_BASE}/repos/{repo}"
        if event_type == "issues":
            return f"{base}/issues?state=all&sort=created&direction=desc&per_page={per_page}"
        elif event_type == "commits":
            return f"{base}/commits?per_page={per_page}"
        elif event_type == "releases":
            return f"{base}/releases?per_page={per_page}"
        raise ValueError(f"Unknown event_type: {event_type}")

    def _build_repo_entry_dict(self, raw: Dict, event_type: str) -> Dict:
        if event_type == "issues":
            return {
                "title": f"[Issue] #{raw['number']}: {raw['title']}",
                "link": raw["html_url"],
                "published": self._convert_time(raw["created_at"]),
                "content": self._extract_content(raw, "issue"),
                "id": str(raw["id"]),
                "type": "issue"
            }
        elif event_type == "commits":
            return {
                "title": f"[Commit] {raw['sha'][:7]}: {raw['commit']['message'].splitlines()[0][:100]}",
                "link": raw["html_url"],
                "published": self._convert_time(raw["commit"]["committer"]["date"]),
                "content": self._extract_content(raw, "commit"),
                "id": raw["sha"],
                "type": "commit"
            }
        elif event_type == "releases":
            return {
                "title": f"[Release] {raw['tag_name']}: {raw['name'] or raw['tag_name']}",
                "link": raw["html_url"],
                "published": self._convert_time(raw["published_at"] or raw["created_at"]),
                "content": self._extract_content(raw, "release"),
                "id": str(raw["id"]),
                "type": "release"
            }
        return {}

    # ==================== 组织项目监听 (GraphQL) ====================

    async def _fetch_latest_project_item(self, org: str, number: int) -> Optional[Dict]:
        """获取项目中最新的一个 item（按 updatedAt 降序）"""
        items = await self._fetch_project_items(org, number, first=1)
        if items:
            return items[0]
        return None

    async def _fetch_project_items(self, org: str, number: int, first: int = 50) -> List[Dict]:
        """获取项目中的 items，手动按 updatedAt 降序排序（不使用 orderBy 以避免 schema 错误）"""
        query = """
        query($org: String!, $number: Int!, $first: Int!) {
          organization(login: $org) {
            projectV2(number: $number) {
              items(first: $first) {
                nodes {
                  id
                  createdAt
                  updatedAt
                  content {
                    __typename
                    ... on Issue {
                      title
                      url
                      number
                    }
                    ... on PullRequest {
                      title
                      url
                      number
                    }
                    ... on DraftIssue {
                      title
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"org": org, "number": number, "first": first}
        data = await self._graphql_request(query, variables)
        if not data:
            return []
        org_data = data.get("organization")
        if not org_data:
            return []
        project = org_data.get("projectV2")
        if not project:
            return []
        items = project.get("items", {}).get("nodes", [])
        # 手动按 updatedAt 降序排序，确保最新更新的在前
        items.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
        return items

    async def _fetch_new_project_entries(self, org: str, number: int) -> List[Dict]:
        kv_key = self._get_project_kv_key(org, number)
        full_cursor_key = f"{KV_LAST_CURSOR_PREFIX}{kv_key}"
        last_cursor = await self.get_kv_data(full_cursor_key, "")

        items = await self._fetch_project_items(org, number, first=MAX_SCAN_ENTRIES)
        if not items:
            return []

        new_entries = []
        for item in items:
            item_id = item.get("id", "")
            if item_id == last_cursor:
                break
            entry = self._build_project_entry_dict(item, org, number)
            if entry:
                new_entries.append(entry)

        if self.max_entries > 0 and len(new_entries) > self.max_entries:
            new_entries = new_entries[:self.max_entries]

        if new_entries and items:
            latest_id = items[0].get("id", "")
            if latest_id:
                await self.put_kv_data(full_cursor_key, latest_id)
        return new_entries

    def _build_project_entry_dict(self, item: Dict, org: str, number: int) -> Dict:
        """将 GraphQL 返回的项目 item 转为统一格式（不包含复杂字段）"""
        content = item.get("content")
        if not content:
            return {}

        typename = content.get("__typename")
        if typename == "Issue":
            title = content.get("title", "无标题")
            url = content.get("url", "")
            item_type = "Issue"
            number_str = f"#{content.get('number', '')}"
        elif typename == "PullRequest":
            title = content.get("title", "无标题")
            url = content.get("url", "")
            item_type = "PR"
            number_str = f"#{content.get('number', '')}"
        elif typename == "DraftIssue":
            title = content.get("title", "无标题")
            url = ""  # DraftIssue 没有 url 字段
            item_type = "Draft Issue"
            number_str = ""
        else:
            title = "未知卡片"
            url = ""
            item_type = "Card"
            number_str = ""

        display_title = f"[Project {org}/{number}] {item_type} {number_str}: {title}"
        return {
            "title": display_title,
            "link": url,
            "published": self._convert_time(item.get("updatedAt", item.get("createdAt", ""))),
            "content": "",  # 暂不提取字段值
            "id": item.get("id", ""),
            "type": "project_item"
        }

    # ==================== 定时轮询 ====================

    async def _poll_loop(self):
        await asyncio.sleep(10)
        while True:
            try:
                await self._init_cursors()
                await self._do_poll()
            except asyncio.CancelledError:
                logger.info("[Private GitHub] 轮询任务已取消")
                return
            except Exception as e:
                logger.error(f"[Private GitHub] 轮询出错: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _do_poll(self):
        if (not self.watch_repos and not self.watch_projects) or not self.cfg_bound_sessions or not self.github_token:
            return

        tasks = []
        # 仓库监听
        for repo, event_type in self.watch_repos:
            kv_key = self._get_repo_kv_key(repo, event_type)
            if kv_key in self._initialized_keys:
                tasks.append((f"repo:{repo}:{event_type}", self._fetch_new_repo_entries(repo, event_type)))
        # 项目监听
        for org, number in self.watch_projects:
            kv_key = self._get_project_kv_key(org, number)
            if kv_key in self._initialized_keys:
                tasks.append((f"project:{org}/{number}", self._fetch_new_project_entries(org, number)))

        if not tasks:
            return

        # 并发执行
        results = await asyncio.gather(
            *[task[1] for task in tasks],
            return_exceptions=True
        )

        send_tasks = []
        for (label, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"[Private GitHub] 获取 {label} 失败: {result}")
                continue
            if not result:
                continue

            # 格式化消息
            if label.startswith("repo:"):
                _, repo, etype = label.split(":")
                msg = self._format_repo_entries(repo, etype, result)
            else:
                _, proj = label.split(":")
                msg = self._format_project_entries(proj, result)

            chain = MessageChain().message(msg)
            for umo in self.cfg_bound_sessions:
                send_tasks.append(self._safe_send(umo, chain))

        if send_tasks:
            await asyncio.gather(*send_tasks)

    async def _safe_send(self, umo: str, chain: MessageChain):
        try:
            await self.context.send_message(umo, chain)
        except Exception as e:
            logger.error(f"[Private GitHub] 推送失败 ({umo}): {e}")

    # ==================== 消息格式化 ====================

    @staticmethod
    def _format_repo_entries(repo: str, event_type: str, entries: List[Dict]) -> str:
        type_icon = {
            "issues": "🐛",
            "commits": "📝",
            "releases": "📦"
        }.get(event_type, "🔔")
        lines = [f"{type_icon} 仓库 {repo} 的新{event_type}动态（{len(entries)} 条）：\n"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"  {i}. {entry['title']}")
            if entry["published"]:
                lines.append(f"     🕐 {entry['published']}")
            if entry["content"]:
                lines.append(f"     📝 {entry['content']}")
            if entry["link"]:
                lines.append(f"     🔗 {entry['link']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_project_entries(project_id: str, entries: List[Dict]) -> str:
        lines = [f"📌 组织项目 {project_id} 新增/更新了 {len(entries)} 个卡片：\n"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"  {i}. {entry['title']}")
            if entry["published"]:
                lines.append(f"     🕐 {entry['published']}")
            if entry["content"]:
                lines.append(f"     📝 {entry['content']}")
            if entry["link"]:
                lines.append(f"     🔗 {entry['link']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_single_check_repo(repo: str, event_type: str, entries: List[Dict]) -> str:
        if not entries:
            return f"🔍 仓库 {repo} 暂无最近的 {event_type} 动态。"
        type_icon = {"issues": "🐛", "commits": "📝", "releases": "📦"}.get(event_type, "🔔")
        lines = [f"{type_icon} 仓库 {repo} 最近的 {event_type} 动态：\n"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"  {i}. {entry['title']}")
            if entry["published"]:
                lines.append(f"     🕐 {entry['published']}")
            if entry["content"]:
                lines.append(f"     📝 {entry['content']}")
            if entry["link"]:
                lines.append(f"     🔗 {entry['link']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_single_check_project(project_id: str, entries: List[Dict]) -> str:
        if not entries:
            return f"🔍 项目 {project_id} 暂无最近的卡片动态。"
        lines = [f"📌 项目 {project_id} 最近的卡片：\n"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"  {i}. {entry['title']}")
            if entry["published"]:
                lines.append(f"     🕐 {entry['published']}")
            if entry["content"]:
                lines.append(f"     📝 {entry['content']}")
            if entry["link"]:
                lines.append(f"     🔗 {entry['link']}")
            lines.append("")
        return "\n".join(lines)

    # ==================== 指令处理 ====================

    @filter.command("ghp_list")
    async def ghp_list(self, event: AstrMessageEvent):
        """列出所有监听项及绑定会话"""
        lines = ["📋 Private GitHub 监听列表\n"]
        if self.watch_repos:
            lines.append("仓库监听:")
            for repo, etype in self.watch_repos:
                lines.append(f"  📦 {repo} : {etype}")
        if self.watch_projects:
            lines.append("项目监听:")
            for org, num in self.watch_projects:
                lines.append(f"  📌 {org}/{num}")
        if not self.watch_repos and not self.watch_projects:
            lines.append("  暂无监听项，请在 WebUI 配置中设置 watch_repos 或 watch_org_projects")
        lines.append(f"\n→ 推送到 {len(self.cfg_bound_sessions)} 个绑定会话")
        lines.append(f"⏱️ 轮询间隔：{self.poll_interval} 秒")
        yield event.plain_result("\n".join(lines))

    @filter.command("ghp_check")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ghp_check(self, event: AstrMessageEvent):
        """手动检查指定仓库或项目的最新动态
        用法：
          /ghp_check repo owner/repo issues
          /ghp_check repo owner/repo commits
          /ghp_check repo owner/repo releases
          /ghp_check project org/number
        """
        parts = event.message_str.strip().split()
        if len(parts) < 2:
            yield event.plain_result(
                "❌ 用法错误，示例：\n"
                "  /ghp_check repo nju-mc-org/server_document issues\n"
                "  /ghp_check project my-org/1"
            )
            return

        if parts[1] == "repo":
            if len(parts) < 4:
                yield event.plain_result("❌ 仓库用法: /ghp_check repo owner/repo issues|commits|releases")
                return
            repo = parts[2]
            event_type = parts[3].lower()
            if not RE_REPO.match(repo):
                yield event.plain_result("❌ 仓库格式不正确，应为 owner/repo")
                return
            if event_type not in ("issues", "commits", "releases"):
                yield event.plain_result("❌ 事件类型必须为 issues / commits / releases 之一")
                return

            yield event.plain_result(f"🔄 正在获取 {repo} 的 {event_type} 动态...")
            url = self._build_repo_api_url(repo, event_type, per_page=self.max_entries or 10)
            items = await self._rest_api_get(url)
            if items is None:
                yield event.plain_result("❌ 无法获取数据，请检查仓库名及 token 权限")
                return
            entries = []
            for item in items[:self.max_entries or 10]:
                entry = self._build_repo_entry_dict(item, event_type)
                if entry:
                    entries.append(entry)
            yield event.plain_result(self._format_single_check_repo(repo, event_type, entries))

        elif parts[1] == "project":
            if len(parts) < 3:
                yield event.plain_result("❌ 项目用法: /ghp_check project org/number")
                return
            proj_str = parts[2]
            match = RE_PROJECT_ITEM.match(proj_str)
            if not match:
                yield event.plain_result("❌ 项目格式不正确，应为 org/number，如 my-org/1")
                return
            org = match.group(1)
            number = int(match.group(2))

            yield event.plain_result(f"🔄 正在获取项目 {org}/{number} 的最新卡片...")
            items = await self._fetch_project_items(org, number, first=self.max_entries or 10)
            if not items:
                yield event.plain_result("❌ 无法获取项目数据，请检查组织名、项目编号及 token 权限")
                return
            entries = []
            for item in items[:self.max_entries or 10]:
                entry = self._build_project_entry_dict(item, org, number)
                if entry:
                    entries.append(entry)
            yield event.plain_result(self._format_single_check_project(f"{org}/{number}", entries))

        else:
            yield event.plain_result("❌ 第二个参数必须是 repo 或 project")

    @filter.command("ghp_pushnow")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ghp_pushnow(self, event: AstrMessageEvent):
        """立即执行一次全局推送（检查所有监听项，并向绑定会话发送新动态）"""
        if not self.github_token:
            yield event.plain_result("❌ 未配置 github_token，无法执行推送")
            return
        if not self.cfg_bound_sessions:
            yield event.plain_result("⚠️ 没有绑定的会话，请先使用 /ghp_bindhere 绑定")
            return

        yield event.plain_result("🔄 正在立即检查所有监听项并推送...")
        try:
            await self._init_cursors()
            await self._do_poll()
            yield event.plain_result("✅ 推送完成（如有新动态已发送）")
        except Exception as e:
            logger.error(f"[Private GitHub] 手动推送失败: {e}")
            yield event.plain_result(f"❌ 推送过程中发生错误: {e}")

    @filter.command("ghp_bindhere")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ghp_bindhere(self, event: AstrMessageEvent):
        """绑定当前会话为推送目标"""
        umo = event.unified_msg_origin
        async with self._config_lock:
            if umo in self.cfg_bound_sessions:
                yield event.plain_result("⚠️ 当前会话已在绑定列表中")
                return
            self.cfg_bound_sessions.append(umo)
            self.config["bound_sessions"] = self.cfg_bound_sessions
            self.config.save_config()
        yield event.plain_result(
            f"✅ 已绑定当前会话为推送目标\n会话标识：{umo}\n当前共 {len(self.cfg_bound_sessions)} 个绑定会话"
        )

    @filter.command("ghp_unbindhere")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ghp_unbindhere(self, event: AstrMessageEvent):
        """解绑当前会话"""
        umo = event.unified_msg_origin
        async with self._config_lock:
            if umo not in self.cfg_bound_sessions:
                yield event.plain_result("⚠️ 当前会话不在绑定列表中")
                return
            self.cfg_bound_sessions.remove(umo)
            self.config["bound_sessions"] = self.cfg_bound_sessions
            self.config.save_config()
        yield event.plain_result(f"✅ 已解绑当前会话\n剩余 {len(self.cfg_bound_sessions)} 个绑定会话")