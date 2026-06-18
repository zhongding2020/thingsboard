# OpenCode → Claude Code 工作上下文迁移

> 设计日期: 2026-06-18 | 状态: 待实现

## 目标

从 OpenCode CLI (v1.15.13) 的 SQLite 数据库中，提取 thingsboard 项目最近 20 个会话的工作上下文，生成一份结构化的 Markdown 文档，使 Claude Code 可以通过 `@` 引用无缝接手开发工作。

## 非目标

- 不迁移 OpenCode 的完整对话日志（只需要摘要上下文）
- 不尝试写入 Claude Code 的原生 `.jsonl` 会话格式
- 不处理 thingsboard 项目以外的会话
- 不对 OpenCode 数据库做任何写入

## 架构

```
OpenCode SQLite DB (~/.local/share/opencode/opencode.db)
         │
         ▼
   ┌─────────────────┐
   │  extractor.py    │  Python 脚本 (单文件)
   │  scripts/        │  仅使用标准库: sqlite3, json, datetime, pathlib
   │  migrate-        │
   │  opencode-       │
   │  context.py      │
   └───────┬──────────┘
           │ SQL 查询 → 解析 JSON → 结构化输出
           ▼
   ┌────────────────────────────────┐
   │  Markdown 文档                  │
   │  docs/superpowers/specs/       │
   │  2026-06-18-opencode-          │
   │  context-migration.md          │
   └────────────────────────────────┘
```

## 数据源

### 数据库路径

`~/.local/share/opencode/opencode.db` (SQLite)

### 涉及的表

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `session` | 会话元数据 | `id`, `project_id`, `title`, `time_created`, `time_updated`, `cost`, `tokens_input`, `tokens_output`, `model` |
| `message` | 用户/AI 消息 | `session_id`, `data` (JSON: `role`, `summary.diffs`, `tokens`, `modelID`) |
| `session_message` | 会话事件流 | `session_id`, `type`, `data` (JSON: agent-switched, model-switched 等) |
| `part` | 消息内容块 | `message_id`, `session_id`, `data` (JSON: text parts, tool calls) |
| `todo` | 待办事项 | `session_id`, `content`, `status`, `priority`, `position` |

### 项目标识

thingsboard 项目 `project_id`: `b52e71c68c3d6152862f3ff4892683dce00d6eb1`

## 提取逻辑

### 1. 会话筛选

```sql
SELECT id, title, time_created, time_updated, cost, tokens_input, tokens_output, model
FROM session
WHERE project_id = ?
ORDER BY time_created DESC
LIMIT 20
```

### 2. 消息提取

对每个筛选出的会话:

```sql
SELECT m.id, m.time_created, m.data
FROM message m
WHERE m.session_id = ?
ORDER BY m.time_created
```

解析 `data` JSON:
- `role`: "user" / "assistant"
- `summary.diffs[]`: 代码变更信息 (file, status, additions, deletions)
- `tokens`: token 消耗
- `modelID` / `providerID`: 使用的模型

### 3. Todo 提取

```sql
SELECT content, status, priority
FROM todo
WHERE session_id IN (...)
ORDER BY session_id, position
```

### 4. 消息内容提取

```sql
SELECT p.data
FROM part p
WHERE p.session_id = ?
ORDER BY p.time_created
```

提取 `data` JSON 中的 `type: "text"` 部分作为消息正文。

## 输出文档结构

```markdown
# OpenCode → Claude Code 工作上下文迁移

> 提取自 OpenCode CLI v1.15.13 | 项目: thingsboard
> 会话范围: 最近 20 个 | 提取时间: <timestamp>

## 1. 工作总览

按工作流分组，展示任务树和完成状态。

## 2. 各会话详情（精简）

每个工作流的每个会话一个子章节:
- **意图**: 用户想做什么
- **完成的操作**: 实际改了什么、做了什么决策
- **涉及文件**: 文件变更列表

## 3. 涉及文件总览

所有会话中修改过的文件，按目录分组汇总。

## 4. 关键设计决策

从对话中提取的重要技术决策和 trade-off。

## 5. 未完成事项

从 todo 表中提取 pending 项。

## 6. 建议的下一步

基于对话上下文的自然延续建议。
```

### 设计原则

- **精简优先**: 高层摘要前置（第 1、3、4、5 节），CC 可快速定位上下文
- **按需深入**: 第 2 节在需要深究某个会话时追查
- **可读性**: 中文输出，结构清晰，适合人类和 AI 快速扫描

## 脚本设计

### 文件位置

`scripts/migrate_opencode_context.py`

### 依赖

仅 Python 标准库: `sqlite3`, `json`, `datetime`, `pathlib`, `argparse`

### CLI 接口

```
python scripts/migrate_opencode_context.py \
  --project-id b52e71c68c3d6152862f3ff4892683dce00d6eb1 \
  --limit 20 \
  --output docs/superpowers/specs/2026-06-18-opencode-context-migration.md
```

### 模块划分（单文件内）

1. `extract_sessions(db, project_id, limit)` — 查询会话列表
2. `extract_messages(db, session_id)` — 查询消息并解析 JSON
3. `extract_todos(db, session_ids)` — 查询未完成的 todo
4. `classify_workflows(sessions)` — 按标题模式将会话归入工作流
5. `build_section_overview(workflows)` — 生成第 1 节（工作总览）
6. `build_section_details(workflows)` — 生成第 2 节（各会话详情）
7. `build_section_files(all_messages)` — 生成第 3 节（涉及文件总览），从 `summary.diffs` 中提取
8. `build_section_decisions(all_messages)` — 生成第 4 节（关键设计决策）
9. `build_section_todos(todos)` — 生成第 5 节（未完成事项）
10. `build_section_next_steps(workflows, todos)` — 生成第 6 节
11. `render_markdown(...)` — 组装最终 Markdown
12. `main()` — 解析参数，协调流程

## 错误处理

| 场景 | 处理 |
|------|------|
| 数据库文件不存在 | 打印明确错误信息并退出 (exit 1) |
| project_id 无匹配 | 打印警告，输出空报告 |
| JSON 解析失败 | 跳过该条消息，打印 warning 到 stderr |
| 输出目录不存在 | 自动创建（`Path.mkdir(parents=True)`） |
| part 表无内容 | 回退到 `message.data` 中的 summary 信息 |
| 时间戳转换失败 | 显示原始 Unix 毫秒时间戳 |

## 测试策略

### 手动验证

- 运行脚本，检查输出 Markdown 的结构完整性
- 抽查 2-3 个会话的摘要是否与 OpenCode 中实际对话一致
- 验证文件列表与实际 git diff 匹配

### 边界情况

- 会话 message 为空 → 标记为 "[无消息记录]"
- 会话标题无明确 Phase 标识 → 归入 "其他"
- todo 表为空 → 第 5 节输出 "无未完成事项"
- 单次会话跨越多个工作流 → 按标题关键词归类

## 不在范围内的内容

- 从 part 表中重建完整工具调用/输出细节（摘要足够）
- 迁移其他项目（mvplus, write_info, global）的会话
- 自动化定期同步（一次性迁移）
- Claude Code session 格式写入
