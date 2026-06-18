from __future__ import annotations

from datetime import datetime

import pytest

from process_opt.agent.tools.experiment_tools import create_experiment_tools


class MockExperimentPlan:
    def __init__(self, id: int, name: str, method: str, status: str = "draft"):
        self.id = id
        self.name = name
        self.process_type = "adhesive_curing"
        self.method = method
        self.status = status
        self.created_by = "test"
        self.created_at = datetime(2026, 6, 1, 10, 0)


class MockExperimentRepo:
    def __init__(self) -> None:
        self._plans = [
            MockExperimentPlan(1, "全因子实验", "full_factorial", "completed"),
            MockExperimentPlan(2, "田口设计", "taguchi", "in_progress"),
            MockExperimentPlan(3, "响应面优化", "central_composite", "draft"),
        ]

    async def list_plans(self, limit: int = 20) -> list[MockExperimentPlan]:
        return self._plans[:limit]


@pytest.fixture
def tools() -> list:
    return create_experiment_tools(MockExperimentRepo())


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_experiment_plans_all(tools: list) -> None:
    result = await _find_tool(tools, "list_experiment_plans").ainvoke({"limit": 20})
    assert "全因子实验" in result
    assert "田口设计" in result
    assert "响应面优化" in result
    assert "full_factorial" in result


@pytest.mark.asyncio
async def test_list_experiment_plans_limited(tools: list) -> None:
    result = await _find_tool(tools, "list_experiment_plans").ainvoke({"limit": 1})
    assert "全因子实验" in result
    assert "田口设计" not in result
