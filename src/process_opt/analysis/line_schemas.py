from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    responsible: str = Field(min_length=1)
    location: str | None = None


class LineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1)
    responsible: str | None = Field(default=None, min_length=1)
    location: str | None = None


class LineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    responsible: str
    location: str | None
    device_count: int
    created_at: datetime
    updated_at: datetime


class DeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    line_id: str | None
    line_name: str | None
    name: str
    type: str
    icon: str | None
    description: str | None


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    icon: str | None = None
    description: str | None = None
    line_id: str | None = None


class LineDetailResponse(LineResponse):
    devices: list[DeviceResponse]


class DeviceSpcSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    device_name: str
    type: str
    status: str
    worst_cpk: float | None
    param_count: int
    outlier_total: int


class LineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_count: int
    normal_count: int
    abnormal_count: int
    marginal_count: int
    no_spec_count: int
    status: str


class LineMonitorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: LineResponse
    summary: LineSummary
    devices: list[DeviceSpcSummary]
