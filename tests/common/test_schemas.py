from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from process_opt.common.schemas import InspectionMessage, ProcessMessage


def test_process_message_accepts_required_fields() -> None:
    msg = ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC), params={"temperature": 180})
    assert msg.barcode == "B1"


def test_process_message_rejects_empty_params() -> None:
    with pytest.raises(ValidationError):
        ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC), params={})


def test_inspection_message_accepts_required_fields() -> None:
    msg = InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at=datetime(2026, 6, 8, 10, 5, tzinfo=UTC), results={"diameter": 10.2})
    assert msg.station_id == "QA1"


def test_inspection_message_rejects_empty_results() -> None:
    with pytest.raises(ValidationError):
        InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at=datetime(2026, 6, 8, 10, 5, tzinfo=UTC), results={})
