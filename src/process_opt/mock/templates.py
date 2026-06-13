from typing import Any

DEVICE_TEMPLATES: dict[str, dict[str, Any]] = {
    "reflow-oven": {
        "params": {
            "temperature": {"min": 100, "max": 300, "mu": 220, "sigma": 20, "precision": 1},
            "conveyor_speed": {"min": 10, "max": 100, "mu": 50, "sigma": 10, "precision": 1},
            "oxygen_ppm": {"min": 0, "max": 1000, "mu": 200, "sigma": 50, "precision": 0},
        },
        "results": {
            "solder_joint_quality": "pass_fail",
            "voiding_pct": {"min": 0, "max": 5},
        },
    },
    "injection-molder": {
        "params": {
            "melt_temp": {"min": 150, "max": 350, "mu": 260, "sigma": 15, "precision": 1},
            "injection_pressure": {"min": 50, "max": 200, "mu": 120, "sigma": 20, "precision": 1},
            "cooling_time": {"min": 5, "max": 60, "mu": 25, "sigma": 8, "precision": 1},
        },
        "results": {
            "dimensional_accuracy": "pass_fail",
            "flash_present": "pass_fail",
        },
    },
}
