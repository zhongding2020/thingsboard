from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from starlette.responses import StreamingResponse

from process_opt.mock.manager import DeviceConfig, MockManager

logger = logging.getLogger(__name__)


def register_mock_routes(app: Any, mock_manager: MockManager) -> None:
    router = APIRouter(prefix="/api/v1/mock")

    @router.get("/devices")
    async def list_devices() -> dict:
        return mock_manager.get_state()

    @router.post("/devices", status_code=status.HTTP_201_CREATED)
    async def create_device(body: dict[str, Any]) -> dict:
        try:
            config = DeviceConfig(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
        device = mock_manager.create(config)
        return {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "name": device.name,
            "line_id": device.line_id,
            "status": device.state,
            "report_interval": device.report_interval,
            "current_params": device.current_params,
        }

    @router.get("/devices/{device_id}")
    async def get_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return {
            "device_id": dev.device_id,
            "device_type": dev.device_type,
            "name": dev.name,
            "line_id": dev.line_id,
            "status": dev.state,
            "report_interval": dev.report_interval,
            "report_count": dev._report_count,
            "current_params": dev.current_params,
            "last_heartbeat": dev._last_heartbeat,
        }

    @router.delete("/devices/{device_id}")
    async def delete_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.delete(device_id)
        return {"device_id": device_id, "deleted": True}

    @router.post("/devices/{device_id}/start")
    async def start_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.start(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.post("/devices/{device_id}/pause")
    async def pause_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.pause(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.post("/devices/{device_id}/stop")
    async def stop_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.stop(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.put("/devices/{device_id}/params")
    async def update_params(device_id: str, body: dict[str, Any]) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.configure(device_id, body)
        return {
            "device_id": device_id,
            "current_params": dev.current_params,
            "confirmed": True,
        }

    @router.post("/devices/{device_id}/experiments", status_code=status.HTTP_202_ACCEPTED)
    async def assign_experiment(device_id: str, body: dict[str, Any]) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        plan_id = body.get("plan_id")
        if not plan_id:
            raise HTTPException(status_code=422, detail="plan_id required")
        await mock_manager.enqueue_experiment(device_id, plan_id)
        return {
            "device_id": device_id,
            "plan_id": plan_id,
            "status": "queued",
            "total_runs": body.get("total_runs", "unknown"),
        }

    @router.get("/devices/{device_id}/events")
    async def stream_events(device_id: str, request: Request) -> StreamingResponse:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")

        async def generate():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(dev.events.get(), timeout=15)
                        yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n".encode()
                    except asyncio.TimeoutError:
                        yield b':keepalive\n\n'
            except asyncio.CancelledError:
                pass

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(router)
