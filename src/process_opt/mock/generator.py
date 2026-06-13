import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from process_opt.mock.templates import DEVICE_TEMPLATES


def generate_params(device_type: str) -> dict[str, float | int]:
    template = DEVICE_TEMPLATES[device_type]
    params: dict[str, float | int] = {}
    for name, cfg in template["params"].items():
        if random.random() < 0.05:
            val = random.uniform(cfg["min"], cfg["max"])
        else:
            val = random.gauss(cfg["mu"], cfg["sigma"])
        val = max(cfg["min"], min(cfg["max"], val))
        if cfg["precision"] == 0:
            val = int(round(val))
        else:
            val = round(val, cfg["precision"])
        params[name] = val
    return params


def generate_results(device_type: str, params: dict[str, float | int]) -> dict[str, str]:
    template = DEVICE_TEMPLATES[device_type]
    results: dict[str, str] = {}
    for name in template["results"]:
        if device_type == "reflow-oven" and "temperature" in params:
            quality = "fail" if params["temperature"] > 250 else "pass"
        elif device_type == "injection-molder" and "melt_temp" in params:
            quality = "fail" if params["melt_temp"] > 290 else "pass"
        else:
            quality = "pass" if random.random() < 0.9 else "fail"
        results[name] = quality
    return results


def generate_pair(device_type: str, barcode: str, device_index: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    message_id = str(uuid4())
    params = generate_params(device_type)
    results = generate_results(device_type, params)
    now = datetime.now(UTC)

    process_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "device_id": f"{device_type}-{device_index:03d}",
        "processed_at": now.isoformat(),
        "params": params,
    }

    inspection_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "station_id": f"{device_type}-qa",
        "inspected_at": now.isoformat(),
        "results": results,
    }

    return process_payload, inspection_payload
