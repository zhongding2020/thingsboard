"""Skills system — Markdown-based process and capability skills.

Directory layout:
    skills/
    ├── process/        # type=process skills (session-level, loaded at creation)
    ├── capabilities/   # type=capability skills (on-demand, triggered by LLM)
    └── __init__.py     # This file
"""

from __future__ import annotations

import yaml
from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def _parse_skill_md(path: Path) -> dict:
    """Parse a Markdown skill file: YAML frontmatter + Markdown body.

    The body becomes the ``system_prompt`` field — no programmatic assembly.
    """
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta: dict = yaml.safe_load(fm)
    meta["system_prompt"] = body.strip()
    return meta


def discover_skills() -> dict[str, dict]:
    """Recursively scan the skills/ directory for ``*.md`` files.

    Returns a dict keyed by skill ``name`` (from frontmatter).
    Duplicate names: last file wins (undefined order — don't duplicate).
    """
    registry: dict[str, dict] = {}
    for md_file in SKILLS_DIR.rglob("*.md"):
        skill = _parse_skill_md(md_file)
        registry[skill["name"]] = skill
    return registry


def get_process_skills(registry: dict) -> list[dict]:
    """Return all skills with ``type: process``."""
    return [s for s in registry.values() if s.get("type") == "process"]


def get_capability_skills(registry: dict) -> list[dict]:
    """Return all skills with ``type: capability``."""
    return [s for s in registry.values() if s.get("type") == "capability"]
