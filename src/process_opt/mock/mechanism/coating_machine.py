from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("coating-machine")
class CoatingMachineModel(MechanismModel):
    """涂覆机机理：均匀度取决于喷涂压力与移动速度的配合，气泡由固化温度和厚度决定。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "spray_pressure": ParamSpec(key="spray_pressure", unit="psi", min_val=10, max_val=60, default=35),
        "coating_thickness_um": ParamSpec(key="coating_thickness_um", unit="μm", min_val=5, max_val=100, default=45),
        "cure_temp": ParamSpec(key="cure_temp", unit="°C", min_val=60, max_val=180, default=120),
        "conveyor_speed": ParamSpec(key="conveyor_speed", unit="m/min", min_val=0.5, max_val=5.0, default=2.5),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="coating_uniformity", usl=1.5, lsl=0.5),
        ResultSpec(name="bubble_count", usl=10.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        pressure = params["spray_pressure"]
        thickness = params["coating_thickness_um"]
        cure_temp = params["cure_temp"]
        speed = params["conveyor_speed"]

        # 均匀度：压力×速度的乘积需在理想窗口内
        pv_product = pressure * speed
        ideal = 35 * 2.5  # = 87.5
        uniformity = 1.0 - abs(pv_product - ideal) / ideal * 0.7

        # 气泡：厚涂层 + 过高固化温度 → 更多气泡
        bubbles = 1.0 + thickness * 0.06 + max(0, cure_temp - 100) * 0.04 - pressure * 0.05

        uniformity += random.gauss(0, 0.02)
        bubbles += random.gauss(0, 0.3)

        uniformity = round(uniformity, 2)
        bubbles = round(bubbles, 2)

        return [
            InspectionItem(
                name="coating_uniformity", value=uniformity, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= uniformity <= 1.5 else "fail",
            ),
            InspectionItem(
                name="bubble_count", value=bubbles, usl=10.0, lsl=0.0,
                result="pass" if bubbles <= 10.0 else "fail",
            ),
        ]
