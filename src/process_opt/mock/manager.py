from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from process_opt.mock.device import MockDevice

logger = logging.getLogger(__name__)


class DeviceConfig(BaseModel):
    device_id: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    name: str = ""
    line_id: str = ""
    report_interval: int = Field(default=60, ge=5, le=3600)


class MockManager:
    """管理所有模拟设备生命周期，作为 Backend API 的单例。"""

    def __init__(self, api_url: str, gateway_url: str, api_key: str):
        self._devices: dict[str, MockDevice] = {}
        self._api_url = api_url
        self._gateway_url = gateway_url
        self._api_key = api_key

    def create(self, config: DeviceConfig) -> MockDevice:
        """创建或替换设备（如已存在则先停止旧设备）。"""
        if config.device_id in self._devices:
            old = self._devices[config.device_id]
            try:
                asyncio.ensure_future(old.stop())
            except RuntimeError:
                # No event loop running — stop synchronously as best-effort
                old._stop_event.set()
                for t in old._tasks:
                    t.cancel()
                old._tasks.clear()
                old.state = "idle"

        device = MockDevice(
            device_id=config.device_id,
            device_type=config.device_type,
            name=config.name,
            line_id=config.line_id,
            report_interval=config.report_interval,
            gateway_url=self._gateway_url,
            api_url=self._api_url,
            api_key=self._api_key,
        )
        self._devices[config.device_id] = device
        return device

    async def delete(self, device_id: str) -> None:
        dev = self._devices.pop(device_id, None)
        if dev is not None:
            await dev.stop()

    def get(self, device_id: str) -> MockDevice | None:
        return self._devices.get(device_id)

    def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "device_id": d.device_id,
                "device_type": d.device_type,
                "name": d.name,
                "line_id": d.line_id,
                "status": d.state,
                "report_interval": d.report_interval,
                "report_count": d._report_count,
                "current_params": d.current_params,
            }
            for d in self._devices.values()
        ]

    async def start(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.start()

    async def pause(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.pause()

    async def stop(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.stop()

    async def configure(self, device_id: str, params: dict[str, Any]) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        dev.current_params.update(params)

    async def enqueue_experiment(self, device_id: str, plan_id: int) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.experiment_queue.put(plan_id)

    def get_state(self) -> dict[str, Any]:
        devices = self.list_all()
        summary = {"running": 0, "paused": 0, "idle": 0}
        for d in devices:
            summary[d["status"]] = summary.get(d["status"], 0) + 1
        # Inject line name (from mock data or fallback to line_id)
        for d in devices:
            d["line_name"] = d.get("line_name") or d["line_id"]
        return {"summary": summary, "devices": devices}
