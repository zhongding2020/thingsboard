from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InspectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    value: float
    unit: str = ""
    result: str = Field(default="pass", pattern="^(pass|fail)$")
    usl: float | None = None
    lsl: float | None = None


class ProcessMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    processed_at: datetime
    product_model: str = ""
    params: dict[str, Any]

    @field_validator("params")
    @classmethod
    def params_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("params must not be empty")
        return value


class InspectionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    station_id: str = Field(min_length=1)
    inspected_at: datetime
    product_model: str = ""
    results: list[InspectionItem]

    @field_validator("results")
    @classmethod
    def results_not_empty(cls, value: list[InspectionItem]) -> list[InspectionItem]:
        if not value:
            raise ValueError("results must not be empty")
        return value
