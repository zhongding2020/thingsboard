from __future__ import annotations

import pytest

from process_opt.agent.tools.parameter_tools import create_parameter_tools


class MockParameterSet:
    def __init__(self, id: int, name: str, device_type: str, version: int, status: str):
        self.id = id
        self.name = name
        self.device_type = device_type
        self.version = version
        self.status = status
        self.created_by = "test"
        self.note = None
        self.activated_at = None


class MockParameterItem:
    def __init__(self, param_key: str, param_value, unit: str = "", data_type: str = "continuous"):
        self.param_key = param_key
        self.param_value = param_value
        self.unit = unit
        self.data_type = data_type
        self.min_value = None
        self.max_value = None


class MockParameterSetWithItems:
    def __init__(self, parameter_set: MockParameterSet, items: list[MockParameterItem]):
        self.parameter_set = parameter_set
        self.items = items


class MockParameterService:
    def __init__(self) -> None:
        self._sets = [
            MockParameterSet(1, "默认参数", "adhesive_curing", 1, "active"),
            MockParameterSet(2, "优化参数v2", "adhesive_curing", 2, "proposed"),
            MockParameterSet(3, "注塑标准", "injection_molding", 1, "draft"),
        ]
        self._items = {
            1: [MockParameterItem("cure_temp", 145, "°C"), MockParameterItem("cure_time", 45, "min")],
            2: [MockParameterItem("cure_temp", 150, "°C"), MockParameterItem("cure_time", 40, "min")],
            3: [MockParameterItem("melt_temp", 220, "°C")],
        }

    async def list_sets(self) -> list[MockParameterSet]:
        return self._sets

    async def get_set_with_items(self, set_id: int) -> MockParameterSetWithItems | None:
        for s in self._sets:
            if s.id == set_id:
                return MockParameterSetWithItems(s, self._items.get(set_id, []))
        return None

    async def get_latest(self, device_type: str) -> MockParameterSetWithItems | None:
        for s in self._sets:
            if s.device_type == device_type and s.status == "active":
                return MockParameterSetWithItems(s, self._items.get(s.id, []))
        return None

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "draft":
                    raise ValueError(f"Cannot submit set in status {s.status}")
                s.status = "proposed"
                return s
        raise ValueError(f"Set {set_id} not found")

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "proposed":
                    raise ValueError(f"Cannot approve set in status {s.status}")
                s.status = "approved"
                return s
        raise ValueError(f"Set {set_id} not found")

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "proposed":
                    raise ValueError(f"Cannot reject set in status {s.status}")
                s.status = "rejected"
                return s
        raise ValueError(f"Set {set_id} not found")


@pytest.fixture
def tools() -> list:
    return create_parameter_tools(MockParameterService())


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_parameter_sets_all(tools: list) -> None:
    result = await _find_tool(tools, "list_parameter_sets").ainvoke({"device_type": ""})
    assert "默认参数" in result
    assert "优化参数v2" in result
    assert "注塑标准" in result


@pytest.mark.asyncio
async def test_list_parameter_sets_filtered(tools: list) -> None:
    result = await _find_tool(tools, "list_parameter_sets").ainvoke({"device_type": "adhesive_curing"})
    assert "默认参数" in result
    assert "优化参数v2" in result
    assert "注塑标准" not in result


@pytest.mark.asyncio
async def test_get_parameter_set_found(tools: list) -> None:
    result = await _find_tool(tools, "get_parameter_set").ainvoke({"set_id": 1})
    assert "默认参数" in result
    assert "cure_temp" in result
    assert "145" in result


@pytest.mark.asyncio
async def test_get_parameter_set_not_found(tools: list) -> None:
    result = await _find_tool(tools, "get_parameter_set").ainvoke({"set_id": 99})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_get_latest_active(tools: list) -> None:
    result = await _find_tool(tools, "get_latest_active_parameters").ainvoke({"device_type": "adhesive_curing"})
    assert "默认参数" in result
    assert "cure_temp" in result


@pytest.mark.asyncio
async def test_get_latest_no_active(tools: list) -> None:
    result = await _find_tool(tools, "get_latest_active_parameters").ainvoke({"device_type": "welding"})
    assert "没有激活" in result


@pytest.mark.asyncio
async def test_submit_success(tools: list) -> None:
    result = await _find_tool(tools, "submit_parameter_set").ainvoke({"set_id": 3, "note": "请审批"})
    assert "已提交审批" in result


@pytest.mark.asyncio
async def test_submit_wrong_status(tools: list) -> None:
    result = await _find_tool(tools, "submit_parameter_set").ainvoke({"set_id": 1, "note": ""})
    assert "失败" in result


@pytest.mark.asyncio
async def test_approve_success(tools: list) -> None:
    result = await _find_tool(tools, "approve_parameter_set").ainvoke({"set_id": 2, "note": "同意"})
    assert "已批准" in result


@pytest.mark.asyncio
async def test_reject_success(tools: list) -> None:
    result = await _find_tool(tools, "reject_parameter_set").ainvoke({"set_id": 2, "note": "温度需调整"})
    assert "已驳回" in result
    assert "温度需调整" in result
