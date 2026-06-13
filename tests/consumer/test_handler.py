import json
from typing import Any

import pytest

from process_opt.common.schemas import InspectionMessage, ProcessMessage
from process_opt.consumer.handler import MessageHandler


class FakeMessage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.acked = False
        self.naked = False
        self.termed = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self) -> None:
        self.naked = True

    async def term(self) -> None:
        self.termed = True


class FakeRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.process_calls: list[ProcessMessage] = []
        self.inspection_calls: list[InspectionMessage] = []

    async def upsert_process(self, message: ProcessMessage) -> None:
        if self.fail:
            raise RuntimeError("repository failure")
        self.process_calls.append(message)

    async def upsert_inspection(self, message: InspectionMessage) -> None:
        if self.fail:
            raise RuntimeError("repository failure")
        self.inspection_calls.append(message)


def encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode()


@pytest.mark.asyncio
async def test_handle_process_message_upserts_and_acks() -> None:
    repo = FakeRepository()
    handler = MessageHandler(repo)
    raw_msg = FakeMessage(
        encode(
            {
                "message_id": "m1",
                "barcode": "B1",
                "device_id": "D1",
                "processed_at": "2026-06-08T10:00:00Z",
                "params": {"temperature": 180},
            }
        )
    )

    await handler.handle_process(raw_msg)

    assert len(repo.process_calls) == 1
    assert repo.process_calls[0].barcode == "B1"
    assert raw_msg.acked is True
    assert raw_msg.naked is False
    assert raw_msg.termed is False


@pytest.mark.asyncio
async def test_handle_inspection_message_upserts_and_acks() -> None:
    repo = FakeRepository()
    handler = MessageHandler(repo)
    raw_msg = FakeMessage(
        encode(
            {
                "message_id": "m2",
                "barcode": "B1",
                "station_id": "QA1",
                "inspected_at": "2026-06-08T10:05:00Z",
                "results": {"diameter": 10.2},
            }
        )
    )

    await handler.handle_inspection(raw_msg)

    assert len(repo.inspection_calls) == 1
    assert repo.inspection_calls[0].station_id == "QA1"
    assert raw_msg.acked is True
    assert raw_msg.naked is False
    assert raw_msg.termed is False


@pytest.mark.asyncio
async def test_invalid_json_naks_or_terms_message() -> None:
    repo = FakeRepository()
    handler = MessageHandler(repo)
    raw_msg = FakeMessage(b"not json")

    await handler.handle_process(raw_msg)

    assert repo.process_calls == []
    assert raw_msg.acked is False
    assert raw_msg.naked or raw_msg.termed


@pytest.mark.asyncio
async def test_repository_failure_does_not_ack() -> None:
    repo = FakeRepository(fail=True)
    handler = MessageHandler(repo)
    raw_msg = FakeMessage(
        encode(
            {
                "message_id": "m1",
                "barcode": "B1",
                "device_id": "D1",
                "processed_at": "2026-06-08T10:00:00Z",
                "params": {"temperature": 180},
            }
        )
    )

    await handler.handle_process(raw_msg)

    assert raw_msg.acked is False
