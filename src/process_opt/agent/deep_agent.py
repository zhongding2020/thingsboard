"""DeepAgent factory — one-line agent creation replacing StateGraph + Supervisor + 3 Workers."""

from __future__ import annotations

import logging
from typing import Any

from process_opt.agent.skills import (
    discover_skills,
    get_capability_skills,
)

logger = logging.getLogger(__name__)

# Global: scanned once at import time — all .md files under skills/
SKILL_REGISTRY: dict[str, dict] = discover_skills()

# Lazy imports — deepagents is imported at call time so tests can mock without it installed
create_deep_agent: Any = None  # set on first call


async def create_process_agent(
    llm: Any,
    process_type: str,
    tool_pool: dict[str, Any],
) -> Any:
    """Create a DeepAgent configured for a specific process type.

    Args:
        llm: Chat model instance (e.g., ChatOpenAI).
        process_type: Key into SKILL_REGISTRY (e.g., ``"adhesive_curing"``).
        tool_pool: Dict mapping tool name → callable (from main.py wiring).

    Returns:
        A DeepAgent ready for ``astream_events()`` or ``ainvoke()``.

    Raises:
        ValueError: If ``process_type`` is not in the skill registry.
    """
    # 1. Get process skill — its Markdown body IS the system prompt
    process_skill = SKILL_REGISTRY.get(process_type)
    if not process_skill:
        available = [s["name"] for s in SKILL_REGISTRY.values() if s.get("type") == "process"]
        raise ValueError(
            f"Unknown process type: {process_type}. "
            f"Available: {', '.join(available)}"
        )

    # 2. Get all capability skills (on-demand, triggered by LLM intent matching)
    capability_skills = get_capability_skills(SKILL_REGISTRY)

    # 3. Merge tool names from process skill + all capability skills
    all_tool_names: set[str] = set(process_skill.get("tools", []))
    for cap in capability_skills:
        all_tool_names.update(cap.get("tools", []))
    # Always include core infrastructure tools
    all_tool_names.add("ask_user")
    all_tool_names.add("list_mock_devices")
    all_tool_names.add("assign_experiment")
    all_tool_names.add("get_experiment_results")
    all_tool_names.add("get_plan_results")
    all_tool_names.add("save_experiment_plan")
    all_tool_names.add("list_experiment_plans")

    tools = [tool_pool[name] for name in all_tool_names if name in tool_pool]
    missing = all_tool_names - set(tool_pool.keys())
    if missing:
        logger.warning("Skill tools not in pool: %s", missing)

    # 4. Lazy-load deepagents (deferred import for testability)
    global create_deep_agent
    if create_deep_agent is None:
        from deepagents import create_deep_agent as _create_deep_agent  # type: ignore[no-redef]
        create_deep_agent = _create_deep_agent

    # 5. Create DeepAgent with defaults
    # DeepAgents 0.6+ includes built-in middleware (Filesystem, Summarization,
    # Todo management, Subagent spawning) — no need to add duplicates.
    #
    # Augment system prompt with interactive prompt usage instructions
    interactive_instructions = """
## 与用户交互的方式

当需要用户提供信息时，**必须使用 `ask_user` 工具**，不要在文本中提问。前端会渲染为对应的交互组件。

### 如何选择 type

- 需要用户从已知列表中**选择**产线/设备/参数 → 先调用对应的 list/get 工具获取数据，再用 type="select" 或 type="multi_select"
- 需要用户**自由输入**文本（如目标指标名称、目标值、备注等）→ type="input"
- 需要用户**确认**操作 → type="confirm"
- 需要**级联选择**（如先选产线再选设备）→ type="cascader"

### 使用示例

自由输入（无预设选项时使用）：
```
ask_user(type="input", title="请输入目标质量指标 (Y) 的名称", placeholder="例如 shear_strength")
```

下拉选择（有明确选项时使用）：
```
ask_user(type="select", title="请选择要分析的产线", options='[{"label":"注塑A线","value":"L1"}]')
```

多选勾选：
```
ask_user(type="multi_select", title="请选择要分析的参数", options='[{"label":"固化温度","value":"cure_temp"}]')
```

确认操作：
```
ask_user(type="confirm", title="确认提交此参数集？", confirm_text="确认提交", cancel_text="取消")
```

**重要：调用 ask_user 后，停止当前回复，等待用户操作结果。**
"""
    full_system_prompt = process_skill["system_prompt"] + interactive_instructions
    full_system_prompt = process_skill["system_prompt"] + interactive_instructions

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=full_system_prompt,
    )
    return agent
