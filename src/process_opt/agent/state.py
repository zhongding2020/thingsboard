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
