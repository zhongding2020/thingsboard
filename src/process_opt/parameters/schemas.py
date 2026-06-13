from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParameterStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ParameterItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    param_key: str = Field(min_length=1)
    param_value: Any
    unit: str | None = None
    data_type: str = Field(min_length=1)
    min_value: float | None = None
    max_value: float | None = None
    description: str | None = None


class ParameterSetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    note: str | None = None
    items: list[ParameterItemCreate] = Field(min_length=1)


class ParameterItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    set_id: int
    param_key: str
    param_value: Any
    unit: str | None = None
    data_type: str
    min_value: float | None = None
    max_value: float | None = None
    description: str | None = None


class ParameterSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    device_type: str
    version: int
    status: ParameterStatus
    source: str
    created_by: str
    approved_by: str | None = None
    activated_by: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    activated_at: datetime | None = None
    archived_at: datetime | None = None


class ParameterSetWithItems(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter_set: ParameterSet
    items: list[ParameterItem]
    checksum: str


class ParameterConfirmationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    parameter_set_id: int
    parameter_version: int
    status: str = Field(min_length=1)
    message: str | None = None
