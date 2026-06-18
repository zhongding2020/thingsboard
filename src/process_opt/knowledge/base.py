from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Importance(str, Enum):
    critical = "critical"
    important = "important"
    auxiliary = "auxiliary"


class ParamType(str, Enum):
    continuous = "continuous"
    discrete = "discrete"
    categorical = "categorical"


class ParameterRange(BaseModel):
    min: float
    max: float


class ProcessParameter(BaseModel):
    key: str
    name: str
    unit: str
    type: ParamType = ParamType.continuous
    range: ParameterRange
    target: ParameterRange
    importance: Importance = Importance.important
    description: str = ""
    notes: str = ""


class QualityMetric(BaseModel):
    key: str
    name: str
    unit: str
    description: str = ""
    usl: float | None = None
    lsl: float | None = None


class RuleType(str, Enum):
    hard_constraint = "hard_constraint"
    soft_guideline = "soft_guideline"
    dependency = "dependency"


class Rule(BaseModel):
    type: RuleType
    expression: str
    message: str
    trigger: str | None = None
    effect: str | None = None


class ProcessTemplate(BaseModel):
    process_type: str
    display_name: str
    description: str = ""
    parameters: list[ProcessParameter] = []
    quality_metrics: list[QualityMetric] = []
    rules: list[Rule] = []
    analysis_hints: list[str] = []
