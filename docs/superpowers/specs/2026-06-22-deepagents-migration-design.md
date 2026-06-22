# DeepAgents Migration Design

> **状态：** 设计已确认，待实现

**目标：** 将 LangGraph 手写 StateGraph（Supervisor-Worker + PHASE_ORDER）迁移到 DeepAgents 框架，实现 Skills 可扩展架构和开发逻辑简化。

**核心理由：**
- 技能扩展：新增工艺类型无需修改图结构、路由、提示词
- 简化开发：删除 StateGraph 样板代码（~1500行），用 DeepAgents 声明式配置替代

---

## 架构对比

### 当前架构

```
POST /chat → AgentSession.send_message()
           → _run_with_thinking() → THINKING_PROMPT (fire-and-forget)
           → _run_graph() → StateGraph[AgentState]
               supervisor → chat/analyzer/recommender → supervisor
               supervisor → tools → supervisor
               supervisor → END
           → event_queue → SSE
```

### 目标架构

```
POST /chat → DeepAgent.astream_events()
           → TodoListMiddleware (LLM 自主规划步骤，替代 PHASE_ORDER)
           → SkillsMiddleware (工艺知识 + 工具集动态注入)
           → SubAgentMiddleware (每阶段 spawn 独立子智能体)
           → FilesystemMiddleware (大结果自动落盘)
           → SummarizationMiddleware (长对话自动压缩)
           → AsyncGenerator → SSE
```

---

## 一、整体架构变化

### 删除的文件（约 1500 行）

| 文件 | 原因 |
|------|------|
| `src/process_opt/agent/graph.py` | StateGraph 构建、AgentSession、SessionManager → DeepAgents 接管 |
| `src/process_opt/agent/state.py` | AgentState TypedDict → DeepAgents 内置 State |
| `src/process_opt/agent/nodes/supervisor.py` | SupervisorDecision、阶段路由、help 检测 → TodoListMiddleware |
| `src/process_opt/agent/nodes/worker.py` | ROLE_PROMPTS、PHASE_PROMPTS、worker 节点 → SkillsMiddleware |

### 新增的文件（约 400 行）

| 文件 | 用途 |
|------|------|
| `src/process_opt/agent/deep_agent.py` | `create_process_agent()` 工厂函数 |
| `src/process_opt/agent/skills/__init__.py` | Skill 注册表 + 注册函数 |
| `src/process_opt/agent/skills/adhesive_curing.py` | 点胶固化 Skill 定义 |
| `src/process_opt/agent/skills/injection_molding.py` | 注塑成型 Skill 定义 |
| `src/process_opt/agent/skills/{7 more}.py` | 其他 6 种工艺 Skill 定义 |
| `src/process_opt/agent/middleware.py` | 自定义中间件（阶段感知、规则校验） |

### 保留并改造

| 文件 | 改动 |
|------|------|
| `tools/analysis_tools.py` | 不变，作为工具池供 Skill 按名筛选 |
| `tools/system_tools.py` | 不变 |
| `tools/parameter_tools.py` | 不变 |
| `tools/experiment_tools.py` | 不变 |
| `knowledge/` | 迁移入 `skills/`，JSON 模板内容转为 Skill 定义 |
| `api/agent_routes.py` | 重写，对接 DeepAgents astream_events |
| `api/app.py` | 改动：`create_app` 参数从 graph → agent_factory |
| `api/main.py` | 改动：工具组装方式从 `create_xxx_tools()` 列表 → 工具池字典 |

---

## 二、Skills 系统（双层架构）

```
src/process_opt/agent/skills/
├── process/                  # 工艺技能（会话级，按 process_type 加载）
│   ├── adhesive_curing.md
│   ├── injection_molding.md
│   └── ...
│
├── capabilities/             # 能力技能（按需加载，Claude Code Skill 格式）
│   ├── spc-monitoring.md
│   ├── doe-design.md
│   ├── correlation-analysis.md
│   ├── parameter-recommend.md
│   ├── report-generation.md
│   ├── data-profiling.md
│   ├── product-tracing.md
│   └── line-monitoring.md
│
└── __init__.py               # 自动发现 + 注册 + 加载器
```

### 格式：Markdown 优先

所有 Skill 统一使用 **Markdown frontmatter + 正文** 格式，与 Claude Code Skill 格式同源。非开发人员（工艺工程师）可直接编辑。

### 工艺 Skill（type: process）

```markdown
---
name: adhesive_curing
display_name: 点胶固化
type: process
description: 环氧树脂点胶 + 热固化工艺参数分析
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| temperature | 固化温度 | °C | 100–180 | 150 | critical |
| time | 固化时间 | min | 10–60 | 30 | critical |
| pressure | 点胶压力 | MPa | 0.5–3.0 | 1.5 | major |
| viscosity | 胶水粘度 | mPa·s | 500–3000 | 1500 | minor |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| shear_strength | 剪切强度 | MPa | 15 | 25 |
| void_rate | 气泡率 | % | 0 | 5 |
| cure_depth | 固化深度 | mm | 1.0 | 3.0 |

## 规则约束

- [hard] temperature > 180 → 固化温度超过 180°C 会导致材料降解
- [hard] time < 5 → 固化时间不足 5min 无法完成交联反应
- [soft] pressure > 2.5 → 点胶压力超过 2.5MPa 可能导致溢胶

## 分析提示

- 温度和时间对剪切强度影响最大，优先分析这两个参数的回归关系
- 气泡率与压力、粘度相关，用相关性分析确认
- 固化深度通常只与时间相关，用简单线性回归即可
```

### 能力 Skill（type: capability）

```markdown
---
name: spc-monitoring
display_name: SPC 监控
type: capability
description: 统计过程控制（I-MR 控制图、Cp/Cpk 过程能力分析）
triggers:
  - spc
  - 控制图
  - 过程能力
  - cpk
  - 监控
tools:
  - run_spc
  - query_records
  - get_stats
---

## 功能

对指定设备或产线执行 SPC 监控，生成 I-MR 控制图和过程能力指数（Cp/Cpk）。

## 使用场景

- 用户询问设备过程是否稳定
- 用户要求查看控制图
- 用户询问 Cp/Cpk 值

## 分析步骤

1. 先用 `query_records` 获取该设备最近的数据
2. 用 `run_spc` 对关键参数执行 SPC 分析
3. 判断：Cp < 1.0 → 能力不足；1.0 ≤ Cp < 1.33 → 能力一般；Cp ≥ 1.33 → 能力充分
4. 用 Markdown 表格输出 SPC 结论，含控制图数据

## 输出格式

| 参数 | 均值 | UCL | LCL | Cp | Cpk | 判定 |
|------|------|-----|-----|-----|-----|------|
```

### 自动发现 + 加载

```python
# src/process_opt/agent/skills/__init__.py
import yaml
from pathlib import Path

SKILLS_DIR = Path(__file__).parent

def _parse_skill_md(path: Path) -> dict:
    """解析 Markdown Skill 文件：YAML frontmatter + Markdown 正文。"""
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm)
    meta["system_prompt"] = body.strip()  # 正文即 system_prompt
    return meta

def discover_skills() -> dict[str, dict]:
    """递归扫描 skills/ 目录，自动发现所有 .md Skill 文件。"""
    registry = {}
    for md_file in SKILLS_DIR.rglob("*.md"):
        skill = _parse_skill_md(md_file)
        registry[skill["name"]] = skill
    return registry

def get_process_skills(registry: dict) -> list[dict]:
    """获取所有 type=process 的 Skill。"""
    return [s for s in registry.values() if s.get("type") == "process"]

def get_capability_skills(registry: dict) -> list[dict]:
    """获取所有 type=capability 的 Skill。"""
    return [s for s in registry.values() if s.get("type") == "capability"]
```

### 设计原则

- **Markdown 优先**：工艺工程师可直接编辑参数表、规则、指标
- **自动发现**：放一个 `.md` 文件到 `process/` 或 `capabilities/` 即生效
- **Claude Code Skill 兼容**：frontmatter + 正文格式与 Claude Code Skill 同源
- **正文即提示词**：Markdown 正文直接作为 system_prompt 注入，不需 `_build_prompt()` 拼装
- **工艺 vs 能力分离**：工艺 Skill 会话创建时加载（1个），能力 Skill 对话中按需触发（N个）
- **双层架构 = 原 ROLE_PROMPTS + PHASE_PROMPTS 的进化版**：工艺 Skill = 原 worker 角色提示词，能力 Skill = 原阶段提示词

---

## 三、DeepAgent 组装

### 工厂函数

```python
# src/process_opt/agent/deep_agent.py
from deepagents import create_deep_agent
from deepagents.middleware import (
    TodoListMiddleware,
    SubAgentMiddleware,
    FilesystemMiddleware,
    SummarizationMiddleware,
)
from process_opt.agent.skills import discover_skills, get_capability_skills

# 全局：启动时扫描一次
SKILL_REGISTRY = discover_skills()

async def create_process_agent(
    llm,
    process_type: str,
    tool_pool: dict,  # {"query_records": fn, "run_spc": fn, ...}
):
    # 1. 获取工艺 Skill（Markdown 正文 = system_prompt）
    process_skill = SKILL_REGISTRY.get(process_type)
    if not process_skill:
        raise ValueError(f"Unknown process type: {process_type}")

    # 2. 获取所有能力 Skill（按需触发）
    capability_skills = get_capability_skills(SKILL_REGISTRY)

    # 3. 合并工艺 + 能力 Skill 需要的工具名，从工具池取函数
    all_tool_names = set(process_skill.get("tools", []))
    for cap in capability_skills:
        all_tool_names.update(cap.get("tools", []))
    tools = [tool_pool[name] for name in all_tool_names if name in tool_pool]

    # 4. 组装 DeepAgent
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=process_skill["system_prompt"],  # Markdown 正文
        middleware=[
            TodoListMiddleware(),
            SkillsMiddleware(          # 能力 Skill 按需注入
                skills=capability_skills,
            ),
            SubAgentMiddleware(default_model=llm),
            FilesystemMiddleware(backend="state"),
            SummarizationMiddleware(trigger_tokens=0.85),
        ],
    )
    return agent
```

### 与旧代码的对应关系

| 旧代码（约 250 行） | DeepAgent 替代 |
|---|---|
| `build_graph()` 建图 + 节点 + 边 + 条件路由 | `create_deep_agent()` 一行 |
| `create_supervisor_node()` + `SupervisorDecision` | `TodoListMiddleware` |
| `create_worker_node()` ×3 + `ROLE_PROMPTS` + `PHASE_PROMPTS` | 工艺 Skill 正文 + 能力 Skill（SkillsMiddleware） |
| `_has_pending_tool_calls()` + 安全网路由 | DeepAgents 内部 tool loop |
| `_build_context()` 上下文拼装 | `SummarizationMiddleware` |
| `THINKING_PROMPT` + `_run_with_thinking()` | DeepAgents 内置思考链 |
| `_detect_workflow_intent()` + 关键词匹配 | LLM 从 system_prompt 自主判断 |
| `HELP_MESSAGE` + `_is_help_request()` | 在 system_prompt 中描述 `?` 命令行为 |
| `_build_prompt()` 拼装提示词 | **删除** — Markdown 正文即提示词 |
| `knowledge_loader` + JSON 模板 | **删除** — Markdown Skill 替代 |
| `SKILL_REGISTRY` 手动 import + 注册 | `discover_skills()` 自动扫描 .md 文件 |

---

## 四、API 路由 & SSE 流

### agent_routes.py 重写

```python
# src/process_opt/api/agent_routes.py (重写后)
import asyncio
import json
import uuid
import time
import logging

async def generate():
    try:
        async for event in session["agent"].astream_events(
            {"messages": session.get("pending_messages", [])},
            config={"configurable": {"thread_id": session["thread_id"]}},
            version="v2",
        ):
            sse = _map_deepagent_event(event)
            if sse:
                yield sse
        yield b'data: {"type":"session.status","status":"idle"}\n\n'
    except GeneratorExit:
        pass  # client disconnected, generator naturally stops
```

### SSE 事件映射（保持与前端兼容）

| DeepAgents 事件 | SSE type | 前端组件 |
|---|---|---|
| `on_chat_model_stream` | `message.delta` | ChatBubble 文字流式 |
| `on_tool_start` | `tool.call` | ChatToolCall 工具卡片 |
| `on_tool_end` | `tool.result` | ChatToolCall Markdown 渲染 |
| `on_chain_start` (subagent) | `node.start` | — |
| `on_chain_end` (subagent) | `node.end` | — |
| TodoList 更新 | `phase.change` | PhaseIndicator 步骤条 |

### Session 管理简化

从 `SessionManager` + `AgentSession`（约 120 行）简化为：

```python
_sessions: dict[str, dict] = {}

async def _create_session(agent, thread_id: str) -> str:
    sid = f"ses_{uuid.uuid4().hex[:20]}"
    _sessions[sid] = {
        "agent": agent,
        "thread_id": thread_id,
        "pending_messages": [],
        "created": time.monotonic(),
    }
    return sid

async def _expire_stale(ttl: int = 1800):
    """后台任务：定期清理过期会话。"""
    while True:
        await asyncio.sleep(300)
        now = time.monotonic()
        expired = [sid for sid, s in _sessions.items()
                   if now - s["created"] > ttl]
        for sid in expired:
            del _sessions[sid]
```

### 取消逻辑

DeepAgents 的 `astream_events` 是 `AsyncGenerator`。当 SSE 客户端断开（`GeneratorExit`），生成器自然终止，DeepAgents 内部停止执行。不再需要手动 `session.cancel()` + `_task.cancel()` + 队列排空。

---

## 五、工具池组装（main.py 改动）

```python
# src/process_opt/api/main.py (改动后)
from process_opt.agent.deep_agent import create_process_agent
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.agent.tools.system_tools import create_system_tools
from process_opt.agent.tools.parameter_tools import create_parameter_tools
from process_opt.agent.tools.experiment_tools import create_experiment_tools

# 工具池：按名称索引的扁平字典
tool_pool: dict[str, callable] = {}
for tool in (
    create_analysis_tools(...) +
    create_system_tools(...) +
    create_parameter_tools(...) +
    create_experiment_tools(...)
):
    tool_pool[tool.name] = tool  # @tool 装饰器的 name 属性

# Agent 工厂
async def agent_factory(llm, process_type: str):
    return await create_process_agent(llm, process_type, tool_pool)

# 注册路由
register_agent_routes(app, agent_factory, llm)
```

---

## 六、前向兼容

| 接口 | 兼容性 |
|------|--------|
| `POST /api/v1/agent/session` | 不变 |
| `POST /api/v1/agent/chat` | 不变 |
| `GET /api/v1/agent/chat/{id}/events` | 不变 |
| `GET /api/v1/agent/session/{id}/messages` | 不变 |
| `POST /api/v1/agent/upload` | 不变 |
| `GET /api/v1/agent/processes` | 不变（改用 `list_skills()`） |
| SSE 事件格式 | 兼容（`message.delta`、`tool.call`、`tool.result`、`phase.change`） |
| 前端 | **零改动** |
| Docker Compose | 增加 `deepagents` Python 依赖 |

---

## 七、依赖变更

**pyproject.toml 新增：**
```
"deepagents>=0.5.0",
```

**不再需要显式依赖（由 deepagents 自带）：**
- `langgraph` — DeepAgents 内部使用，不再直接调用

**保留：**
- `langchain-core` — AIMessage、ToolMessage 等基础类型
- `langchain-openai` — LLM 模型适配

---

## 八、风险与缓解

| 风险 | 缓解 |
|------|------|
| DeepAgents 黑盒调试困难 | LangSmith tracing（DeepAgents 原生集成）|
| TodoListMiddleware 规划不可控 | system_prompt 中嵌入硬约束（"必须先 SPC 再 DOE"）|
| Summarization 可能丢失关键工艺参数 | 在 Skill 中标记 `importance: critical` 的参数禁止摘要裁剪 |
| 子智能体间状态不共享 | DeepAgents State 默认通过 thread_id 共享 checkpoints |
| DeepAgents API 不稳定 | 锁定 `deepagents>=0.5,<1.0`，v0.5+ API 已趋于稳定 |
