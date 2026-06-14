import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.common.errors import PublishError
from process_opt.common.settings import Settings
from process_opt.gateway.app import create_app


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, object]]] = []

    async def publish(self, subject: str, payload: dict[str, object]) -> None:
        self.published.append((subject, payload))


class FailingPublisher:
    async def publish(self, subject: str, payload: dict[str, object]) -> None:
        raise PublishError


@pytest.mark.asyncio
async def test_process_endpoint_publishes_and_returns_202() -> None:
    settings = Settings()
    publisher = FakePublisher()
    app = create_app(settings, publisher)
    payload = {
        "message_id": "m1",
        "barcode": "B1",
        "device_id": "D1",
        "processed_at": "2026-06-08T10:00:00Z",
        "params": {"temperature": 180},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data/process", json=payload, headers={"X-API-Key": settings.gateway_api_key})

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert len(publisher.published) == 1
    assert publisher.published[0][0] == settings.process_subject
    assert publisher.published[0][1]["barcode"] == "B1"
    assert publisher.published[0][1]["product_model"] == ""


@pytest.mark.asyncio
async def test_inspection_endpoint_publishes_and_returns_202() -> None:
    settings = Settings()
    publisher = FakePublisher()
    app = create_app(settings, publisher)
    payload = {
        "message_id": "m2",
        "barcode": "B1",
        "station_id": "QA1",
        "inspected_at": "2026-06-08T10:05:00Z",
        "results": [{"name": "diameter", "value": 10.2, "result": "pass", "unit": "", "usl": None, "lsl": None}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data/inspection", json=payload, headers={"X-API-Key": settings.gateway_api_key})

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert len(publisher.published) == 1
    assert publisher.published[0][0] == settings.inspection_subject
    assert publisher.published[0][1]["barcode"] == "B1"
    assert publisher.published[0][1]["product_model"] == ""
    assert publisher.published[0][1]["results"] == payload["results"]


@pytest.mark.asyncio
async def test_missing_api_key_returns_401() -> None:
    settings = Settings()
    publisher = FakePublisher()
    app = create_app(settings, publisher)
    payload = {
        "message_id": "m1",
        "barcode": "B1",
        "device_id": "D1",
        "processed_at": "2026-06-08T10:00:00Z",
        "params": {"temperature": 180},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data/process", json=payload)

    assert response.status_code == 401
    assert publisher.published == []


@pytest.mark.asyncio
async def test_invalid_payload_returns_422() -> None:
    settings = Settings()
    publisher = FakePublisher()
    app = create_app(settings, publisher)
    payload = {
        "message_id": "m1",
        "barcode": "B1",
        "device_id": "D1",
        "processed_at": "2026-06-08T10:00:00Z",
        "params": {},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data/process", json=payload, headers={"X-API-Key": settings.gateway_api_key})

    assert response.status_code == 422
    assert publisher.published == []


@pytest.mark.asyncio
async def test_publish_failure_returns_503() -> None:
    settings = Settings()
    app = create_app(settings, FailingPublisher())
    payload = {
        "message_id": "m1",
        "barcode": "B1",
        "device_id": "D1",
        "processed_at": "2026-06-08T10:00:00Z",
        "params": {"temperature": 180},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data/process", json=payload, headers={"X-API-Key": settings.gateway_api_key})

    assert response.status_code == 503
