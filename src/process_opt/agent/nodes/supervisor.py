from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from process_opt.agent.state import AgentState

ROUTES = ["chat", "analyzer", "recommender", "tools"]


def create_supervisor_node(llm: BaseChatModel):
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
            "根据对话状态输出下一个处理节点名称。\n\n"
            "可选节点:\n"
            "- chat: 通用问答、工艺咨询\n"
            "- analyzer: 数据分析（SPC、相关性、回归等）\n"
            "- recommender: 参数推荐或优化\n"
            "- FINISH: 本轮对话已完成\n\n"
            "规则:\n"
            "- 如果助手已经对用户问题给出了实质性回答，输出 FINISH\n"
            "- 如果没有助手回复，根据用户意图选择合适的节点\n\n"
            f"{ctx}\n"
            "只输出节点名称: chat, analyzer, recommender, FINISH"
        )

        response = await llm.ainvoke([SystemMessage(content=prompt)])
        text = (response.content or "").strip()

        for route in ["chat", "analyzer", "recommender"]:
            if route in text:
                return {"next": route}
        return {"next": "FINISH"}

    return supervisor_node
