# 工艺参数调优专家 Agent — P1 框架设计

> 状态: **已确认** | 日期: 2026-06-17 | 作者: Agent + User

## 概述

用 **LangGraph 替代 OpenCode 容器池** 作为 AI Agent 引擎，搭建工艺参数调优专家系统的基础框架。以"点胶固化"作为首个工艺场景跑通全链路。

### 子项目分解

| 编号 | 子项目 | 核心交付 | 状态 |
|------|--------|----------|------|
| P1 | Agent 框架 + 知识底座 | LangGraph 替代 OpenCode，知识库，工具集，对话 UI | **本文档** |
| P2 | DOE 引擎 | 实验设计生成（全因子/部分因子/响应面/Taguchi）、ANOVA | 后续 |
| P3 | 实验管理与追溯 | 实验执行追踪、参数迭代历史、知识追溯链 | 后续 |
| P4 | 报告 + 多工艺 | 自动分析报告、多工艺模板（注塑、焊接扩展） | 后续 |

### P1 目标

- 用 LangGraph 替代 Docker 容器池，agent 作为 Python 模块运行在 FastAPI 同一进程
- 构建 JSON 模板驱动的工艺知识底座，先支持"点胶固化"
- 定义 11 个分析工具，封装现有 `/api/v1/analysis/*` 能力
- 保持现有异步 + SSE 流式交互模式，前端改动最小化
- 特性开关支持新老引擎并行，可随时回滚

---

## 1. 整体架构

### 当前（容器池）→ 目标（LangGraph 进程内）

```
当前:                                  目标:
Vue SPA                               Vue SPA
  ├─ /api/v1/analysis/*                 ├─ /api/v1/analysis/*
  │    → FastAPI → PostgreSQL           │    → FastAPI → PostgreSQL
  └─ /api/opencode/*                    └─ /api/v1/agent/*
       → 容器池 → 5x Docker(OpenCode)        → LangGraph Agent (进程内)
         → AGENTS.md                         ├─ 知识库 (JSON 模板)
         → DeepSeek API                      ├─ 工具集 (分析 API 封装)
                                             ├─ StateGraph 编排
                                             └─ DeepSeek API
```

### 新增模块

```
src/process_opt/
├── agent/              ← 新增: LangGraph Agent 核心
│   ├── graph.py        ← StateGraph 编译
│   ├── state.py        ← AgentState
│   ├── nodes/          ← 工作节点
│   │   ├── supervisor  ← 意图路由
│   │   ├── chat        ← 自由对话
│   │   ├── analyzer    ← 数据分析
│   │   └── recommender ← 参数推荐
│   ├── tools/          ← Tool 定义
│   │   └── analysis_tools.py
│   └── prompts/        ← Prompt 模板
│       └── templates.py
├── knowledge/          ← 新增: 工艺知识底座
│   ├── base.py         ← ProcessTemplate 模型
│   ├── loader.py       ← JSON 加载器
│   ├── rules.py        ← 规则引擎
│   └── templates/      ← 工艺模板
│       └── adhesive_curing.json
├── api/
│   └── agent_routes.py ← 新增: Agent API 路由
└── container_pool/     ← 待废弃 (P1 过渡保留)
```

### 新增依赖

```toml
"langgraph>=0.2.0"
"langchain-openai>=0.2.0"
"langchain-core>=0.3.0"
```

移除: `docker>=7.0.0`（P1 结束时删除）

---

## 2. StateGraph 编排设计

### AgentState

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 对话历史（自动追加）
    user_id: str                              # 用户标识
    process_type: str                         # 当前工艺
    intent: str                               # 当前意图
    context: dict                             # 上下文缓存
    tool_results: dict                        # 工具调用结果
    next: str                                 # supervisor 路由目标
```

### Graph 结构: Supervisor-Worker 模式

```
         ┌──── START ────┐
         │               │
         v               │
    ┌──────────┐         │
    │supervisor│ ←───────┤
    └────┬─────┘         │
         │               │
  ┌──────┼──────┐        │
  v      v      v        │
┌────┐┌──────┐┌────────┐ │
│chat││analy-││recom-  │ │
│    ││zer   ││mender  │ │
└──┬─┘└──┬───┘└───┬────┘ │
   │     │        │      │
   │  ┌──┴──┐     │      │
   └─→│tools│←────┘      │
      └──┬──┘            │
         └───────────────┘
```

### 节点职责

| 节点 | 触发场景 | 处理逻辑 |
|------|----------|----------|
| **supervisor** | 每次用户输入 / tool 返回后 | LLM 分类意图 → 路由到对应 worker 或 FINISH |
| **chat** | 通用问答、工艺咨询 | 加载知识库 → SystemMessage → LLM + tools |
| **analyzer** | "分析这批数据"、"看相关性" | 确定分析类型 → 调用对应 API → LLM 解读结果 |
| **recommender** | "优化参数"、"推荐实验" | 调用 regression + recommendation → 结合工艺约束过滤 |
| **tools** | LLM 决定调用工具 | 执行工具 → 返回结果到 supervisor |

### 工具集 (P1)

| 工具 | 对应 API | 用途 |
|------|----------|------|
| query_records | GET /api/v1/analysis/records | 查询生产数据 |
| get_devices | GET /api/v1/analysis/devices | 设备列表 |
| get_stats | GET /api/v1/analysis/stats | 统计概览 |
| profile_data | POST /api/v1/analysis/profile | 数据画像 |
| analyze_correlation | POST /api/v1/analysis/correlation | 相关性 |
| analyze_pareto | POST /api/v1/analysis/pareto | 帕累托 |
| run_regression | POST /api/v1/analysis/regression | 回归 |
| recommend_params | POST /api/v1/analysis/recommendation | 参数推荐 |
| run_spc | POST /api/v1/analysis/spc | SPC 监控 |
| get_parameters | GET /api/v1/parameters/sets | 参数集 |
| get_process_knowledge | GET /api/v1/knowledge/processes/{type} | 工艺知识 |

---

## 3. 工艺知识底座

### 设计原则

JSON 模板驱动，每种工艺一个文件。Agent 通过 `get_process_knowledge` 工具加载，注入各节点 SystemMessage。

### 模板 Schema

```json
{
  "process_type": "adhesive_curing",
  "display_name": "点胶固化",
  "description": "...",
  "parameters": [
    {
      "key": "cure_temp",
      "name": "固化温度",
      "unit": "°C",
      "type": "continuous",
      "range": {"min": 80, "max": 180},
      "target": {"min": 120, "max": 150},
      "importance": "critical",
      "description": "...",
      "notes": "..."
    }
  ],
  "quality_metrics": [
    {"key": "shear_strength", "name": "剪切强度", "unit": "kgf/cm²"}
  ],
  "rules": [
    {
      "type": "hard_constraint",
      "expression": "cure_temp > 180",
      "message": "固化温度不超过180°C，否则胶水老化"
    },
    {
      "type": "soft_guideline",
      "expression": "...",
      "message": "..."
    },
    {
      "type": "dependency",
      "trigger": "cure_temp increase",
      "effect": "可适当缩短 cure_time",
      "message": "温度每升高10°C，固化时间可减少约5分钟"
    }
  ],
  "analysis_hints": [...]
}
```

### 参数等级

- **critical**: 关键参数，必须分析（如固化温度、固化时间、胶量）
- **important**: 重要参数（如点胶压力）
- **auxiliary**: 辅助参数（如环境湿度）

### 规则类型

- **hard_constraint**: 硬约束，不可违反
- **soft_guideline**: 软建议，警告
- **dependency**: 参数关联关系

### 点胶固化工艺参数 (P1)

| 参数 | 单位 | 范围 | 目标 | 等级 |
|------|------|------|------|------|
| 固化温度 (cure_temp) | °C | 80-180 | 120-150 | 关键 |
| 固化时间 (cure_time) | min | 10-120 | 30-60 | 关键 |
| 胶量 (glue_amount) | mg | 5-50 | 15-30 | 关键 |
| 点胶压力 (dispense_pressure) | kPa | 50-300 | 100-200 | 重要 |
| 环境湿度 (ambient_humidity) | %RH | 20-80 | 30-60 | 辅助 |

质量指标: 剪切强度 (kgf/cm²)、气泡率 (%)、胶水溢出量 (mm)

---

## 4. API 与 SSE 流设计

### 端点

| 端点 | 方法 | 说明 | 响应 |
|------|------|------|------|
| `/api/v1/agent/session` | POST | 创建会话 | `{"session_id": "xxx"}` |
| `/api/v1/agent/chat` | POST | 发送消息（异步） | **204 No Content** |
| `/api/v1/agent/chat/{id}/events` | GET | SSE 事件流 | SSE stream |
| `/api/v1/agent/session/{id}/messages` | GET | 获取消息历史 | `[{role, content, ...}]` |
| `/api/v1/agent/session` | GET | 列出会话 | `[{session_id, ...}]` |
| `/api/v1/knowledge/processes` | GET | 列出支持工艺 | `[{type, name}]` |
| `/api/v1/knowledge/processes/{type}` | GET | 获取工艺模板 | `ProcessTemplate` |

### SSE 事件类型

| 事件 | 数据 | 说明 |
|------|------|------|
| `session.status` | `{"status": "busy\|idle"}` | 会话状态变更 |
| `node.start` | `{"node": "analyzer", "intent": "..."}` | 进入 Worker |
| `node.end` | `{"node": "analyzer"}` | Worker 完成 |
| `tool.call` | `{"name": "...", "args": {...}}` | 开始调用工具 |
| `tool.result` | `{"name": "...", "data": {...}}` | 工具返回 |
| `message.delta` | `{"text": "..."}` | LLM 逐字输出 |
| `message.complete` | `{"tokens": {...}}` | 一轮回答结束 |
| `error` | `{"message": "..."}` | 异常 |

### 会话管理

内存 dict: `session_id → AgentInstance + AgentState`，不依赖 Docker。P1 不做持久化（后续轮次考虑 Redis/PostgreSQL 持久化）。

### 前端集成

复用现有 AgentChat.vue 的异步 + SSE 模式：

1. `opencode.ts` → `agent.ts`，URL 前缀 `/opencode` → `/api/v1/agent`
2. 事件名映射适配（`message.part.delta` → `message.delta` 等）
3. 新增工艺选择下拉框
4. 特性开关控制: `VITE_AGENT_ENGINE=langgraph | opencode`

---

## 5. 实施计划

### 开发顺序 (7步)

1. **知识底座**: knowledge/ 包 + adhesive_curing.json（可独立开发测试）
2. **Agent 骨架**: agent/ 包 + state.py + graph.py + supervisor 路由
3. **工具定义**: 11 个 `@tool` 函数封装分析 API
4. **Worker 节点**: chat_node + analyzer_node + recommender_node
5. **API 路由 + SSE**: agent_routes.py + astream_events → SSE 映射
6. **前端适配**: AgentChat.vue 事件映射 + 工艺选择
7. **清理**: 移除 container_pool/、docker-compose.yml 中 opencode 相关配置

### 迁移策略

- Step 1-6 期间 `/api/opencode/*` 与 `/api/v1/agent/*` 并行
- 前端通过 `VITE_AGENT_ENGINE` 开关选择引擎
- Step 7 确认稳定后，删除旧路由和容器池代码
- 回滚: 设置 `VITE_AGENT_ENGINE=opencode` 即可恢复

### P1 不包含

| 能力 | 状态 | 目标轮 |
|------|------|--------|
| DOE 实验设计生成引擎 | Agent 可建议，无结构化 DOE | P2 |
| 实验管理 UI | 无 | P3 |
| 知识追溯链 | 无 | P3 |
| 自动报告生成 | Agent 可生成文本，无模板化 | P4 |
| 多工艺模板 | 框架支持，仅实现胶固 | P4 |

---

## 6. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LangGraph 流式事件与 SSE 格式不匹配 | 前端渲染异常 | 增加事件映射层，兼容新旧格式 |
| DeepSeek API 与 langchain-openai 兼容性 | tool calling 异常 | 已验证 volcengine ARK 兼容 OpenAI 格式 |
| 会话内存占用过高 | 内存泄漏 | 30min TTL + LRU 淘汰 |
| LangGraph 学习曲线 | 开发延期 | 先做 chat node（最简单），逐节点增量开发 |
