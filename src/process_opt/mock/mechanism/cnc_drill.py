from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("cnc-drill")
class CncDrillModel(MechanismModel):
    """CNC钻孔机理：孔径精度取决于转速/进给的比值，表面粗糙度由进给率和冷却液共同影响。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "spindle_speed": ParamSpec(key="spindle_speed", unit="RPM", min_val=5000, max_val=25000, default=15000),
        "feed_rate": ParamSpec(key="feed_rate", unit="mm/min", min_val=100, max_val=800, default=400),
        "drill_depth": ParamSpec(key="drill_depth", unit="mm", min_val=0.5, max_val=12.0, default=4.5),
        "coolant_flow": ParamSpec(key="coolant_flow", unit="L/min", min_val=2, max_val=15, default=8),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="hole_accuracy", usl=1.5, lsl=0.5),
        ResultSpec(name="surface_roughness_ra", unit="μm", usl=6.0, lsl=0.5),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        speed = params["spindle_speed"]
        feed = params["feed_rate"]
        depth = params["drill_depth"]
        coolant = params["coolant_flow"]

        # 孔径精度：speed/feed 比值的稳定性
        sf_ratio = speed / max(feed, 1)
        ideal_ratio = 15000 / 400  # = 37.5
        accuracy = 1.0 - abs(sf_ratio - ideal_ratio) / ideal_ratio * 0.6 - depth / 20 * 0.1

        # 表面粗糙度：高进给 → 粗糙，充分冷却 → 光滑
        roughness = 1.5 + feed * 0.005 - coolant * 0.15

        accuracy += random.gauss(0, 0.02)
        roughness += random.gauss(0, 0.15)
        roughness = max(0, roughness)

        accuracy = round(accuracy, 2)
        roughness = round(roughness, 2)

        return [
            InspectionItem(
                name="hole_accuracy", value=accuracy, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= accuracy <= 1.5 else "fail",
            ),
            InspectionItem(
                name="surface_roughness_ra", value=roughness, unit="μm", usl=6.0, lsl=0.5,
                result="pass" if roughness <= 6.0 else "fail",
            ),
        ]
