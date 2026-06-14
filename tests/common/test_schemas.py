from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from process_opt.common.schemas import InspectionItem, InspectionMessage, ProcessMessage


def test_process_message_accepts_required_fields() -> None:
    msg = ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC), params={"temperature": 180})
    assert msg.barcode == "B1"


def test_process_message_rejects_empty_params() -> None:
    with pytest.raises(ValidationError):
        ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC), params={})


def test_inspection_message_accepts_required_fields() -> None:
    msg = InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at=datetime(2026, 6, 8, 10, 5, tzinfo=UTC), results=[InspectionItem(name="diameter", value=10.2, result="pass")])
    assert msg.station_id == "QA1"


def test_inspection_message_rejects_empty_results() -> None:
    with pytest.raises(ValidationError):
        InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at=datetime(2026, 6, 8, 10, 5, tzinfo=UTC), results=[])


def test_inspection_item_valid() -> None:
    item = InspectionItem(name="voltage", value=5.0, result="pass", usl=10.0, lsl=0.0)
    assert item.name == "voltage"
    assert item.value == 5.0
    assert item.usl == 10.0


def test_inspection_item_invalid_result() -> None:
    with pytest.raises(ValidationError):
        InspectionItem(name="v", value=1.0, result="unknown")


def test_inspection_message_with_items() -> None:
    msg = InspectionMessage(
        message_id="m1", barcode="B001", station_id="S1",
        inspected_at=datetime(2026, 1, 1, 12, 0, 0),
        product_model="A",
        results=[
            InspectionItem(name="voltage", value=5.0, result="pass"),
        ],
    )
    assert msg.product_model == "A"
    assert len(msg.results) == 1


def test_process_message_with_product_model() -> None:
    msg = ProcessMessage(
        message_id="m1", barcode="B001", device_id="D1",
        processed_at=datetime(2026, 1, 1, 12, 0, 0),
        product_model="A",
        params={"temp": 220},
    )
    assert msg.product_model == "A"


def test_inspection_message_results_empty() -> None:
    with pytest.raises(ValidationError):
        InspectionMessage(
            message_id="m1", barcode="B001", station_id="S1",
            inspected_at=datetime(2026, 1, 1, 12, 0, 0),
            results=[],
        )


def test_inspection_message_to_json() -> None:
    msg = InspectionMessage(
        message_id="m1", barcode="B001", station_id="S1",
        inspected_at=datetime(2026, 1, 1, 12, 0, 0),
        results=[InspectionItem(name="v", value=5.0, result="pass")],
    )
    data = msg.model_dump(mode="json")
    assert isinstance(data["results"], list)
    assert data["results"][0]["name"] == "v"
    assert data["results"][0]["value"] == 5.0
