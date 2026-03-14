# Changelog

本文档记录了 `astrbot_plugin_listen_github` 插件的所有重要变更。

## [1.0.1] - 2026-03-14

### 🐛 Bug 修复

- **修复 `gh_check` 参数解析问题**：修复当 `message_str` 包含命令本体时，命令名被误作为查询目标的 Bug（如搜索 `gh_check` 用户），新增 `_parse_check_args()` 方法正确剥离命令前缀 ([#3](https://github.com/aliveriver/astrbot_plugin_listen_github/pull/3))，非常感谢 sanqi-ya 的贡献！

### ✨ 功能新增

- **监听列表规范化**：新增 `_normalize_watch_list()` 方法，对配置中的监听项去空白、去重、过滤非法值