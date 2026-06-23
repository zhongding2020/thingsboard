import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.app import create_app
from process_opt.mock.manager import MockManager


@pytest.fixture
def mock_manager():
    return MockManager(
        api_url="http://test-api:8000",
        gateway_url="http://test-gw:8001",
        api_key="test-key",
    )


@pytest.fixture
def app_with_mock(mock_manager):
    return create_app(mock_manager=mock_manager)


# ---- Create / List / Get / Delete ----


@pytest.mark.asyncio
async def test_create_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        r = await client.post("/api/v1/mock/devices", json={
            "device_id": "reflow-oven-001",
            "device_type": "reflow-oven",
            "name": "回流焊1号",
            "line_id": "L1",
            "report_interval": 60,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["device_id"] == "reflow-oven-001"
        assert data["status"] == "idle"


@pytest.mark.asyncio
async def test_list_devices(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d2", "device_type": "cnc-drill", "name": "B", "line_id": "L2",
        })
        r = await client.get("/api/v1/mock/devices")
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["idle"] == 2
        assert len(data["devices"]) == 2


@pytest.mark.asyncio
async def test_get_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        r = await client.get("/api/v1/mock/devices/d1")
        assert r.status_code == 200
        assert r.json()["name"] == "A"


@pytest.mark.asyncio
async def test_get_device_404(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        r = await client.get("/api/v1/mock/devices/nonexistent")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        r = await client.delete("/api/v1/mock/devices/d1")
        assert r.status_code == 200
        r2 = await client.get("/api/v1/mock/devices/d1")
        assert r2.status_code == 404


# ---- Start / Pause / Stop ----


@pytest.mark.asyncio
async def test_start_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        r = await client.post("/api/v1/mock/devices/d1/start")
        assert r.status_code == 200
        assert r.json()["status"] == "running"


@pytest.mark.asyncio
async def test_start_nonexistent_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        r = await client.post("/api/v1/mock/devices/nope/start")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_pause_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        await client.post("/api/v1/mock/devices/d1/start")
        r = await client.post("/api/v1/mock/devices/d1/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_stop_device(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        await client.post("/api/v1/mock/devices/d1/start")
        r = await client.post("/api/v1/mock/devices/d1/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"


# ---- Configure / Experiment ----


@pytest.mark.asyncio
async def test_configure_params(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        r = await client.put("/api/v1/mock/devices/d1/params", json={
            "temperature": 250, "conveyor_speed": 55, "oxygen_ppm": 150,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["current_params"]["temperature"] == 250


@pytest.mark.asyncio
async def test_enqueue_experiment(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        })
        r = await client.post("/api/v1/mock/devices/d1/experiments", json={"plan_id": 3})
        assert r.status_code == 202
        assert r.json()["plan_id"] == 3
        assert r.json()["status"] == "queued"


# ---- Validation ----


@pytest.mark.asyncio
async def test_create_device_missing_required_fields(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        r = await client.post("/api/v1/mock/devices", json={"name": "test"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_report_interval(app_with_mock):
    async with AsyncClient(transport=ASGITransport(app=app_with_mock), base_url="http://test") as client:
        r = await client.post("/api/v1/mock/devices", json={
            "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
            "report_interval": 0,
        })
        assert r.status_code == 422
