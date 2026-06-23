from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from process_opt.mock.mechanism import get_mechanism

logger = logging.getLogger(__name__)


class MockDevice:
    """单设备模拟引擎 — 内部跑 4 个 asyncio.Task。"""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        name: str = "",
        line_id: str = "",
        report_interval: int = 60,
        *,
        gateway_url: str,
        api_url: str,
        api_key: str,
        use_mechanism: bool = True,
    ):
        self.device_id = device_id
        self.device_type = device_type
        self.name = name or device_id
        self.line_id = line_id
        self.report_interval = report_interval

        self._gateway_url = gateway_url.rstrip("/")
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._use_mechanism = use_mechanism
        self._http: httpx.AsyncClient | None = None

        # Mechanism model
        try:
            self._mechanism = get_mechanism(device_type) if use_mechanism else None
        except ValueError:
            self._mechanism = None

        # Build default params from mechanism spec
        if self._mechanism is not None:
            self.current_params: dict[str, Any] = {
                k: v.default for k, v in self._mechanism.param_spec.items()
            }
        else:
            self.current_params = {}

        self.state: str = "idle"  # idle | running | paused
        self.experiment_queue: asyncio.Queue[int] = asyncio.Queue()
        self.events: asyncio.Queue[dict] = asyncio.Queue()

        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._report_count = 0
        self._last_heartbeat: float | None = None

    # ---- lifecycle ----

    async def start(self) -> None:
        if self.state == "running":
            return
        self.state = "running"
        self._stop_event.clear()
        self._http = httpx.AsyncClient()
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._report_loop()),
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(self._experiment_loop()),
        ]
        await self._emit("status", {"status": "running"})

    async def pause(self) -> None:
        if self.state != "running":
            return
        self.state = "paused"
        await self._cancel_tasks()
        await self._emit("status", {"status": "paused"})

    async def stop(self) -> None:
        if self.state == "idle":
            return
        self.state = "idle"
        await self._cancel_tasks()
        if self._http:
            await self._http.aclose()
            self._http = None
        await self._emit("status", {"status": "idle"})

    async def _cancel_tasks(self) -> None:
        self._stop_event.set()
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    # ---- Task loops ----

    async def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._send_heartbeat()
            except Exception:
                await self._emit("error", {"message": "Heartbeat send failed"})
            await self._sleep_or_stop(30)

    async def _report_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._send_data_pair()
            except Exception:
                await self._emit("error", {"message": "Data report failed"})
            await self._sleep_or_stop(self.report_interval)

    async def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._poll_experiments()
            except Exception:
                pass  # polling failures are non-critical
            await self._sleep_or_stop(30)

    async def _experiment_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                plan_id = await asyncio.wait_for(self.experiment_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                continue
            try:
                await self._execute_experiment(plan_id)
            except Exception as exc:
                await self._emit("error", {"message": f"Experiment {plan_id} failed: {exc}"})

    # ---- Network ops ----

    async def _send_heartbeat(self) -> None:
        payload = {
            "message_id": f"hb-{self.device_id}-{int(time.time())}",
            "barcode": "_heartbeat_",
            "device_id": self.device_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "product_model": "",
            "params": {
                "_heartbeat": True,
                "status": self.state,
                "current_params": self.current_params,
            },
        }
        if self._http:
            r = await self._http.post(
                f"{self._gateway_url}/api/v1/data/process",
                json=payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
            r.raise_for_status()
        self._last_heartbeat = time.monotonic()
        await self._emit("heartbeat", {"status": self.state, "current_params": dict(self.current_params)})

    async def _send_data_pair(self) -> None:
        # Generate params with small noise
        noisy_params = {}
        for k, v in self.current_params.items():
            if isinstance(v, (int, float)):
                sigma = abs(v) * 0.01 + 0.1
                noisy_params[k] = round(v + random.gauss(0, sigma), 2)
            else:
                noisy_params[k] = v

        message_id = str(uuid4())
        barcode = f"MOCK-{uuid4().hex[:8].upper()}"
        now = datetime.now(UTC).isoformat()

        process_payload = {
            "message_id": message_id,
            "barcode": barcode,
            "device_id": self.device_id,
            "processed_at": now,
            "product_model": random.choice(["A", "B", "C"]),
            "params": noisy_params,
        }

        # Generate inspection results via mechanism or fallback
        if self._mechanism is not None:
            results = self._mechanism.simulate(noisy_params)
            insp_results = [
                {"name": r.name, "value": r.value, "unit": r.unit or "",
                 "result": r.result, "usl": r.usl, "lsl": r.lsl}
                for r in results
            ]
        else:
            insp_results = []

        inspection_payload = {
            "message_id": message_id,
            "barcode": barcode,
            "station_id": f"{self.device_id}-qa",
            "inspected_at": now,
            "product_model": process_payload["product_model"],
            "results": insp_results,
        }

        if self._http:
            r1 = await self._http.post(
                f"{self._gateway_url}/api/v1/data/process",
                json=process_payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
            r1.raise_for_status()
            r2 = await self._http.post(
                f"{self._gateway_url}/api/v1/data/inspection",
                json=inspection_payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
            r2.raise_for_status()
        self._report_count += 1
        await self._emit("data.reported", {"barcode": barcode})

    async def _poll_experiments(self) -> None:
        if self._http is None:
            return
        need_plan = self.experiment_queue.empty()
        if not need_plan:
            return
        try:
            r = await self._http.get(
                f"{self._api_url}/api/v1/experiment/plans",
                params={"process_type": self.device_type, "limit": 5},
            )
            if r.status_code == 200:
                plans = r.json()
                for p in plans:
                    if p.get("status") in ("draft", "ready"):
                        self.experiment_queue.put_nowait(p["id"])
                        break
        except Exception:
            pass

    async def _execute_experiment(self, plan_id: int) -> None:
        if self._http is None:
            return
        # Fetch plan details
        r = await self._http.get(f"{self._api_url}/api/v1/experiment/plans/{plan_id}")
        if r.status_code != 200:
            return
        plan = r.json()
        runs = plan.get("design_runs", [])
        response_name = plan.get("response_name", "response")

        total = len(runs)
        for idx, run in enumerate(runs, start=1):
            # Inject factor values into current_params
            params = dict(self.current_params)
            for factor in run.get("factors", {}):
                params[factor] = run["factors"][factor]

            # Simulate
            if self._mechanism is not None:
                results = self._mechanism.simulate(params)
                # Find response value
                response_value = None
                for ri in results:
                    if ri.name == response_name:
                        response_value = ri.value
                        break
                if response_value is None and results:
                    response_value = results[0].value
            else:
                response_value = random.uniform(0.5, 1.5)

            # Report result
            await self._http.post(
                f"{self._api_url}/api/v1/experiment/plans/{plan_id}/results",
                json={
                    "run_order": run.get("run_order", idx),
                    "response_value": response_value,
                    "device_id": self.device_id,
                },
            )
            await self._emit("experiment.progress", {
                "plan_id": plan_id, "run_order": idx, "total_runs": total,
            })

        await self._emit("experiment.complete", {"plan_id": plan_id, "total_runs": total})

    # ---- helpers ----

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _emit(self, event_type: str, data: dict) -> None:
        payload = {"type": event_type, "device_id": self.device_id, **data}
        try:
            self.events.put_nowait(payload)
        except asyncio.QueueFull:
            pass
