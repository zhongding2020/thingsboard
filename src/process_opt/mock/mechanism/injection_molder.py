from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("injection-molder")
class InjectionMolderModel(MechanismModel):
    """注塑成型机理：尺寸精度取决于熔体温度与压力的平衡，飞边由压力过高引起。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "melt_temp": ParamSpec(key="melt_temp", unit="°C", min_val=150, max_val=350, default=260),
        "injection_pressure": ParamSpec(key="injection_pressure", unit="MPa", min_val=50, max_val=200, default=120),
        "cooling_time": ParamSpec(key="cooling_time", unit="s", min_val=5, max_val=60, default=25),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="dimensional_accuracy", usl=1.5, lsl=0.5),
        ResultSpec(name="flash_present", usl=1.5, lsl=0.5),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        melt_temp = params["melt_temp"]
        pressure = params["injection_pressure"]
        cooling = params["cooling_time"]

        # 尺寸精度：温度与冷却时间的平衡
        temp_ideal = 260
        cool_ideal = 25
        deviation = abs(melt_temp - temp_ideal) / temp_ideal * 0.5 + abs(cooling - cool_ideal) / cool_ideal * 0.3
        accuracy = 1.0 - deviation

        # 飞边：压力过高 → 飞边增多
        flash = 0.3 + max(0, pressure - 100) * 0.008

        accuracy += random.gauss(0, 0.02)
        flash += random.gauss(0, 0.05)

        accuracy = round(accuracy, 2)
        flash = round(flash, 2)

        return [
            InspectionItem(
                name="dimensional_accuracy", value=accuracy, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= accuracy <= 1.5 else "fail",
            ),
            InspectionItem(
                name="flash_present", value=flash, usl=1.5, lsl=0.5,
                result="pass" if flash <= 1.5 else "fail",
            ),
        ]
