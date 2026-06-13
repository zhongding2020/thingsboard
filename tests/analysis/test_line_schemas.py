import pytest
from pydantic import ValidationError
from process_opt.analysis.line_schemas import (
    LineCreate, LineUpdate, LineResponse, DeviceResponse,
    DeviceUpdate, LineDetailResponse, DeviceSpcSummary,
    LineSummary, LineMonitorResponse,
)
from datetime import datetime, timezone


class TestLineCreate:
    def test_valid_line(self):
        lc = LineCreate(name="SMT-01", responsible="张工", location="A栋2层")
        assert lc.name == "SMT-01"
        assert lc.responsible == "张工"
        assert lc.location == "A栋2层"

    def test_location_optional(self):
        lc = LineCreate(name="SMT-01", responsible="张工")
        assert lc.location is None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            LineCreate(name="", responsible="张工")

    def test_empty_responsible_rejected(self):
        with pytest.raises(ValidationError):
            LineCreate(name="SMT-01", responsible="")


class TestLineUpdate:
    def test_all_fields_optional(self):
        lu = LineUpdate()
        assert lu.name is None
        assert lu.responsible is None
        assert lu.location is None

    def test_partial_update(self):
        lu = LineUpdate(name="新名称")
        assert lu.name == "新名称"
        assert lu.responsible is None


class TestLineResponse:
    def test_serialization(self):
        now = datetime.now(timezone.utc)
        lr = LineResponse(
            id="uuid-1", name="SMT-01", responsible="张工",
            location="A栋", device_count=3,
            created_at=now, updated_at=now,
        )
        d = lr.model_dump()
        assert d["id"] == "uuid-1"
        assert d["device_count"] == 3


class TestDeviceUpdate:
    def test_update_line_assignment(self):
        du = DeviceUpdate(line_id="line-1")
        assert du.line_id == "line-1"
        assert du.name is None


class TestLineMonitorResponse:
    def test_valid_response(self):
        now = datetime.now(timezone.utc)
        line = LineResponse(
            id="l1", name="SMT-01", responsible="张工",
            location=None, device_count=2,
            created_at=now, updated_at=now,
        )
        summary = LineSummary(
            device_count=2, normal_count=1, abnormal_count=1,
            marginal_count=0, no_spec_count=0, status="abnormal",
        )
        devices = [
            DeviceSpcSummary(
                device_id="d1", device_name="回流焊-01",
                type="reflow-oven", status="normal",
                worst_cpk=1.5, param_count=3, outlier_total=2,
            ),
            DeviceSpcSummary(
                device_id="d2", device_name="贴片机-03",
                type="pick-and-place", status="abnormal",
                worst_cpk=0.8, param_count=2, outlier_total=12,
            ),
        ]
        resp = LineMonitorResponse(line=line, summary=summary, devices=devices)
        assert resp.summary.status == "abnormal"
        assert len(resp.devices) == 2
