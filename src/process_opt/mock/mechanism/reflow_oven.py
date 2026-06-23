from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("reflow-oven")
class ReflowOvenModel(MechanismModel):
    """回流焊机理模型：焊点质量由热输入量决定，空洞率由峰值温度和氧含量共同影响。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "temperature": ParamSpec(key="temperature", unit="°C", min_val=100, max_val=300, default=230),
        "conveyor_speed": ParamSpec(key="conveyor_speed", unit="mm/s", min_val=10, max_val=100, default=60),
        "oxygen_ppm": ParamSpec(key="oxygen_ppm", unit="ppm", min_val=0, max_val=1000, default=200),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="solder_joint_quality", usl=1.5, lsl=0.5),
        ResultSpec(name="voiding_pct", unit="%", usl=5.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        temp = params["temperature"]
        speed = params["conveyor_speed"]
        oxygen = params["oxygen_ppm"]

        # 热输入量 = f(temp, speed)，理想值 ~48
        heat_input = temp / max(speed, 1) * 10
        ideal = 240 / 60 * 10  # = 40
        quality = 1.0 - abs(heat_input - ideal) / ideal * 0.8

        # 空洞率：高温 + 高氧 → 更多空洞
        voiding = max(0, 0.5 + (temp - 230) * 0.02 + oxygen * 0.003)

        # 可控噪声
        quality += random.gauss(0, 0.02)
        voiding += random.gauss(0, 0.15)
        voiding = max(0, voiding)

        quality = round(quality, 2)
        voiding = round(voiding, 2)

        return [
            InspectionItem(
                name="solder_joint_quality", value=quality, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= quality <= 1.5 else "fail",
            ),
            InspectionItem(
                name="voiding_pct", value=voiding, unit="%", usl=5.0, lsl=0.0,
                result="pass" if voiding <= 5.0 else "fail",
            ),
        ]
