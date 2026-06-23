from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from process_opt.common.schemas import InspectionItem


@dataclass
class ParamSpec:
    key: str
    unit: str = ""
    min_val: float = 0.0
    max_val: float = 100.0
    default: float = 0.0


@dataclass
class ResultSpec:
    name: str
    unit: str = ""
    usl: float = 0.0
    lsl: float = 0.0


class MechanismModel(ABC):
    """工艺机理模型基类。子类需声明 param_spec 和 result_spec，并实现 simulate。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {}
    result_spec: ClassVar[list[ResultSpec]] = []

    @abstractmethod
    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        """输入工艺参数 → 输出检测结果列表（基于领域机理 + 可控噪声）。"""
        ...
