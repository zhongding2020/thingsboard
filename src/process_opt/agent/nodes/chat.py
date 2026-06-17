from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_chat_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def chat_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""
        system_message = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺参数分析助手。\n\n"
                f"{knowledge_prompt}\n\n"
                "用中文回答，使用 Markdown 格式。数据分析结果用表格呈现。"
            )
        )
        messages = [system_message] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return chat_node
