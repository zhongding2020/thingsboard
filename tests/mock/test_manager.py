import asyncio

import pytest

from process_opt.mock.manager import MockManager, DeviceConfig


@pytest.fixture
def manager():
    return MockManager(
        api_url="http://test-api:8000",
        gateway_url="http://test-gw:8001",
        api_key="test-key",
    )


# ---- Create, List, Get ----

@pytest.mark.asyncio
async def test_create_device_idle(manager):
    cfg = DeviceConfig(
        device_id="test-reflow-001",
        device_type="reflow-oven",
        name="测试回流焊",
        line_id="L1",
        report_interval=999,
    )
    dev = await manager.create(cfg)
    assert dev.device_id == "test-reflow-001"
    assert dev.device_type == "reflow-oven"
    assert dev.state == "idle"
    assert dev.name == "测试回流焊"


@pytest.mark.asyncio
async def test_list_all(manager):
    await manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    await manager.create(DeviceConfig(device_id="d2", device_type="injection-molder", name="B", line_id="L2"))
    devices = manager.list_all()
    assert len(devices) == 2


@pytest.mark.asyncio
async def test_get_device(manager):
    await manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    dev = manager.get("d1")
    assert dev is not None
    assert dev.name == "A"


def test_get_nonexistent(manager):
    assert manager.get("nope") is None


# ---- Delete ----

@pytest.mark.asyncio
async def test_delete_device(manager):
    await manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    await manager.delete("d1")
    assert manager.get("d1") is None


@pytest.mark.asyncio
async def test_delete_running_device_stops_first(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    await manager.create(cfg)
    await manager.start("d1")
    assert manager.get("d1").state == "running"
    await manager.delete("d1")
    assert manager.get("d1") is None
    # Give the stopped device a moment to clear tasks
    await asyncio.sleep(0.1)


# ---- Start / Stop / Pause ----

@pytest.mark.asyncio
async def test_start_stop_pause(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    await manager.create(cfg)
    dev = manager.get("d1")
    assert dev.state == "idle"

    await manager.start("d1")
    assert dev.state == "running"

    await manager.pause("d1")
    assert dev.state == "paused"

    await manager.start("d1")  # start from paused = resume
    assert dev.state == "running"

    await manager.stop("d1")
    assert dev.state == "idle"
    # Give the stopped device a moment to clear tasks
    await asyncio.sleep(0.1)


# ---- Configure Params ----

@pytest.mark.asyncio
async def test_configure_params(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    await manager.create(cfg)
    dev = manager.get("d1")
    await manager.configure("d1", {"temperature": 260, "conveyor_speed": 70, "oxygen_ppm": 150})
    assert dev.current_params["temperature"] == 260
    assert dev.current_params["conveyor_speed"] == 70


# ---- Enqueue Experiment ----

@pytest.mark.asyncio
async def test_enqueue_experiment(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    await manager.create(cfg)
    dev = manager.get("d1")
    await manager.enqueue_experiment("d1", 3)
    assert dev.experiment_queue.qsize() == 1
    plan_id = await dev.experiment_queue.get()
    assert plan_id == 3


# ---- Get State ----

@pytest.mark.asyncio
async def test_get_state_snapshot(manager):
    await manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    await manager.create(DeviceConfig(device_id="d2", device_type="cnc-drill", name="B", line_id="L2"))
    state = manager.get_state()
    assert state["summary"]["running"] == 0
    assert state["summary"]["idle"] == 2
    assert len(state["devices"]) == 2


@pytest.mark.asyncio
async def test_get_state_with_running(manager):
    await manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    await manager.create(DeviceConfig(device_id="d2", device_type="cnc-drill", name="B", line_id="L2"))
    await manager.start("d1")
    state = manager.get_state()
    assert state["summary"]["running"] == 1
    assert state["summary"]["idle"] == 1
    assert len(state["devices"]) == 2
    await manager.stop("d1")
    await asyncio.sleep(0.1)


# ---- Duplicate Create ----

@pytest.mark.asyncio
async def test_duplicate_create_replaces_existing(manager):
    c1 = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    c2 = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A-v2", line_id="L2")
    await manager.create(c1)
    await manager.start("d1")
    await manager.create(c2)  # should stop old, replace with new
    dev = manager.get("d1")
    assert dev.name == "A-v2"
    assert dev.line_id == "L2"
    assert dev.state == "idle"


# ---- Events Queue ----

@pytest.mark.asyncio
async def test_device_events_queue(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    await manager.create(cfg)
    dev = manager.get("d1")
    # Put a test event
    await dev.events.put({"type": "test", "msg": "hello"})
    event = await asyncio.wait_for(dev.events.get(), timeout=0.1)
    assert event["type"] == "test"
