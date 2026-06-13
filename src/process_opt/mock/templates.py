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
    "pick-and-place": {
        "params": {
            "placement_speed": {"min": 5000, "max": 30000, "mu": 18000, "sigma": 3000, "precision": 0},
            "placement_accuracy_um": {"min": 10, "max": 100, "mu": 45, "sigma": 12, "precision": 1},
            "feeder_count": {"min": 20, "max": 120, "mu": 60, "sigma": 15, "precision": 0},
            "nozzle_pressure": {"min": 40, "max": 90, "mu": 65, "sigma": 8, "precision": 1},
        },
        "results": {
            "placement_quality": "pass_fail",
            "misalignment_count": {"min": 0, "max": 20},
        },
    },
    "wave-solder": {
        "params": {
            "solder_temp": {"min": 230, "max": 280, "mu": 255, "sigma": 8, "precision": 1},
            "wave_height": {"min": 3, "max": 12, "mu": 7, "sigma": 1.5, "precision": 1},
            "preheat_temp": {"min": 80, "max": 150, "mu": 110, "sigma": 10, "precision": 1},
            "conveyor_angle": {"min": 3, "max": 8, "mu": 5.5, "sigma": 0.8, "precision": 1},
        },
        "results": {
            "solder_bridge_rate": {"min": 0, "max": 3},
            "through_hole_fill": "pass_fail",
        },
    },
    "cnc-drill": {
        "params": {
            "spindle_speed": {"min": 5000, "max": 25000, "mu": 15000, "sigma": 3000, "precision": 0},
            "feed_rate": {"min": 100, "max": 800, "mu": 400, "sigma": 100, "precision": 0},
            "drill_depth": {"min": 0.5, "max": 12.0, "mu": 4.5, "sigma": 1.5, "precision": 2},
            "coolant_flow": {"min": 2, "max": 15, "mu": 8, "sigma": 2, "precision": 1},
        },
        "results": {
            "hole_accuracy": "pass_fail",
            "surface_roughness_ra": {"min": 0.5, "max": 6.0},
        },
    },
    "3d-printer": {
        "params": {
            "nozzle_temp": {"min": 180, "max": 260, "mu": 215, "sigma": 12, "precision": 1},
            "bed_temp": {"min": 50, "max": 110, "mu": 70, "sigma": 10, "precision": 1},
            "layer_height": {"min": 0.05, "max": 0.30, "mu": 0.16, "sigma": 0.04, "precision": 2},
            "print_speed": {"min": 20, "max": 120, "mu": 60, "sigma": 15, "precision": 0},
            "filament_diameter": {"min": 1.70, "max": 1.80, "mu": 1.75, "sigma": 0.02, "precision": 2},
        },
        "results": {
            "print_quality": "pass_fail",
            "warping_mm": {"min": 0, "max": 5.0},
        },
    },
    "testing-station": {
        "params": {
            "test_voltage": {"min": 3.0, "max": 5.5, "mu": 3.3, "sigma": 0.3, "precision": 2},
            "test_current_ma": {"min": 10, "max": 500, "mu": 150, "sigma": 60, "precision": 1},
            "test_temperature": {"min": 20, "max": 85, "mu": 45, "sigma": 10, "precision": 1},
            "cycle_time_ms": {"min": 50, "max": 2000, "mu": 600, "sigma": 200, "precision": 0},
        },
        "results": {
            "functional_test": "pass_fail",
            "leakage_current_na": {"min": 0, "max": 100},
        },
    },
}
