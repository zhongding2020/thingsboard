from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from typing import Literal

from process_opt.agent.state import AgentState


class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "FINISH"]


def create_supervisor_node(llm: BaseChatModel):
    structured_llm = llm.with_structured_output(SupervisorDecision, method="function_calling")

    async def supervisor_node(state: AgentState) -> dict:
        last_human = None
        last_assistant = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and last_human is None:
                last_human = msg
            elif hasattr(msg, "type") and msg.type == "ai" and last_assistant is None:
                last_assistant = msg

        ctx = ""
        if last_human:
            ctx += f"用户消息: {last_human.content}\n"
        if last_assistant:
            content = last_assistant.content
            if isinstance(content, list):
                content = " ".join(
                    t.get("text", "") if isinstance(t, dict) else str(t)
                    for t in content
                )
            ctx += f"助手已回复: {str(content)[:200]}\n"

        prompt = (
            "根据对话状态输出下一个处理节点。\n\n"
            "- CHAT: 通用问答、工艺咨询\n"
            "- ANALYZER: 数据分析（SPC、相关性、回归等）\n"
            "- RECOMMENDER: 参数推荐或优化\n"
            "- FINISH: 本轮对话已完成，助手已给出实质性回答\n\n"
            f"{ctx}"
        )

        result: SupervisorDecision = await structured_llm.ainvoke([SystemMessage(content=prompt)])
        intent = result.intent.upper()
        if intent == "FINISH":
            return {"next": "FINISH"}
        return {"next": intent.lower()}

    return supervisor_node
