from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel
from typing import Literal

from process_opt.agent.state import AgentState


class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "TOOLS", "FINISH"]


def _has_pending_tool_calls(state: AgentState) -> bool:
    """Check if the most recent AI message has unexecuted tool calls.

    Scans messages in reverse — if we find a ToolMessage first, the tools
    have already been executed and we return False.
    """
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            return True
        if isinstance(msg, ToolMessage):
            return False  # tool already executed
        if isinstance(msg, AIMessage):
            return False  # AI response without tool calls
    return False


def _build_context(state: AgentState) -> str:
    """Build decision context for the supervisor including message history."""
    parts: list[str] = []

    # Count AI turns to detect excessive looping
    ai_turns = sum(
        1 for msg in state["messages"]
        if isinstance(msg, AIMessage)
    )
    parts.append(f"当前对话轮次: {ai_turns} (超过 3 轮应优先考虑 FINISH)")

    # Show the user's original question
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            parts.append(f"用户问题: {str(msg.content)[:300]}")
            break

    # Show recent activity (last 4 non-system messages)
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

    async def supervisor_node(state: AgentState) -> dict:
        # Automatic: if last AI message has pending tool calls, must route to tools
        if _has_pending_tool_calls(state):
            return {"next": "tools"}

        ctx = _build_context(state)

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
