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
    # Always include ask_user for interactive prompts
    all_tool_names.add("ask_user")

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

当需要用户提供信息（选择产线、设备、参数、确认操作等）时，**必须使用 `ask_user` 工具**，不要直接在文本中提问。`ask_user` 会在前端渲染为下拉框、多选、确认按钮等交互组件。

### 何时使用 ask_user

- 需要用户选择产线或设备 → type="cascader" 或 type="select"
- 需要用户勾选要分析的参数 → type="multi_select"
- 需要用户确认操作（如提交参数集）→ type="confirm"
- 需要用户输入具体数值 → type="input"

### 使用示例

选择产线：
```
ask_user(type="select", title="请选择要分析的产线", options='[{"label":"注塑A线","value":"L1"},{"label":"注塑B线","value":"L2"}]')
```

多选参数：
```
ask_user(type="multi_select", title="请选择要分析的参数", options='[{"label":"固化温度","value":"cure_temp"},{"label":"固化时间","value":"cure_time"}]')
```

确认操作：
```
ask_user(type="confirm", title="确认提交此参数集？", confirm_text="确认提交", cancel_text="取消")
```

**重要：调用 ask_user 后，停止当前回复，等待用户在交互组件中的操作结果。**
"""
    full_system_prompt = process_skill["system_prompt"] + interactive_instructions

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=full_system_prompt,
    )
    return agent
