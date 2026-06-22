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

## 二、Skills 系统

### Skill 定义格式

每个工艺类型 = 一个 Skill 文件，包含完整知识：参数、质量指标、规则约束、分析提示、可用工具。

```python
# src/process_opt/agent/skills/adhesive_curing.py

ADHESIVE_CURING_SKILL = {
    "name": "adhesive_curing",
    "display_name": "点胶固化",
    "description": "环氧树脂点胶 + 热固化工艺分析",
    "parameters": [
        {"key": "temperature", "name": "固化温度", "unit": "°C",
         "range": [100, 180], "target": 150, "importance": "critical"},
        {"key": "time", "name": "固化时间", "unit": "min",
         "range": [10, 60], "target": 30, "importance": "critical"},
        {"key": "pressure", "name": "点胶压力", "unit": "MPa",
         "range": [0.5, 3.0], "target": 1.5, "importance": "major"},
        {"key": "viscosity", "name": "胶水粘度", "unit": "mPa·s",
         "range": [500, 3000], "target": 1500, "importance": "minor"},
    ],
    "quality_metrics": [
        {"key": "shear_strength", "name": "剪切强度", "unit": "MPa",
         "usl": 25, "lsl": 15},
        {"key": "void_rate", "name": "气泡率", "unit": "%",
         "usl": 5, "lsl": 0},
        {"key": "cure_depth", "name": "固化深度", "unit": "mm",
         "usl": 3.0, "lsl": 1.0},
    ],
    "rules": [
        {"type": "hard", "expr": "temperature > 180",
         "message": "固化温度超过 180°C 会导致材料降解"},
        {"type": "hard", "expr": "time < 5",
         "message": "固化时间不足 5min 无法完成交联反应"},
        {"type": "soft", "expr": "pressure > 2.5",
         "message": "点胶压力超过 2.5MPa 可能导致溢胶"},
    ],
    "tools": [
        "query_records", "get_devices", "get_stats",
        "profile_data", "analyze_correlation", "analyze_pareto",
        "run_regression", "run_spc", "analyze_importance",
        "design_experiment", "analyze_experiment",
        "recommend_params", "optimize_parameters",
        "trace_product", "trace_product_full",
        "build_dataset", "preview_dataset",
        "generate_report",
    ],
    "analysis_hints": [
        "温度和时间对剪切强度影响最大，优先分析这两个参数的回归关系",
        "气泡率与压力、粘度相关，用相关性分析确认",
        "固化深度通常只与时间相关，用简单线性回归即可",
    ],
}
```

### Skill 注册表

```python
# src/process_opt/agent/skills/__init__.py
from .adhesive_curing import ADHESIVE_CURING_SKILL
from .injection_molding import INJECTION_MOLDING_SKILL
from .die_casting import DIE_CASTING_SKILL
from .cnc_machining import CNC_MACHINING_SKILL
from .reflow_soldering import REFLOW_SOLDERING_SKILL
from .heat_treatment import HEAT_TREATMENT_SKILL
from .welding import WELDING_SKILL
from .powder_coating import POWDER_COATING_SKILL

SKILL_REGISTRY: dict[str, dict] = {
    "adhesive_curing": ADHESIVE_CURING_SKILL,
    "injection_molding": INJECTION_MOLDING_SKILL,
    "die_casting": DIE_CASTING_SKILL,
    "cnc_machining": CNC_MACHINING_SKILL,
    "reflow_soldering": REFLOW_SOLDERING_SKILL,
    "heat_treatment": HEAT_TREATMENT_SKILL,
    "welding": WELDING_SKILL,
    "powder_coating": POWDER_COATING_SKILL,
}

def register_skill(skill: dict) -> None:
    """运行时动态注册新工艺 Skill。"""
    SKILL_REGISTRY[skill["name"]] = skill

def get_skill(process_type: str) -> dict | None:
    return SKILL_REGISTRY.get(process_type)

def list_skills() -> list[dict]:
    return [{"process_type": s["name"], "display_name": s["display_name"]}
            for s in SKILL_REGISTRY.values()]
```

### 设计原则

- **新增工艺 = 新增一个 Skill 文件 + 注册**，不改核心代码
- **工具按名筛选**：Skill 声明 `tools: ["run_spc", ...]` → 工厂函数从全局工具池取对应函数
- **system_prompt 自动生成**：`_build_prompt(skill)` 将参数表/规则/指标/hints 转为结构化 Markdown 提示词
- **前端工艺列表**：`list_skills()` 替代 `knowledge_loader.list_processes()`

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

async def create_process_agent(
    llm,
    process_type: str,
    tool_pool: dict,  # {"query_records": fn, "run_spc": fn, ...}
):
    skill = get_skill(process_type)
    if not skill:
        raise ValueError(f"Unknown process type: {process_type}")

    # 1. system_prompt 完全由 Skill 定义生成
    system_prompt = _build_prompt(skill)

    # 2. 从全局工具池筛选取该 Skill 需要的工具
    tools = [tool_pool[name] for name in skill["tools"] if name in tool_pool]

    # 3. 组装 DeepAgent
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            TodoListMiddleware(),
            SkillsMiddleware(
                skills=list(SKILL_REGISTRY.values()),
                current=process_type,
            ),
            SubAgentMiddleware(default_model=llm),
            FilesystemMiddleware(backend="state"),
            SummarizationMiddleware(trigger_tokens=0.85),
        ],
    )
    return agent


def _build_prompt(skill: dict) -> str:
    """从 Skill 定义生成结构化 system_prompt。"""
    params_table = "\n".join(
        f"| {p['key']} | {p['name']} | {p['unit']} | "
        f"{p['range'][0]}–{p['range'][1]} | {p['target']} | {p['importance']} |"
        for p in skill["parameters"]
    )
    metrics_table = "\n".join(
        f"| {m['key']} | {m['name']} | {m['unit']} | "
        f"{m.get('lsl', '-')} | {m.get('usl', '-')} |"
        for m in skill["quality_metrics"]
    )
    rules_text = "\n".join(
        f"- [{r['type']}] {r['expr']}: {r['message']}" for r in skill["rules"]
    )
    hints_text = "\n".join(f"- {h}" for h in skill["analysis_hints"])

    return f"""## 工艺类型: {skill['display_name']} ({skill['name']})

{skill['description']}

### 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
{params_table}

### 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
{metrics_table}

### 规则约束

{rules_text}

### 分析提示

{hints_text}

### 输出格式

- 所有数据分析结果以 Markdown 表格呈现
- 参数推荐需附带预测质量指标值和置信度
- 实验设计结果需包含因子水平表和 ANOVA 分析
"""
```

### 与旧代码的对应关系

| 旧代码（约 200 行） | DeepAgent 替代 |
|---|---|
| `build_graph()` 建图 + 节点 + 边 + 条件路由 | `create_deep_agent()` 一行 |
| `create_supervisor_node()` + `SupervisorDecision` | `TodoListMiddleware` |
| `create_worker_node()` ×3 + `ROLE_PROMPTS` + `PHASE_PROMPTS` | `system_prompt` + `SkillsMiddleware` |
| `_has_pending_tool_calls()` + 安全网路由 | DeepAgents 内部 tool loop |
| `_build_context()` 上下文拼装 | `SummarizationMiddleware` |
| `THINKING_PROMPT` + `_run_with_thinking()` | DeepAgents 内置思考链 |
| `_detect_workflow_intent()` + 关键词匹配 | LLM 从 system_prompt 自主判断 |
| `HELP_MESSAGE` + `_is_help_request()` | 在 system_prompt 中描述 `?` 命令行为 |

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
