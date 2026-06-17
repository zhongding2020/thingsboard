from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from process_opt.agent.state import AgentState

WORKERS = ["chat", "analyzer", "recommender"]


def create_supervisor_node(llm: BaseChatModel):
    async def supervisor_node(state: AgentState) -> dict:
        messages = [
            SystemMessage(
                content=(
                    "你是一个路由节点，负责根据用户的意图将请求分发到合适的 Worker。\n\n"
                    "可用 Worker:\n"
                    "- chat: 通用问答、工艺咨询\n"
                    "- analyzer: 数据分析\n"
                    "- recommender: 参数推荐和优化\n"
                    "- FINISH: 对话结束\n\n"
                    "只输出 Worker 名称。\n"
                    "Worker: chat, analyzer, recommender, FINISH"
                )
            ),
        ]
        last_msg = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_msg = msg
                break
        if last_msg:
            messages.append(last_msg)
        response = await llm.ainvoke(messages)
        text = (response.content or "").strip()
        for worker in WORKERS:
            if worker in text:
                return {"next": worker}
        return {"next": "FINISH"}

    return supervisor_node
