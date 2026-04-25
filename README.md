# 🔐 GitHub 仓库动态监听插件

**只要你的GitHub Personal Access Token有权限就能视奸别人的仓库，赶快看看好闺蜜在搞什么名堂😈**

通过 GitHub REST API 和 GraphQL API 定时获取私有仓库及组织项目（Projects v2）的动态，自动推送到绑定的聊天会话。支持 Personal Access Token 认证，可用于**公开**仓库（Public Repository）、**私有**仓库（Private Repository）、项目动态（Projects）的实时监控。

## ✨ 功能特性

- 📦 **仓库监听** — 支持 `Issues`、`Commits`、`Releases` 事件
- 📌 **组织项目监听 (Projects v2)** — 自动检测项目中新增/更新的卡片（Issue / PR / Draft Issue）
- 🔐 **Token 认证** — 使用 GitHub Personal Access Token 访问私有资源
- ⏱️ **定时轮询** — 可自定义轮询间隔（默认 30 分钟，最低 60 秒）
- 🌐 **多会话推送** — 支持绑定多个聊天会话
- 🕐 **时区转换** — 自动将 GitHub 时间转为本地时区
- 🗂️ **多会话独立订阅** — 每个群聊/私聊可独立添加/取消订阅，互不干扰
- 🔒 **权限控制** — 可配置白名单，控制普通用户使用订阅指令

## 📋 可用指令

| 指令 | 权限 | 说明 |
|------|------|------|
| `ghp_check repo <owner/repo> <issues\|commits\|releases>` | 管理员 | 立即查看某仓库的最新动态 |
| `ghp_check project <org/number>` | 管理员 | 立即查看某组织项目的最新卡片 |
| `ghp_subscribe repo <owner/repo> <issues\|commits\|releases>` | 白名单成员或管理员 | 订阅仓库动态 |
| `ghp_subscribe project <org/number>` | 同上 | 订阅组织项目卡片 |
| `ghp_unsubscribe <序号>` | 同上 | 取消当前会话中指定序号的订阅 |
| `ghp_list_subs` | 同上 | 列出当前会话的所有订阅 |
| ~~`/ghp_list`~~ | 所有人 | 已废弃，请用 `/ghp_list_subs` |
| ~~`/ghp_bindhere`~~ | 管理员 | 已废弃，现在每个会话自动独立管理 |

### 指令示例

ghp_check repo AstrBotDevs/AstrBot issues —— 立刻推送 Astrbot 团队最新收到的小纸条

ghp_subscribe repo AstrBotDevs/AstrBot commits —— 监听并推送 Astrbot 团队提交的新修改

ghp_check project AstrBotDevs/1 —— 立刻推送 Astrbot 团队1号项目的最新动态

ghp_subscribe project AstrBotDevs/3 —— 监听并推送 Astrbot 团队3号项目的最新动态

## ⚙️ 配置项

在 AstrBot WebUI 插件配置页面可设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `github_token` | string | 空 | GitHub Personal Access Token，需具有 `repo`、`read:org`、`project` 权限 |
| `poll_interval` | int | 1800 | 轮询间隔（秒），建议不低于 600 秒 |
| `max_entries` | int | 5 | 每次推送的最大条目数，设为 0 不限制 |
| `timezone` | string | Asia/Shanghai | 时间显示时区 |
| `whitelist` | list | [] | 允许使用订阅指令的普通用户 ID 列表，留空则所有用户均可使用（不建议） |

### 配置示例

```json
{
    "github_token": "ghp_1145141919810",
    "poll_interval": 900,
    "max_entries": 5,
    "watch_repos": [
        "AstrBotDevs/AstrBot:issues",
        "AstrBotDevs/AstrBot:commits"
    ],
    "watch_org_projects": [
        "AstrBotDevs/1"
    ],
    "timezone": "Asia/Shanghai",
    "bound_sessions": []
}
```

## 📦 升级指南（从 v1.0.0 升级）

1. **备份原配置**（可选）
2. **更新本插件**
3. **重新添加订阅**：在每个需要推送的会话中重新使用 `ghp_subscribe` 添加订阅

> 旧版绑定的会话和监听项不会自动迁移，请手动重新订阅。

## 👥 贡献指南

-🌟 Star 这个项目！（点右上角的星星，感谢支持！）

-🐛 提交 Issue 报告问题

-💡 提出新功能建议

-🔧 提交 Pull Request 改进代码

## 🙏 致谢

- 😋 感谢 [astrbot_plugin_listen_github](https://github.com/aliveriver/astrbot_plugin_listen_github) 插件，为本项目提供了架构参考和灵感，建议搭配食用喵。

- 感谢 [reminder](https://github.com/Soulter/astrbot_plugin_reminder) 插件的设计思路与架构启发，为本插件的多会话订阅管理提供了重要参考。

## ⚠️ 注意事项

1. **Token 权限要求**：Personal Access Token 必须勾选 `repo`（完全控制私有仓库）、`read:org`（读取组织信息）和 `project`（访问项目）。如果组织启用了 SAML SSO，需要先授权该 Token。

公开仓库不受限制，主要是**私有仓库你要有权限访问**。可以在任何联网设备的命令行用 `curl -H` 验证token是否有权限，有效的话会返回访问记录。

例如，我使用

```bash
curl -H "Authorization: token ghp_1145141919810" "https://api.github.com/repos/xxxx/xxxxxx/issues"
```

返回了该仓库的 issues，则 ghp_1145141919810 是有访问 xxxxxx 仓库权限的，可以放心填在配置里。

2. **项目编号获取**：组织项目的编号请在浏览器地址栏查看，例如 `https://github.com/orgs/xxxx/projects/4` 中的 `4` 即为项目编号。配置时写入 `xxxx/4`。

3. **API 限流**：GitHub REST API 的 Token 限频为每小时 5000 次请求，GraphQL 节点数也有一定限制。插件内置了扫描窗口上限（`MAX_SCAN_ENTRIES = 50`），避免单次轮询请求过多。建议轮询间隔不要低于 600 秒（10 分钟）。

4. **项目卡片更新检测**：插件通过比较项目的 `updatedAt` 时间戳来判断是否有新卡片，仅推送新增或最近更新的项目卡片。目前未支持监听卡片内字段值的变更（如状态从“待办”变为“进行中”）。

5. **Draft Issue 无法提供链接**：GitHub GraphQL API 中的 Draft Issue 没有 `url` 字段，因此推送时不会附带链接，需要用户直接在项目网页中查看。

6. **合法合规使用**：请确保使用本插件遵守 GitHub 服务条款及适用的法律法规。不得有利用本插件对其他用户造成侵权、对 GitHub API 进行高频请求或任何可能对 GitHub 服务造成压力的行为。用户应自行承担因滥用产生的责任。

~~出问题不要把我供出来，我改这个插件的初衷是为社团私有的看板做推送宣传，不是搞事的，这是我的免责声明喵😭~~