from __future__ import annotations

import pytest

from process_opt.agent.tools.system_tools import create_system_tools


class MockLineDeviceRepo:
    def __init__(self) -> None:
        self._lines = [
            {"id": "L1", "name": "产线A", "responsible": "张三", "location": "一楼", "device_count": 2},
            {"id": "L2", "name": "产线B", "responsible": "李四", "location": "二楼", "device_count": 1},
        ]
        self._devices = [
            {"id": "D1", "name": "注塑机1", "type": "injection_molding", "line_name": "产线A", "line_id": "L1", "description": "主注塑机"},
            {"id": "D2", "name": "检测站1", "type": "inspection", "line_name": "产线A", "line_id": "L1", "description": "QA检测"},
            {"id": "D3", "name": "固化炉1", "type": "adhesive_curing", "line_name": "产线B", "line_id": "L2", "description": ""},
        ]

    async def list_lines(self) -> list[dict]:
        return self._lines

    async def get_line(self, line_id: str) -> dict | None:
        for line in self._lines:
            if line["id"] == line_id:
                return line
        return None

    async def list_devices(self, line_id: str | None = None) -> list[dict]:
        if line_id is None:
            return self._devices
        return [d for d in self._devices if d.get("line_id") == line_id]

    async def get_device(self, device_id: str) -> dict | None:
        for d in self._devices:
            if d["id"] == device_id:
                return d
        return None


@pytest.fixture
def tools() -> list:
    repo = MockLineDeviceRepo()
    return create_system_tools(repo, analysis_service=None)


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_production_lines(tools: list) -> None:
    tool = _find_tool(tools, "list_production_lines")
    result = await tool.ainvoke({})
    assert "产线A" in result
    assert "产线B" in result
    assert "张三" in result


@pytest.mark.asyncio
async def test_get_production_line_found(tools: list) -> None:
    tool = _find_tool(tools, "get_production_line")
    result = await tool.ainvoke({"line_id": "L1"})
    assert "产线A" in result
    assert "注塑机1" in result


@pytest.mark.asyncio
async def test_get_production_line_not_found(tools: list) -> None:
    tool = _find_tool(tools, "get_production_line")
    result = await tool.ainvoke({"line_id": "L99"})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_list_registered_devices_all(tools: list) -> None:
    tool = _find_tool(tools, "list_registered_devices")
    result = await tool.ainvoke({"line_id": ""})
    assert "注塑机1" in result
    assert "固化炉1" in result


@pytest.mark.asyncio
async def test_list_registered_devices_filtered(tools: list) -> None:
    tool = _find_tool(tools, "list_registered_devices")
    result = await tool.ainvoke({"line_id": "L2"})
    assert "固化炉1" in result
    assert "注塑机1" not in result


@pytest.mark.asyncio
async def test_get_registered_device_found(tools: list) -> None:
    tool = _find_tool(tools, "get_registered_device")
    result = await tool.ainvoke({"device_id": "D1"})
    assert "注塑机1" in result
    assert "injection_molding" in result


@pytest.mark.asyncio
async def test_get_registered_device_not_found(tools: list) -> None:
    tool = _find_tool(tools, "get_registered_device")
    result = await tool.ainvoke({"device_id": "D99"})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_monitor_no_analysis_service(tools: list) -> None:
    tool = _find_tool(tools, "monitor_production_line")
    result = await tool.ainvoke({"line_id": "L1"})
    assert "不可用" in result
