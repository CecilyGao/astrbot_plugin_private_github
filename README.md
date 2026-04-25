# 🔐 AstrBot 私有 GitHub 动态监听插件

**只要你的GitHub Personal Access Token有权限就能视奸别人的private仓库，赶快看看好闺蜜在搞什么名堂😈**

通过 GitHub REST API 和 GraphQL API 定时获取私有仓库及组织项目（Projects v2）的动态，自动推送到绑定的聊天会话。支持 Personal Access Token 认证，可用于私有仓库、内部项目看板的实时监控。

## ✨ 功能特性

- 📦 **私有仓库监听** — 支持 `Issues`、`Commits`、`Releases` 事件
- 📌 **组织项目监听 (Projects v2)** — 自动检测项目中新增/更新的卡片（Issue / PR / Draft Issue）
- 🔐 **Token 认证** — 使用 GitHub Personal Access Token 访问私有资源
- ⏱️ **定时轮询** — 可自定义轮询间隔（默认 30 分钟，最低 60 秒）
- 🌐 **多会话推送** — 支持绑定多个聊天会话
- 🕐 **时区转换** — 自动将 GitHub 时间转为本地时区
- 🔒 **权限控制** — 关键指令仅管理员可用
- 🚀 **并发拉取推送** — 多目标并行处理，高效不阻塞
- 🛡️ **输入校验** — 仓库名/项目编号合法性检查，无效项自动跳过
- 🔐 **并发安全** — 配置写入加锁，避免竞态条件

## 📋 可用指令

| 指令 | 权限 | 说明 |
|------|------|------|
| `ghp_list` | 所有人 | 列出所有监听项和绑定会话数 |
| `ghp_check repo <owner/repo> <issues\|commits\|releases>` | 管理员 | 立即查看某仓库的最新动态 |
| `ghp_check project <org/number>` | 管理员 | 立即查看某组织项目的最新卡片 |
| `ghp_bindhere` | 管理员 | 将当前会话绑定为推送目标 |
| `ghp_unbindhere` | 管理员 | 解绑当前会话 |

## ⚙️ 配置项

在 AstrBot WebUI 插件配置页面可设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `github_token` | string | 空 | GitHub Personal Access Token，需具有 `repo`、`read:org`、`project` 权限 |
| `poll_interval` | int | 1800 | 轮询间隔（秒），建议不低于 600 秒 |
| `max_entries` | int | 5 | 每次推送的最大条目数，设为 0 不限制 |
| `watch_repos` | list | [] | 监听的仓库及事件类型，格式 `owner/repo:type`，type 可选 `issues`、`commits`、`releases` |
| `watch_org_projects` | list | [] | 监听的 GitHub 组织项目，格式 `org/number`，项目编号在 URL 中查看 |
| `timezone` | string | Asia/Shanghai | 时间显示时区 |
| `bound_sessions` | list | [] | 推送目标会话（也可用 `/ghp_bindhere` 绑定） |

### 配置示例

```json
{
    "github_token": "ghp_your_token_here",
    "poll_interval": 900,
    "max_entries": 5,
    "watch_repos": [
        "nju-mc-org/server_document:issues",
        "my-org/private-repo:commits"
    ],
    "watch_org_projects": [
        "nju-mc-org/4"
    ],
    "timezone": "Asia/Shanghai",
    "bound_sessions": []
}