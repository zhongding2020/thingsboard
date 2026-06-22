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

PHASE_HINTS = {
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
        parts.append(f"当前阶段: {phase} ({PHASE_HINTS.get(phase, '')})")
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

        mode = state.get("mode", "chat")
        phase = state.get("phase", "")

        # Detect workflow mode entry
        if mode != "workflow":
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    if _detect_workflow_intent(str(msg.content)):
                        return {"next": "analyzer", "mode": "workflow", "phase": "define"}
                    break

        ctx = _build_context(state)

        if mode == "workflow" and phase:
            phase_prompt = (
                f"当前处于工艺调优工作流「{phase}」阶段。\n"
                f"阶段说明: {PHASE_HINTS.get(phase, '')}\n\n"
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

        # Chat mode routing
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
