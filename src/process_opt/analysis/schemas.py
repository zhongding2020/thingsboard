from __future__ import annotations

from typing import Any

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_fields: list[str] = Field(default=[])
    target_fields: list[str] = Field(default=[])
    missing_strategy: str = "drop_row"
    max_samples: int | None = None
    dataset_id: str | None = None


class AnalysisDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: list[dict[str, Any]]
    targets: list[dict[str, Any]]
    metadata: list[dict[str, Any]]
    field_summary: dict[str, Any]
    sample_count: int
    truncated: bool = False


class ProfilingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    dtype: str = "numeric"
    count: int = 0
    missing_count: int = 0
    missing_rate: float = 0.0
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    iqr_outliers: int = 0


class CorrelationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_x: str
    field_y: str
    method: str = "pearson"


class CorrelationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_x: str
    field_y: str
    coefficient: float
    p_value: float
    method: str


class ImportanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_fields: list[str] = Field(min_length=1)
    target_field: str
    method: str = "random_forest"


class ImportanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    importances: dict[str, float]
    method: str


class RegressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_fields: list[str] = Field(min_length=1)
    target_field: str
    model_type: str = "linear"


class RegressionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    r_squared: float
    rmse: float
    coefficients: dict[str, float]
    model_type: str


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    min: float | None = None
    max: float | None = None


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_fields: list[str] = Field(min_length=1)
    target_field: str
    target_value: float
    constraints: list[Constraint] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_parameters: dict[str, float]
    predicted_target: float
    alternatives: list[dict[str, float]]
    important_features: list[str]
    risk_notes: list[str]
    model_metrics: dict[str, Any]
    dataset_summary: dict[str, Any]
    can_submit_as_proposed: bool = True


class SpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    field: str | None = None
    line_id: str | None = None
    usl: float | None = None
    lsl: float | None = None
    target: float | None = None
    since: datetime | None = None


class IChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[float]
    labels: list[str]
    mean: float
    ucl: float
    lcl: float
    alerts: list[int]


class MrChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[float]
    labels: list[str]
    mr_bar: float
    ucl: float


class Histogram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bins: list[float]
    counts: list[int]
    curve_x: list[float]
    curve_y: list[float]


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cp: float
    cpk: float
    pp: float
    ppk: float
    usl: float
    lsl: float
    target: float | None = None


class PChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    periods: list[str]
    rates: list[float]
    total_count: int
    defect_count: int
    ucl: float
    p_bar: float


class SummaryStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    mean: float
    std: float
    min_val: float
    max_val: float
    normality_p: float | None = None


class ParamOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    n: int
    mean: float
    std: float
    usl: float
    lsl: float
    cpk: float | None = None
    outlier_count: int
    status: str  # "normal" | "marginal" | "abnormal" | "no_spec"


class SpcResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overview: list[ParamOverview]
    i_chart: IChart | None = None
    mr_chart: MrChart | None = None
    histogram: Histogram | None = None
    capability: Capability | None = None
    p_chart: PChart | None = None
    summary: SummaryStats | None = None
