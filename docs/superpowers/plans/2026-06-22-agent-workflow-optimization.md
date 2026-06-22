# Agent 工艺参数调优工作流 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the agent from reactive Q&A into a guided 5-phase process optimization workflow (Define → Explore → Analyze → Optimize → Verify).

**Architecture:** Supervisor gains a `workflow` mode with phase-state machine routing. Worker receives phase-specific system prompts. SSE stream emits `phase.change` events. Frontend renders a PhaseIndicator progress bar.

**Tech Stack:** Python/LangGraph (backend), Vue 3/TypeScript (frontend)

**Spec:** [2026-06-22-agent-workflow-optimization-design.md](../specs/2026-06-22-agent-workflow-optimization-design.md)

## Global Constraints

- Workflow mode auto-detected from user intent, or triggered by `__start_workflow__` message
- Phase advancement decided by LLM (PhaseDecision structured output), not hardcoded rules
- Goal/baseline/recommendation stored in State; large data via dataset_id reference
- All tools return Markdown strings (existing constraint)
- PhaseIndicator only visible when mode === "workflow"

## File Structure

```
src/process_opt/agent/
├── state.py              # MODIFY: add 6 workflow fields
├── nodes/supervisor.py   # MODIFY: add workflow mode + PhaseDecision + routing
├── nodes/worker.py       # MODIFY: add 5 phase system prompts
└── api/agent_routes.py   # MODIFY: add phase.change SSE event

web/src/components/agent/
├── PhaseIndicator.vue    # CREATE: workflow progress bar
├── ChatView.vue          # MODIFY: integrate PhaseIndicator
└── ChatInput.vue         # MODIFY: add workflow shortcut button

web/src/composables/
├── useChatStream.ts      # MODIFY: add onPhase callback
└── useChatMessages.ts    # MODIFY: add workflowPhase state
```

---

### Task 1: Extend AgentState with workflow fields

**Files:**
- Modify: `src/process_opt/agent/state.py`

**Interfaces:**
- Produces: updated `AgentState` TypedDict with 6 new optional fields

- [ ] **Step 1: Replace state.py**

```python
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    process_type: str
    intent: str
    next: str

    # Workflow fields
    mode: str              # "chat" | "workflow"
    phase: str             # "define"|"explore"|"analyze"|"optimize"|"verify"|""
    goal: dict | None      # {"target_metric":..., "direction":..., "usl":..., "lsl":..., "target_value":...}
    baseline: dict | None  # {"current_cpk":..., "current_params":{...}}
    recommendation: dict | None  # {"params":{...}, "predicted_cpk":..., "model_r2":...}
    dataset_id: str        # Explore phase dataset reference
    experiment_plan_id: int  # DOE plan reference
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/agent/state.py
git commit -m "feat: add workflow fields to AgentState"
```

---

### Task 2: Add workflow routing to Supervisor

**Files:**
- Modify: `src/process_opt/agent/nodes/supervisor.py`

**Interfaces:**
- Consumes: AgentState (with new workflow fields)
- Produces: `SupervisorDecision` (extended), `PhaseDecision`, `_detect_workflow_mode()`, updated `create_supervisor_node()`

- [ ] **Step 1: Replace supervisor.py**

```python
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel
from typing import Literal

from process_opt.agent.state import AgentState


class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "TOOLS", "FINISH"]
    phase_action: Literal["STAY", "ADVANCE", "BACK", "FINISH"] | None = None


class PhaseDecision(BaseModel):
    action: Literal["STAY", "ADVANCE", "BACK", "FINISH"]
    reason: str


PHASE_ORDER = ["define", "explore", "analyze", "optimize", "verify"]

PHASE_PROMPTS = {
    "define": "用户正在「明确目标与基准」阶段。需引导用户设定优化目标、查看当前基准。完成后推进到 explore。",
    "explore": "用户正在「设计试验与探索」阶段。需构建数据集或设计DOE实验。产出 dataset_id 后推进到 analyze。",
    "analyze": "用户正在「数据分析与建模」阶段。需执行相关性、回归、重要性分析。产出分析结论后推进到 optimize。",
    "optimize": "用户正在「训优与参数推荐」阶段。需调用推荐工具并校验规则。产出推荐参数后推进到 verify。",
    "verify": "用户正在「验证与闭环」阶段。汇总优化结果、对比基准、建议提交审批。用户确认后 FINISH。",
}

WORKFLOW_TRIGGERS = [
    "优化", "调优", "改善", "提高", "降低", "提升", "改进",
    "参数推荐", "工艺优化", "质量改善", "doe", "实验设计",
]


def _detect_workflow_intent(text: str) -> bool:
    """Check if user message indicates a process optimization intent."""
    lower = text.lower()
    return any(t in lower for t in WORKFLOW_TRIGGERS) or "__start_workflow__" in text


def _has_pending_tool_calls(state: AgentState) -> bool:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            return True
        if isinstance(msg, ToolMessage):
            return False
        if isinstance(msg, AIMessage):
            return False
    return False


def _build_context(state: AgentState) -> str:
    parts: list[str] = []

    mode = state.get("mode", "chat")
    phase = state.get("phase", "")

    if mode == "workflow" and phase:
        parts.append(f"当前模式: 工艺调优工作流")
        parts.append(f"当前阶段: {phase} ({PHASE_PROMPTS.get(phase, '')})")
        parts.append(f"阶段顺序: {' → '.join(PHASE_ORDER)}")
        parts.append(f"阶段目标: {state.get('goal')}")
        parts.append(f"阶段基准: {state.get('baseline')}")
        parts.append(f"数据集ID: {state.get('dataset_id', '')}")
        parts.append(f"实验方案ID: {state.get('experiment_plan_id', 0)}")
        parts.append(f"推荐结果: {state.get('recommendation')}")
    else:
        ai_turns = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
        parts.append(f"当前对话轮次: {ai_turns} (超过 3 轮应优先考虑 FINISH)")

    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            parts.append(f"用户问题: {str(msg.content)[:300]}")
            break

    recent = [m for m in state["messages"] if not isinstance(m, SystemMessage)][-4:]
    for msg in recent:
        if isinstance(msg, HumanMessage):
            continue
        if isinstance(msg, AIMessage):
            has_tools = getattr(msg, "tool_calls", None)
            content = str(msg.content)[:200] if msg.content else ""
            if has_tools:
                tool_names = [tc.get("name", "?") for tc in msg.tool_calls]
                parts.append(f"AI 调用了工具: {', '.join(tool_names)}")
                if content:
                    parts.append(f"AI 附带文本: {content}")
            elif content:
                parts.append(f"助手已回复 (摘要): {content}")
        elif isinstance(msg, ToolMessage):
            parts.append(f"工具返回结果: {str(msg.content)[:150]}")

    return "\n".join(parts)


def create_supervisor_node(llm: BaseChatModel):
    structured_llm = llm.with_structured_output(SupervisorDecision, method="function_calling")
    phase_llm = llm.with_structured_output(PhaseDecision, method="function_calling")

    async def supervisor_node(state: AgentState) -> dict:
        if _has_pending_tool_calls(state):
            return {"next": "tools"}

        # Detect workflow mode entry
        mode = state.get("mode", "chat")
        phase = state.get("phase", "")

        if mode != "workflow":
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    if _detect_workflow_intent(str(msg.content)):
                        return {"next": "analyzer", "mode": "workflow", "phase": "define"}
                    break

        ctx = _build_context(state)

        if mode == "workflow" and phase:
            # Phase advancement decision
            phase_prompt = (
                f"当前处于工艺调优工作流「{phase}」阶段。\n"
                f"阶段说明: {PHASE_PROMPTS.get(phase, '')}\n\n"
                f"根据对话上下文，判断当前阶段是否已完成、应推进到下一阶段、回退还是完成：\n"
                f"- STAY: 当前阶段任务未完成，需继续\n"
                f"- ADVANCE: 当前阶段已完成，推进到下一阶段\n"
                f"- BACK: 用户对结果不满意，回退到上一阶段\n"
                f"- FINISH: 整个调优流程已完成\n\n"
                f"{ctx}"
            )
            decision: PhaseDecision = await phase_llm.ainvoke([SystemMessage(content=phase_prompt)])

            if decision.action == "ADVANCE":
                idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else -1
                next_phase = PHASE_ORDER[idx + 1] if idx >= 0 and idx + 1 < len(PHASE_ORDER) else ""
                if next_phase:
                    return {"next": "analyzer", "phase": next_phase, "phase_action": "ADVANCE", "prev_phase": phase}
                else:
                    return {"next": "FINISH", "phase": "", "phase_action": "FINISH", "prev_phase": phase}
            elif decision.action == "BACK":
                idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else 0
                prev_phase = PHASE_ORDER[idx - 1] if idx > 0 else "define"
                return {"next": "analyzer", "phase": prev_phase, "phase_action": "BACK", "prev_phase": phase}
            elif decision.action == "FINISH":
                return {"next": "FINISH", "phase": "", "phase_action": "FINISH", "prev_phase": phase}
            else:
                return {"next": "analyzer", "phase": phase}

        # Normal chat mode routing
        prompt = (
            "你是对话路由器。根据上下文决定下一步路由。\n\n"
            "## 路由选项\n"
            "- TOOLS: 仅当 AI 已发起工具调用且工具尚未执行时使用 (通常自动处理)\n"
            "- CHAT: 用户在进行通用问答、工艺咨询、知识解释\n"
            "- ANALYZER: 用户需要执行数据分析 (SPC、相关性、回归、DOE等)\n"
            "- RECOMMENDER: 用户需要参数推荐或优化方案\n"
            "- FINISH: 助手已给出完整的、实质性的回答，本轮对话结束\n\n"
            "## 关键规则\n"
            "1. 如果助手刚刚给出了包含数据、分析结果或建议的完整回复 → 必须 FINISH\n"
            "2. 不要在助手给出完整回复后再路由到其他 worker (避免死循环)\n"
            "3. 对话轮次超过 3 轮时，优先选择 FINISH\n"
            "4. 工具调用由程序自动检测，通常不需要手动选择 TOOLS\n\n"
            f"{ctx}"
        )

        result: SupervisorDecision = await structured_llm.ainvoke([SystemMessage(content=prompt)])
        intent = result.intent.upper()
        if intent == "FINISH":
            return {"next": "FINISH"}
        return {"next": intent.lower()}

    return supervisor_node
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/agent/nodes/supervisor.py
git commit -m "feat: add workflow mode detection and phase routing to supervisor"
```

---

### Task 3: Add phase-specific system prompts to Worker

**Files:**
- Modify: `src/process_opt/agent/nodes/worker.py`

**Interfaces:**
- Consumes: AgentState (now has mode/phase)
- Produces: `ROLE_PROMPTS` extended, `create_worker_node()` reads phase from state

- [ ] **Step 1: Add PHASE_PROMPTS and update worker**

Add this new constant before `ROLE_PROMPTS`:

```python
PHASE_PROMPTS = {
    "define": (
        "## 当前阶段：明确目标与基准（Define）\n\n"
        "### 任务\n"
        "1. 引导用户明确：优化哪个质量指标？方向（最大化/最小化/达标）？\n"
        "2. 调用 get_process_knowledge 获取工艺规范（USL/LSL）\n"
        "3. 调用 get_latest_active_parameters 获取当前参数作为基准\n"
        "4. 调用 run_spc 获取当前 Cpk 基线\n"
        "5. 汇总为「优化目标卡」表格\n\n"
        "### 输出格式\n"
        "| 项目 | 内容 |\n"
        "|------|------|\n"
        "| 优化目标 | 剪切强度 ↑ |\n"
        "| USL / LSL | N/A / 80 |\n"
        "| 当前 Cpk | 0.82 |\n"
        "| 当前参数 | 固化温度 145°C, ... |\n\n"
        "### 规则\n"
        "- 不要跳过工具调用，必须先获取真实数据\n"
        "- 完成后自然结束，由 Supervisor 推进到下一阶段"
    ),
    "explore": (
        "## 当前阶段：设计试验与探索（Explore）\n\n"
        "### 任务\n"
        "1. 若历史数据 ≥ 30条：build_dataset → profile_data → analyze_pareto\n"
        "2. 若数据不足：引导用户设计 DOE（design_experiment），建议 Box-Behnken 或 Central Composite\n"
        "3. 若设计了实验：提示用户按实验矩阵执行并记录结果\n"
        "4. 将 dataset_id 或 experiment_plan_id 告知用户\n\n"
        "### 规则\n"
        "- 数据量判断：先调用 get_stats 查看记录数\n"
        "- DOE 因素建议基于 Define 阶段的 goal 和 get_process_knowledge 结果\n"
        "- 完成后自然结束"
    ),
    "analyze": (
        "## 当前阶段：数据分析与建模（Analyze）\n\n"
        "### 任务\n"
        "1. 基于 Explore 阶段的 dataset_id，执行：\n"
        "   - analyze_correlation（相关性矩阵）\n"
        "   - analyze_importance（特征重要性排序）\n"
        "   - run_regression（回归建模，输出 R² 和系数）\n"
        "2. 若有 DOE 数据：analyze_experiment（ANOVA 方差分析）\n"
        "3. 识别关键因子，评估模型质量\n\n"
        "### 输出格式\n"
        "- 关键因子排名表\n"
        "- 回归模型摘要（R², RMSE, 显著因子）\n\n"
        "### 规则\n"
        "- 使用 Explore 阶段产出的 dataset_id\n"
        "- 分析结果用表格呈现\n"
        "- 完成后自然结束"
    ),
    "optimize": (
        "## 当前阶段：训优与参数推荐（Optimize）\n\n"
        "### 任务\n"
        "1. 调用 recommend_params 或 optimize_parameters（多目标时）\n"
        "2. 自动传入 Define 阶段的 goal 约束（USL/LSL/target_value）\n"
        "3. 调用 get_process_knowledge 校验工艺规则\n"
        "4. 对比推荐参数 vs 当前基准\n\n"
        "### 输出格式\n"
        "| 参数 | 当前值 | 推荐值 | 调整 |\n"
        "|------|--------|--------|------|\n"
        "| 固化温度 | 145°C | 152°C | +7°C |\n\n"
        "- 预测 Cpk: 0.82 → 1.45\n"
        "- 风险提示（如有规则违规）\n\n"
        "### 规则\n"
        "- 必须基于 Analyze 阶段的分析结果选择优化参数\n"
        "- 自动校验工艺规则，违规项标注 ❌ 或 ⚠\n"
        "- 完成后自然结束"
    ),
    "verify": (
        "## 当前阶段：验证与闭环（Verify）\n\n"
        "### 任务\n"
        "1. 汇总整个调优过程的产出\n"
        "2. 调优前后对比表\n"
        "3. 建议用户下一步操作：\n"
        "   - 提交审批（submit_parameter_set）→ 试验验证 → SPC 持续监控\n"
        "4. 若用户不满意推荐结果：可建议回退到 Explore/Analyze/Optimize 阶段\n\n"
        "### 输出格式\n"
        "- 调优前后对比表\n"
        "- 下一步操作建议\n\n"
        "### 规则\n"
        "- 汇总 Define → Explore → Analyze → Optimize 的全流程产出\n"
        "- 给出清晰可操作的下一步建议\n"
        "- 完成后自然结束"
    ),
}
```

Then update `create_worker_node()` to inject phase prompt when in workflow mode:

```python
def create_worker_node(role: str, llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    if role not in ROLE_PROMPTS:
        raise ValueError(f"Unknown role: {role}. Valid: {list(ROLE_PROMPTS.keys())}")

    role_cfg = ROLE_PROMPTS[role]
    _all_processes = knowledge_loader.list_processes()

    async def worker_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = (
            knowledge_loader.build_system_prompt(template, all_processes=_all_processes)
            if template
            else ""
        )

        # Inject phase-specific prompt when in workflow mode
        mode = state.get("mode", "chat")
        phase = state.get("phase", "")
        phase_prompt = ""
        if mode == "workflow" and phase and phase in PHASE_PROMPTS:
            phase_prompt = "\n\n" + PHASE_PROMPTS[phase]

        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}"
                f"{role_cfg['title']}。\n\n"
                f"{role_cfg['instructions']}"
                f"{phase_prompt}\n\n"
                f"{knowledge_prompt}"
            )
        )
        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return worker_node
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/agent/nodes/worker.py
git commit -m "feat: add 5-phase system prompts for workflow worker"
```

---

### Task 4: Add phase.change SSE event

**Files:**
- Modify: `src/process_opt/api/agent_routes.py`

**Interfaces:**
- Consumes: supervisor_node now returns `phase`, `phase_action`, `prev_phase` in state
- Produces: `phase.change` SSE event in `_map_event()`

- [ ] **Step 1: Add phase.change event to _map_event**

Insert after the `on_chain_end` handler for supervisor (line ~149):

```python
    if kind == "on_chain_end":
        node_name = event.get("name", "")
        if node_name == "supervisor":
            # Emit phase.change when phase transitions
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                phase = output.get("phase", "")
                phase_action = output.get("phase_action", "")
                prev_phase = output.get("prev_phase", "")
                if phase_action in ("ADVANCE", "BACK") and phase:
                    data = json.dumps({
                        "type": "phase.change",
                        "phase": phase,
                        "prev_phase": prev_phase,
                        "action": phase_action,
                    })
                    yield f"data: {data}\n\n".encode()

            if _supervisor_text.strip():
                data = json.dumps({"type": "agent.trace", "node": "supervisor", "text": _supervisor_text.strip()})
                _supervisor_text = ""
                return f"data: {data}\n\n".encode()
            return None
```

Note: The existing `_map_event` is a plain function returning `bytes | None`. For the phase change to yield, it needs to become a generator or the phase event logic moves elsewhere. Since `_map_event` is called per-event in a loop, the simplest approach: add a `_pending_phase_event` global variable, set it when phase changes, and yield it on the next call.

Actually, the simplest fix: in `_map_event`, when supervisor chain ends and phase changes, set a module-level variable `_pending_phase_event`. Then in the SSE `generate()` loop in `stream_events`, check and flush `_pending_phase_event` after each `_map_event` call. But that's complex.

Simpler approach: just modify `_map_event` to handle the supervisor `on_chain_end` differently — append the phase event data to a list and then also include it in the returned bytes. Or even simpler: make `_map_event` write the phase event inline.

Let's use the simplest approach — modify the supervisor chain end handler:

```python
    if kind == "on_chain_end":
        node_name = event.get("name", "")
        if node_name == "supervisor":
            output = event.get("data", {}).get("output", {})
            result_parts: list[bytes] = []

            # Phase change event
            if isinstance(output, dict):
                phase = output.get("phase", "")
                phase_action = output.get("phase_action", "")
                prev_phase = output.get("prev_phase", "")
                if phase_action in ("ADVANCE", "BACK") and phase:
                    data = json.dumps({
                        "type": "phase.change",
                        "phase": phase,
                        "prev_phase": prev_phase,
                        "action": phase_action,
                    })
                    result_parts.append(f"data: {data}\n\n".encode())

            if _supervisor_text.strip():
                data = json.dumps({"type": "agent.trace", "node": "supervisor", "text": _supervisor_text.strip()})
                _supervisor_text = ""
                result_parts.append(f"data: {data}\n\n".encode())

            if result_parts:
                return b"".join(result_parts)
            return None
```

But `_map_event` returns `bytes | None`, not `list[bytes]`. Need to join them:

Make the return type `bytes | None` and join the parts:

```python
            if result_parts:
                return b"".join(result_parts)
            return None
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/api/agent_routes.py
git commit -m "feat: emit phase.change SSE event on workflow phase transition"
```

---

### Task 5: Create PhaseIndicator.vue

**Files:**
- Create: `web/src/components/agent/PhaseIndicator.vue`

- [ ] **Step 1: Write component**

```vue
<template>
  <div class="phase-indicator" v-if="phase">
    <div class="phase-bar">
      <template v-for="(p, i) in phases" :key="p.key">
        <div class="phase-step" :class="phaseClass(p.key)" @click="$emit('selectPhase', p.key)">
          <span class="phase-dot">{{ dotChar(p.key) }}</span>
          <span class="phase-label">{{ p.label }}</span>
        </div>
        <div v-if="i < phases.length - 1" class="phase-connector" :class="{ active: isDone(p.key) || isCurrent(p.key) }" />
      </template>
    </div>
    <div class="phase-hint">{{ currentLabel }} — {{ hintText }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ phase: string }>()
defineEmits<{ selectPhase: [key: string] }>()

const phases = [
  { key: 'define', label: 'Define', hint: '明确优化目标与基准' },
  { key: 'explore', label: 'Explore', hint: '探索数据与设计实验' },
  { key: 'analyze', label: 'Analyze', hint: '数据分析与建模' },
  { key: 'optimize', label: 'Optimize', hint: '参数推荐与优化' },
  { key: 'verify', label: 'Verify', hint: '验证与闭环控制' },
]

const phaseOrder = phases.map(p => p.key)
const currentIdx = computed(() => phaseOrder.indexOf(props.phase))

function isDone(key: string) { return phaseOrder.indexOf(key) < currentIdx.value }
function isCurrent(key: string) { return key === props.phase }

function phaseClass(key: string) {
  if (isDone(key)) return 'done'
  if (isCurrent(key)) return 'current'
  return 'pending'
}

function dotChar(key: string) {
  if (isDone(key)) return '✓'
  if (isCurrent(key)) return '●'
  return '○'
}

const currentLabel = computed(() => {
  const p = phases.find(p => p.key === props.phase)
  return p ? p.label : ''
})

const hintText = computed(() => {
  const p = phases.find(p => p.key === props.phase)
  return p ? p.hint : ''
})
</script>

<style scoped>
.phase-indicator {
  padding: 8px 14px 6px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-color-primary-light-9);
}
.phase-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}
.phase-step {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
  white-space: nowrap;
}
.phase-step:hover { background: var(--el-fill-color); }
.phase-dot { font-size: 10px; flex-shrink: 0; }
.phase-label { font-size: 11px; }
.phase-step.done .phase-dot { color: var(--el-color-success); }
.phase-step.done .phase-label { color: var(--el-color-success); }
.phase-step.current .phase-dot { color: var(--el-color-primary); animation: pulse 1.2s infinite; }
.phase-step.current .phase-label { color: var(--el-color-primary); font-weight: 600; }
.phase-step.pending .phase-dot { color: var(--el-text-color-placeholder); }
.phase-step.pending .phase-label { color: var(--el-text-color-placeholder); }
.phase-connector {
  width: 20px;
  height: 1px;
  background: var(--el-border-color);
  flex-shrink: 0;
  margin: 0 2px;
}
.phase-connector.active { background: var(--el-color-success); }
.phase-hint {
  text-align: center;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/agent/PhaseIndicator.vue
git commit -m "feat: add PhaseIndicator workflow progress bar component"
```

---

### Task 6: Integrate PhaseIndicator into ChatView + add workflow state

**Files:**
- Modify: `web/src/components/agent/ChatView.vue`
- Modify: `web/src/composables/useChatMessages.ts`
- Modify: `web/src/composables/useChatStream.ts`
- Modify: `web/src/api/agent.ts`

- [ ] **Step 1: Add workflowPhase to useChatMessages**

In `useChatMessages.ts`, add before the `return`:

```typescript
const workflowPhase = ref('')
```

And add `workflowPhase` to the return object:

```typescript
return { messages, suggestions, workflowPhase, addUserMessage, ... }
```

- [ ] **Step 2: Add onPhase to useChatStream**

In `useChatStream.ts`, add to the `sendAndStream` callbacks interface and pass through:

```typescript
async function sendAndStream(
    sessionId: string,
    text: string,
    callbacks: {
      onDelta: (delta: string) => void
      onToolCall: (name: string, args: any) => void
      onToolResult: (name: string, data: string, durationMs: number) => void
      onDone: () => void
      onError: (msg: string) => void
      onSuggestions: (questions: string[]) => void
      onTrace?: (node: string, text: string) => void
      onPhase?: (phase: string, prevPhase: string, action: string) => void
    },
  )
```

And in `agent.ts` SSE event handler, add:

```typescript
case 'phase.change':
    if (callbacks.onPhase) {
        callbacks.onPhase(event.phase, event.prev_phase || '', event.action || '')
    }
    break
```

- [ ] **Step 3: Wire PhaseIndicator into ChatView.vue**

Add import and component usage at the top of the template (after the messages div, before ChatInput):

```html
<PhaseIndicator v-if="workflowPhase" :phase="workflowPhase" />
```

Add import:

```typescript
import PhaseIndicator from './PhaseIndicator.vue'
```

Add phase handler in onSend / onUpload callbacks:

```typescript
const { messages, suggestions, workflowPhase, addUserMessage, ... } = useChatMessages()

// In makeCallbacks:
onPhase: (phase: string) => { workflowPhase.value = phase },
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/agent/ChatView.vue web/src/composables/useChatMessages.ts web/src/composables/useChatStream.ts web/src/api/agent.ts
git commit -m "feat: integrate PhaseIndicator with workflow phase state"
```

---

### Task 7: Add workflow shortcut button to ChatInput

**Files:**
- Modify: `web/src/components/agent/ChatInput.vue`

- [ ] **Step 1: Add shortcut button**

In the toolbar-left section, add a button before the upload button:

```html
<button class="tool-btn workflow-btn" title="工艺参数调优向导" @click="$emit('startWorkflow')">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.2L22 9.5l-5.7 4.8L17.8 22 12 18l-5.8 4 1.3-7.7L2 9.5l7.6-.3z"/></svg>
  <span class="tool-label">工艺调优</span>
</button>
```

Add the emit:

```typescript
const emit = defineEmits<{ send: [text: string]; upload: [file: File]; startWorkflow: [] }>()
```

Add CSS for the workflow button:

```css
.workflow-btn { color: var(--el-color-warning); }
.workflow-btn:hover { background: var(--el-color-warning-light-9); }
```

- [ ] **Step 2: Wire in ChatView.vue**

Add handler:

```html
<ChatInput :disabled="loading" @send="onSend" @upload="onUpload" @startWorkflow="onStartWorkflow" />
```

```typescript
function onStartWorkflow() {
  onSend('__start_workflow__')
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatInput.vue web/src/components/agent/ChatView.vue
git commit -m "feat: add workflow shortcut button to ChatInput toolbar"
```

---

### Task 8: Add graph.py session init for workflow fields

**Files:**
- Modify: `src/process_opt/agent/graph.py`

In `AgentSession.__init__`, initialize new workflow fields in `self.state`:

```python
self.state: dict = {
    "messages": [],
    "user_id": user_id,
    "process_type": process_type,
    "intent": "",
    "next": "supervisor",
    "mode": "chat",
    "phase": "",
    "goal": None,
    "baseline": None,
    "recommendation": None,
    "dataset_id": "",
    "experiment_plan_id": 0,
}
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/agent/graph.py
git commit -m "feat: initialize workflow fields in AgentSession state"
```
