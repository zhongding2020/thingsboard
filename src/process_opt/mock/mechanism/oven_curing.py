from __future__ import annotations

import math
import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("oven-curing")
class OvenCuringModel(MechanismModel):
    """固化炉机理：Arrhenius 固化动力学 — 固化度取决于温度×时间的积分，湿度抑制固化。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "oven_temp": ParamSpec(key="oven_temp", unit="°C", min_val=80, max_val=200, default=150),
        "cure_duration_min": ParamSpec(key="cure_duration_min", unit="min", min_val=10, max_val=120, default=45),
        "humidity_pct": ParamSpec(key="humidity_pct", unit="%", min_val=10, max_val=80, default=40),
        "airflow_rate": ParamSpec(key="airflow_rate", unit="m³/h", min_val=5, max_val=50, default=25),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="cure_complete", usl=1.5, lsl=0.5),
        ResultSpec(name="weight_loss_pct", unit="%", usl=3.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        temp = params["oven_temp"]
        duration = params["cure_duration_min"]
        humidity = params["humidity_pct"]
        airflow = params["airflow_rate"]

        # Arrhenius 简化：固化速率 k = A * exp(-Ea/RT)
        # 简化后固化度 ∝ temp * duration，湿度抑制
        R = 8.314
        T_kelvin = temp + 273.15
        k = math.exp(-50000 / (R * T_kelvin))  # Ea ≈ 50 kJ/mol
        cure_raw = k * duration * (1 - humidity / 200) * airflow / 25
        cure = 0.3 + cure_raw * 12000

        # 失重：高温长时 → 更多挥发
        weight_loss = 0.3 + (temp - 80) * 0.015 + duration * 0.008

        cure += random.gauss(0, 0.03)
        weight_loss += random.gauss(0, 0.1)

        cure = round(cure, 2)
        weight_loss = round(weight_loss, 2)

        return [
            InspectionItem(
                name="cure_complete", value=cure, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= cure <= 1.5 else "fail",
            ),
            InspectionItem(
                name="weight_loss_pct", value=weight_loss, unit="%", usl=3.0, lsl=0.0,
                result="pass" if weight_loss <= 3.0 else "fail",
            ),
        ]
