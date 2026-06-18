from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


ROLE_PROMPTS = {
    "chat": {
        "title": "工艺参数分析助手",
        "instructions": "用中文回答，使用 Markdown 格式。数据分析结果用表格呈现。",
    },
    "analyzer": {
        "title": "工艺数据分析专家",
        "instructions": "任务: 1.选择合适分析工具 2.调用工具获取结果 3.用中文解读 4.用表格呈现 5.不输出原始JSON",
    },
    "recommender": {
        "title": "工艺参数推荐专家",
        "instructions": "任务: 1.build_dataset构建数据集 2.run_regression分析 3.recommend_params推荐 4.结合规则过滤 5.用表格呈现",
    },
}


def create_worker_node(role: str, llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    if role not in ROLE_PROMPTS:
        raise ValueError(f"Unknown role: {role}. Valid: {list(ROLE_PROMPTS.keys())}")

    role_cfg = ROLE_PROMPTS[role]

    async def worker_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""
        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}{role_cfg['title']}。\n\n"
                f"{knowledge_prompt}\n\n"
                f"{role_cfg['instructions']}"
            )
        )
        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return worker_node
