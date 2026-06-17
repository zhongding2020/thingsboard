from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_recommender_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def recommender_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""
        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺参数推荐专家。\n\n"
                f"{knowledge_prompt}\n\n"
                "任务: 1.build_dataset构建数据集 2.run_regression分析 3.recommend_params推荐 4.结合规则过滤 5.用表格呈现"
            )
        )
        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return recommender_node
