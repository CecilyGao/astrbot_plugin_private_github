# Changelog

本文档记录了 `astrbot_plugin_private_github` 插件的所有重要变更。

## [2.0.0] - 2026-04-25

### 🚀 重大变更：多会话独立订阅

- **废除全局绑定机制**：移除 `bound_sessions` 配置项，每个会话（群聊/私聊）可独立管理自己的订阅，互不干扰。
- **新增订阅管理存储**：订阅数据保存在 `data/plugins/astrbot_plugin_private_github/subscriptions.json` 中，每个订阅项单独维护游标。
- **游标隔离**：不同会话的同一仓库/项目订阅拥有独立游标，避免互相影响。
- **指令系统重构**：
  - ✨ 新增 `ghp_subscribe repo <owner/repo> <issues|commits|releases>` – 订阅仓库动态
  - ✨ 新增 `ghp_subscribe project <org/number>` – 订阅组织项目卡片
  - ✨ 新增 `ghp_unsubscribe <序号>` – 取消当前会话的指定订阅
  - ✨ 新增 `ghp_list_subs` – 列出当前会话的所有订阅
  - ⚠️ 废弃 `ghp_bindhere`、`ghp_unbindhere`（仅提示，不再产生实际效果）
  - ⚠️ 废弃 `ghp_list`（改为提示使用 `ghp_list_subs`）
  - ✅ 保留 `ghp_pushnow` 并增强为检查所有会话的所有订阅
  - ✅ 保留 `ghp_check` 临时手动查询功能（仍可使用）

- **权限控制升级**：新增 `whitelist` 配置项（默认空），用于控制哪些普通用户可以使用订阅指令。管理员始终拥有全部权限。
- **轮询逻辑优化**：支持每个会话独立推送，消息仅发送到产生新动态的订阅所属会话。
- **启动行为改进**：自动为所有已有订阅初始化游标，确保不重复推送历史内容。

### 🐛 修复

- 修复了当项目为空时游标初始化失败的 bug。
- 修复了 GraphQL 请求中 `orderBy` 参数导致 schema 错误的问题，改为客户端手动排序。
- 修复了并发轮询时可能导致的游标覆盖问题。

---

## [1.0.0] - 2026-04-25

### ✨ 初始版本发布（已废弃架构）

- 私有仓库监听（Issues/Commits/Releases）
- 组织项目监听（Projects v2）
- 全局绑定会话、全局监听项配置
- Token 认证、定时轮询、手动推送等基础功能