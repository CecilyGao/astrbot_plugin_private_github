
---

## `CHANGELOG.md`

```markdown
# Changelog

本文档记录了 `astrbot_plugin_private_github` 插件的所有重要变更。

## [1.0.0] - 2026-04-25

### ✨ 初始版本发布

- **私有仓库监听**：通过 GitHub REST API 支持监听 `Issues`、`Commits`、`Releases` 动态
- **组织项目监听**：通过 GraphQL API 支持监听 GitHub Projects v2 中新增/更新的卡片（Issue / PR / Draft Issue）
- **Token 认证**：支持使用 Personal Access Token 访问私有资源
- **定时轮询**：可配置轮询间隔（默认 30 分钟），支持游标机制避免重复推送历史内容
- **多会话推送**：支持绑定多个聊天会话，将动态推送到指定群聊/私聊
- **时区转换**：自动将 GitHub 时间转换为本地时区显示
- **指令系统**：
  - `ghp_list` — 列出当前监听项和绑定会话
  - `ghp_check repo ...` — 手动查询仓库动态
  - `ghp_check project ...` — 手动查询项目卡片
  - `ghp_pushnow` — 立即触发全局检查并推送
  - `ghp_bindhere` / `ghp_unbindhere` — 绑定/解绑推送会话
- **并发处理**：多监听项并行拉取和推送，提升效率
- **输入校验**：对仓库名、项目编号进行合法性检查，自动跳过无效配置项
- **配置持久化**：游标和初始化状态存储在 KV 数据库中，插件重启后继续正常工作
- **错误容忍**：单个监听项失败不影响其他项的轮询和推送