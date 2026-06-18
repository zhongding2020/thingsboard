from enum import Enum

from pydantic import BaseModel, Field


class DesignMethod(str, Enum):
    full_factorial = "full_factorial"
    frac_factorial = "frac_factorial"
    central_composite = "central_composite"
    box_behnken = "box_behnken"
    taguchi = "taguchi"


class Factor(BaseModel):
    name: str
    low: float
    high: float
    unit: str = ""


class DOEConfig(BaseModel):
    method: DesignMethod
    factors: list[Factor] = Field(min_length=2, max_length=10)
    center_points: int = 0
    alpha: str | None = None
    replicates: int = Field(default=1, ge=1, le=10)


class DOERun(BaseModel):
    run_order: int
    standard_order: int
    factor_values: dict[str, float]
    replicate: int = 1


class DOEDesign(BaseModel):
    method: DesignMethod
    factors: list[Factor]
    runs: list[DOERun]
    run_count: int
    design_matrix: list[list[float]]


class ExperimentResult(BaseModel):
    run_order: int
    response: float


class ANOVARequest(BaseModel):
    factors: list[Factor]
    design_runs: list[DOERun]
    results: list[ExperimentResult]
    response_name: str = "response"
    interactions: list[list[str]] = []


class FactorEffect(BaseModel):
    factor: str
    effect: float
    coefficient: float
    std_error: float
    t_value: float
    p_value: float
    significant: bool


class ANOVAResult(BaseModel):
    response_name: str
    effects: list[FactorEffect]
    r_squared: float
    adj_r_squared: float
    model_significant: bool
    summary: str
