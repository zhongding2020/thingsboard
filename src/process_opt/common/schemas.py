from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    processed_at: datetime
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
    results: dict[str, Any]

    @field_validator("results")
    @classmethod
    def results_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("results must not be empty")
        return value
