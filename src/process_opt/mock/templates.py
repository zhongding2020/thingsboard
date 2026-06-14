from typing import Any

DEVICE_TEMPLATES: dict[str, dict[str, Any]] = {
    "reflow-oven": {
        "params": {
            "temperature": {"min": 100, "max": 300, "mu": 220, "sigma": 20, "precision": 1},
            "conveyor_speed": {"min": 10, "max": 100, "mu": 50, "sigma": 10, "precision": 1},
            "oxygen_ppm": {"min": 0, "max": 1000, "mu": 200, "sigma": 50, "precision": 0},
        },
        "results": [
            {"name": "solder_joint_quality", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "voiding_pct", "value": 0.0, "unit": "", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "injection-molder": {
        "params": {
            "melt_temp": {"min": 150, "max": 350, "mu": 260, "sigma": 15, "precision": 1},
            "injection_pressure": {"min": 50, "max": 200, "mu": 120, "sigma": 20, "precision": 1},
            "cooling_time": {"min": 5, "max": 60, "mu": 25, "sigma": 8, "precision": 1},
        },
        "results": [
            {"name": "dimensional_accuracy", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "flash_present", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
        ],
    },
    "pick-and-place": {
        "params": {
            "placement_speed": {"min": 5000, "max": 30000, "mu": 18000, "sigma": 3000, "precision": 0},
            "placement_accuracy_um": {"min": 10, "max": 100, "mu": 45, "sigma": 12, "precision": 1},
            "feeder_count": {"min": 20, "max": 120, "mu": 60, "sigma": 15, "precision": 0},
            "nozzle_pressure": {"min": 40, "max": 90, "mu": 65, "sigma": 8, "precision": 1},
        },
        "results": [
            {"name": "placement_quality", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "misalignment_count", "value": 0.0, "unit": "", "result": "pass", "usl": 20.0, "lsl": 0.0},
        ],
    },
    "wave-solder": {
        "params": {
            "solder_temp": {"min": 230, "max": 280, "mu": 255, "sigma": 8, "precision": 1},
            "wave_height": {"min": 3, "max": 12, "mu": 7, "sigma": 1.5, "precision": 1},
            "preheat_temp": {"min": 80, "max": 150, "mu": 110, "sigma": 10, "precision": 1},
            "conveyor_angle": {"min": 3, "max": 8, "mu": 5.5, "sigma": 0.8, "precision": 1},
        },
        "results": [
            {"name": "solder_bridge_rate", "value": 0.0, "unit": "", "result": "pass", "usl": 3.0, "lsl": 0.0},
            {"name": "through_hole_fill", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
        ],
    },
    "cnc-drill": {
        "params": {
            "spindle_speed": {"min": 5000, "max": 25000, "mu": 15000, "sigma": 3000, "precision": 0},
            "feed_rate": {"min": 100, "max": 800, "mu": 400, "sigma": 100, "precision": 0},
            "drill_depth": {"min": 0.5, "max": 12.0, "mu": 4.5, "sigma": 1.5, "precision": 2},
            "coolant_flow": {"min": 2, "max": 15, "mu": 8, "sigma": 2, "precision": 1},
        },
        "results": [
            {"name": "hole_accuracy", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "surface_roughness_ra", "value": 0.5, "unit": "", "result": "pass", "usl": 6.0, "lsl": 0.5},
        ],
    },
    "3d-printer": {
        "params": {
            "nozzle_temp": {"min": 180, "max": 260, "mu": 215, "sigma": 12, "precision": 1},
            "bed_temp": {"min": 50, "max": 110, "mu": 70, "sigma": 10, "precision": 1},
            "layer_height": {"min": 0.05, "max": 0.30, "mu": 0.16, "sigma": 0.04, "precision": 2},
            "print_speed": {"min": 20, "max": 120, "mu": 60, "sigma": 15, "precision": 0},
            "filament_diameter": {"min": 1.70, "max": 1.80, "mu": 1.75, "sigma": 0.02, "precision": 2},
        },
        "results": [
            {"name": "print_quality", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "warping_mm", "value": 0.0, "unit": "", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "testing-station": {
        "params": {
            "test_voltage": {"min": 3.0, "max": 5.5, "mu": 3.3, "sigma": 0.3, "precision": 2},
            "test_current_ma": {"min": 10, "max": 500, "mu": 150, "sigma": 60, "precision": 1},
            "test_temperature": {"min": 20, "max": 85, "mu": 45, "sigma": 10, "precision": 1},
            "cycle_time_ms": {"min": 50, "max": 2000, "mu": 600, "sigma": 200, "precision": 0},
        },
        "results": [
            {"name": "functional_test", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "leakage_current_na", "value": 0.0, "unit": "nA", "result": "pass", "usl": 100.0, "lsl": 0.0},
        ],
    },
    "laser-cutter": {
        "params": {
            "laser_power": {"min": 50, "max": 500, "mu": 280, "sigma": 60, "precision": 1},
            "cutting_speed": {"min": 10, "max": 200, "mu": 100, "sigma": 25, "precision": 1},
            "focus_depth": {"min": 0.5, "max": 8.0, "mu": 3.5, "sigma": 1.2, "precision": 2},
            "gas_pressure": {"min": 2, "max": 20, "mu": 10, "sigma": 3, "precision": 1},
        },
        "results": [
            {"name": "cut_quality", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "kerf_width_um", "value": 50.0, "unit": "", "result": "pass", "usl": 300.0, "lsl": 50.0},
        ],
    },
    "coating-machine": {
        "params": {
            "spray_pressure": {"min": 10, "max": 60, "mu": 35, "sigma": 8, "precision": 1},
            "coating_thickness_um": {"min": 5, "max": 100, "mu": 45, "sigma": 15, "precision": 1},
            "cure_temp": {"min": 60, "max": 180, "mu": 120, "sigma": 15, "precision": 1},
            "conveyor_speed": {"min": 0.5, "max": 5.0, "mu": 2.5, "sigma": 0.6, "precision": 1},
        },
        "results": [
            {"name": "coating_uniformity", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "bubble_count", "value": 0.0, "unit": "", "result": "pass", "usl": 10.0, "lsl": 0.0},
        ],
    },
    "xray-inspection": {
        "params": {
            "xray_voltage_kv": {"min": 40, "max": 150, "mu": 90, "sigma": 15, "precision": 1},
            "exposure_ms": {"min": 100, "max": 2000, "mu": 800, "sigma": 300, "precision": 0},
            "resolution_um": {"min": 1, "max": 20, "mu": 8, "sigma": 3, "precision": 1},
            "detector_gain": {"min": 1.0, "max": 8.0, "mu": 4.0, "sigma": 1.2, "precision": 1},
        },
        "results": [
            {"name": "defect_detected", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "false_positive_rate", "value": 0.0, "unit": "", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "oven-curing": {
        "params": {
            "oven_temp": {"min": 80, "max": 200, "mu": 150, "sigma": 15, "precision": 1},
            "cure_duration_min": {"min": 10, "max": 120, "mu": 45, "sigma": 15, "precision": 0},
            "humidity_pct": {"min": 10, "max": 80, "mu": 40, "sigma": 10, "precision": 1},
            "airflow_rate": {"min": 5, "max": 50, "mu": 25, "sigma": 8, "precision": 1},
        },
        "results": [
            {"name": "cure_complete", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "weight_loss_pct", "value": 0.0, "unit": "", "result": "pass", "usl": 3.0, "lsl": 0.0},
        ],
    },
    "wire-bonder": {
        "params": {
            "bond_force_g": {"min": 10, "max": 100, "mu": 50, "sigma": 12, "precision": 1},
            "ultrasonic_power": {"min": 20, "max": 200, "mu": 110, "sigma": 25, "precision": 1},
            "bond_time_ms": {"min": 10, "max": 100, "mu": 45, "sigma": 12, "precision": 0},
            "stage_temp": {"min": 100, "max": 250, "mu": 175, "sigma": 20, "precision": 1},
            "wire_tension": {"min": 3, "max": 15, "mu": 8, "sigma": 2, "precision": 1},
        },
        "results": [
            {"name": "bond_strength", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "lift_off_count", "value": 0.0, "unit": "", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "ultrasonic-cleaner": {
        "params": {
            "frequency_khz": {"min": 20, "max": 80, "mu": 40, "sigma": 8, "precision": 0},
            "power_watt": {"min": 100, "max": 1000, "mu": 500, "sigma": 150, "precision": 0},
            "clean_time_min": {"min": 3, "max": 30, "mu": 12, "sigma": 4, "precision": 0},
            "temperature_c": {"min": 25, "max": 80, "mu": 50, "sigma": 8, "precision": 1},
            "solution_conc_pct": {"min": 1, "max": 20, "mu": 7, "sigma": 3, "precision": 1},
        },
        "results": [
            {"name": "cleanliness_pass", "value": 0.5, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "particle_residue", "value": 0.0, "unit": "", "result": "pass", "usl": 50.0, "lsl": 0.0},
        ],
    },
}
