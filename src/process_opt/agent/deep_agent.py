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
FilesystemMiddleware: Any = None
SummarizationMiddleware: Any = None


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

    tools = [tool_pool[name] for name in all_tool_names if name in tool_pool]
    missing = all_tool_names - set(tool_pool.keys())
    if missing:
        logger.warning("Skill tools not in pool: %s", missing)

    # 4. Lazy-load deepagents (deferred import for testability)
    global create_deep_agent, FilesystemMiddleware, SummarizationMiddleware
    if create_deep_agent is None:
        from deepagents import create_deep_agent as _create_deep_agent  # type: ignore[no-redef]
        from deepagents.middleware import (  # type: ignore[import-untyped]
            FilesystemMiddleware as _FilesystemMiddleware,
            SummarizationMiddleware as _SummarizationMiddleware,
        )
        create_deep_agent = _create_deep_agent
        FilesystemMiddleware = _FilesystemMiddleware
        SummarizationMiddleware = _SummarizationMiddleware

    # 5. Assemble middleware stack
    # DeepAgents 0.6+ has built-in todo management and subagent spawning.
    # FilesystemMiddleware provides file operations for large result eviction.
    # SummarizationMiddleware auto-compresses long conversations.
    middleware: list[Any] = [
        FilesystemMiddleware(),
        SummarizationMiddleware(model=llm),
    ]

    # 6. Create DeepAgent
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=process_skill["system_prompt"],  # Markdown body
        middleware=middleware,
    )
    return agent
