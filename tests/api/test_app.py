from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.app import create_app


class FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {
            "B1": {
                "barcode": "B1",
                "device_id": "D1",
                "processed_at": datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
                "params": {"temperature": 180},
                "process_product_model": "Model-A",
                "station_id": "QA1",
                "inspected_at": datetime(2026, 6, 8, 10, 5, tzinfo=UTC),
                "results": {"diameter": 10.2},
                "inspection_product_model": "Model-A",
            }
        }
        self.requested_barcodes: list[str] = []

    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None:
        self.requested_barcodes.append(barcode)
        return self.records.get(barcode)

    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        product_model: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        items = list(self.records.values())
        if barcode:
            items = [r for r in items if r["barcode"] == barcode]
        if device_id:
            items = [r for r in items if r["device_id"] == device_id]
        if start_time:
            items = [r for r in items if r["processed_at"] >= start_time]
        if end_time:
            items = [r for r in items if r["processed_at"] <= end_time]
        if product_model:
            items = [r for r in items if r.get("process_product_model") == product_model or r.get("inspection_product_model") == product_model]
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {"items": items[start:end], "total": total, "page": page, "page_size": page_size}

    async def list_devices(self) -> list[str]:
        return sorted(set(r["device_id"] for r in self.records.values()))

    async def get_stats(self) -> dict[str, Any]:
        return {
            "today_data_count": 1,
            "total_records": len(self.records),
            "device_count": len(set(r["device_id"] for r in self.records.values())),
            "pending_approvals": 0,
            "latest_records": [],
        }


@pytest.mark.asyncio
async def test_get_analysis_record_by_barcode_returns_joined_data() -> None:
    repository = FakeRepository()
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/records/B1")

    assert response.status_code == 200
    assert response.json() == {
        "barcode": "B1",
        "device_id": "D1",
        "processed_at": "2026-06-08T10:00:00+00:00",
        "params": {"temperature": 180},
        "process_product_model": "Model-A",
        "station_id": "QA1",
        "inspected_at": "2026-06-08T10:05:00+00:00",
        "results": {"diameter": 10.2},
        "inspection_product_model": "Model-A",
    }
    assert repository.requested_barcodes == ["B1"]


@pytest.mark.asyncio
async def test_query_records_returns_paginated_list() -> None:
    app = create_app(FakeRepository())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/records")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["barcode"] == "B1"
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_query_records_filters_by_parameters() -> None:
    repository = FakeRepository()
    repository.records["B2"] = {
        "barcode": "B2",
        "device_id": "injection-molder",
        "processed_at": datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        "params": {"pressure": 150},
        "process_product_model": "",
        "station_id": None,
        "inspected_at": None,
        "results": None,
        "inspection_product_model": "",
    }
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Filter by device
        r = await client.get("/api/v1/analysis/records", params={"device_id": "injection-molder"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["device_id"] == "injection-molder"

        # Filter by barcode
        r = await client.get("/api/v1/analysis/records", params={"barcode": "B1"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

        # Filter by time range
        r = await client.get(
            "/api/v1/analysis/records",
            params={
                "start_time": "2026-06-09T00:00:00Z",
                "end_time": "2026-06-09T23:59:59Z",
            },
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

        # Pagination
        r = await client.get("/api/v1/analysis/records", params={"page": 1, "page_size": 1})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1
        assert r.json()["total"] == 2

        # No match
        r = await client.get("/api/v1/analysis/records", params={"barcode": "NONEXIST"})
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_devices_returns_device_ids() -> None:
    repository = FakeRepository()
    repository.records["B2"] = {
        "barcode": "B2",
        "device_id": "injection-molder",
        "processed_at": datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        "params": {"pressure": 150},
        "process_product_model": "",
        "station_id": None,
        "inspected_at": None,
        "results": None,
        "inspection_product_model": "",
    }
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/devices")

    assert response.status_code == 200
    assert response.json() == ["D1", "injection-molder"]


@pytest.mark.asyncio
async def test_get_unknown_barcode_returns_404() -> None:
    repository = FakeRepository()
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/records/UNKNOWN")

    assert response.status_code == 404
    assert repository.requested_barcodes == ["UNKNOWN"]


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    app = create_app(FakeRepository())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


import json as _json_mod


@pytest.mark.asyncio
async def test_ask_user_emits_interactive_prompt_not_tool_call() -> None:
    """Verify ask_user tool start emits interactive.prompt, not tool.call."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_start",
        "name": "ask_user",
        "run_id": "run-123",
        "data": {
            "input": {
                "type": "select",
                "title": "请选择产线",
                "options": '[{"label":"A线","value":"L1"}]',
            }
        },
    }
    result = _map_event(event, set())
    assert result is not None
    decoded = _json_mod.loads(result.decode().lstrip("data: "))
    assert decoded["type"] == "interactive.prompt"
    assert decoded["action"]["type"] == "select"
    assert decoded["action"]["title"] == "请选择产线"
    assert "id" in decoded["action"]


@pytest.mark.asyncio
async def test_ask_user_tool_end_is_skipped() -> None:
    """Verify ask_user tool_end produces no SSE output."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_end",
        "name": "ask_user",
        "run_id": "run-123",
        "data": {"output": "..."},
    }
    result = _map_event(event, set())
    assert result is None


@pytest.mark.asyncio
async def test_normal_tool_call_still_works() -> None:
    """Verify non-ask_user tools still emit tool.call."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_start",
        "name": "list_production_lines",
        "run_id": "run-456",
        "data": {"input": {}},
    }
    result = _map_event(event, set())
    assert result is not None
    decoded = _json_mod.loads(result.decode().lstrip("data: "))
    assert decoded["type"] == "tool.call"
    assert decoded["name"] == "list_production_lines"


