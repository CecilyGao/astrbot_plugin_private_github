# AstrBot GitHub 动态监听插件

通过 GitHub 公开的 RSS (Atom Feed) 定时获取用户动态、仓库 Release 和 Commit 信息，自动推送到绑定的聊天会话中。

## ✨ 功能特性

- **用户动态监听** — Star、Fork、创建仓库、Push 等公开事件
- **仓库 Release 监听** — 新版本发布提醒
- **仓库 Commit 监听** — 最新提交推送
- **定时轮询** — 可自定义轮询间隔（默认 30 分钟）
- **多会话推送** — 支持绑定多个聊天会话
- **时区转换** — 自动将 GitHub 时间转为本地时区
- **权限控制** — 关键指令仅管理员可用

## 📋 可用指令

| 指令 | 权限 | 说明 |
|------|------|------|
| `/gh_watch <用户名>` | 管理员 | 添加 GitHub 用户到当前会话的监听列表 |
| `/gh_unwatch <用户名>` | 管理员 | 从当前会话移除监听 |
| `/gh_list` | 所有人 | 列出全局配置 + 当前会话的所有监听项 |
| `/gh_check <用户名或owner/repo>` | 管理员 | 立即查看某用户或仓库的最新动态 |
| `/gh_bindhere` | 管理员 | 将当前会话绑定为全局推送目标 |
| `/gh_unbindhere` | 管理员 | 解绑当前会话 |

## ⚙️ 配置项

在 AstrBot WebUI 插件配置页面可设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poll_interval` | int | 1800 | 轮询间隔（秒），最低 60 秒 |
| `max_entries` | int | 5 | 每次推送的最大条目数，设为 0 不限制 |
| `watch_users` | list | [] | 监听的 GitHub 用户名列表 |
| `watch_repos` | list | [] | 监听 Release 的仓库（`owner/repo` 格式） |
| `watch_repos_commits` | list | [] | 监听 Commit 的仓库（`owner/repo` 格式） |
| `timezone` | string | Asia/Shanghai | 时间显示时区 |
| `bound_sessions` | list | [] | 推送目标会话（也可用 `/gh_bindhere` 绑定） |

## 🚀 两种监听模式

1. **全局配置模式**：在 WebUI 中填写 `watch_users`、`watch_repos`、`watch_repos_commits`，动态推送到 `bound_sessions` 中的所有会话
2. **指令模式**：在聊天中使用 `/gh_watch` 添加的用户，仅推送到当前会话

两种模式并行运行，互不冲突。

## 📦 安装

在 AstrBot 中搜索 `astrbot_plugin_listen_github` 安装，或手动克隆到 `data/plugins/` 目录：

```bash
cd AstrBot/data/plugins
git clone https://github.com/aliveriver/astrbot_plugin_listen_github.git
```

**要求**：AstrBot >= 4.9.2

## 📄 许可证

[GPL-3.0](LICENSE)

## 欢迎Issue与PR

-----
*快去视奸你好友的github动态吧）*