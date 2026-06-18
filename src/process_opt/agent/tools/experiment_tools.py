from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


def create_experiment_tools(experiment_repo: Any) -> list:
    @tool
    async def list_experiment_plans(limit: int = 20) -> str:
        """列出所有实验方案。limit: 返回数量上限（默认20）。
        返回实验方案的名称、方法、状态、运行次数和创建时间。"""
        plans = await experiment_repo.list_plans(limit)

        if not plans:
            return "当前系统没有实验方案。"

        result = [f"## 实验方案列表 (共 {len(plans)} 个)", ""]
        result.append("| ID | 名称 | 工艺 | 方法 | 状态 | 创建者 | 创建时间 |")
        result.append("|----|------|------|------|------|--------|----------|")
        for p in plans:
            status_emoji = {
                "draft": "📝", "in_progress": "🔄",
                "completed": "✅", "archived": "📦",
            }.get(p.status, "")
            created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-"
            result.append(
                f"| {p.id} | {p.name} | {p.process_type} | "
                f"{p.method} | {status_emoji} {p.status} | "
                f"{p.created_by} | {created} |"
            )
        return "\n".join(result)

    return [list_experiment_plans]
