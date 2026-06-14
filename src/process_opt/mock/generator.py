import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from process_opt.mock.templates import DEVICE_TEMPLATES

PRODUCT_MODELS = ["A", "B", "C"]


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


def generate_results(device_type: str, params: dict[str, float | int]) -> list[dict[str, Any]]:
    template = DEVICE_TEMPLATES[device_type]
    results: list[dict[str, Any]] = []
    for item_def in template["results"]:
        name = item_def["name"]
        usl = item_def["usl"]
        lsl = item_def["lsl"]
        if random.random() < 0.05:
            val = random.uniform(usl, usl * 1.2) if random.random() < 0.5 else random.uniform(lsl * 0.8, lsl)
        else:
            val = random.uniform(lsl, usl)
        val = round(val, 2)
        result = "fail" if val > usl or val < lsl else "pass"
        results.append({
            "name": name,
            "value": val,
            "unit": item_def.get("unit", ""),
            "result": result,
            "usl": usl,
            "lsl": lsl,
        })
    return results


def generate_pair(device_type: str, barcode: str, device_index: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    message_id = str(uuid4())
    params = generate_params(device_type)
    results = generate_results(device_type, params)
    now = datetime.now(UTC)
    product_model = random.choice(PRODUCT_MODELS)

    process_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "device_id": f"{device_type}-{device_index:03d}",
        "processed_at": now.isoformat(),
        "product_model": product_model,
        "params": params,
    }

    inspection_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "station_id": f"{device_type}-qa",
        "inspected_at": now.isoformat(),
        "product_model": product_model,
        "results": results,
    }

    return process_payload, inspection_payload
