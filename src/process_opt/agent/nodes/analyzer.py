from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_analyzer_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def analyzer_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""
        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺数据分析专家。\n\n"
                f"{knowledge_prompt}\n\n"
                "任务: 1.选择合适分析工具 2.调用工具获取结果 3.用中文解读 4.用表格呈现 5.不输出原始JSON"
            )
        )
        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return analyzer_node
