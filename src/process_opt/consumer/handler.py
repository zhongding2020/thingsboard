import json
from collections.abc import Awaitable, Callable
from typing import TypeVar, Protocol

from pydantic import ValidationError

from process_opt.common.schemas import InspectionMessage, ProcessMessage


class RawMessage(Protocol):
    data: bytes

    def ack(self) -> Awaitable[None]: ...

    def nak(self) -> Awaitable[None]: ...

    def term(self) -> Awaitable[None]: ...


class Repository(Protocol):
    def upsert_process(self, message: ProcessMessage) -> Awaitable[None]: ...

    def upsert_inspection(self, message: InspectionMessage) -> Awaitable[None]: ...


MessageT = TypeVar("MessageT", ProcessMessage, InspectionMessage)


class MessageHandler:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    async def handle_process(self, raw_msg: RawMessage) -> None:
        await self._handle(raw_msg, ProcessMessage, self._repository.upsert_process)

    async def handle_inspection(self, raw_msg: RawMessage) -> None:
        await self._handle(raw_msg, InspectionMessage, self._repository.upsert_inspection)

    async def _handle(
        self,
        raw_msg: RawMessage,
        model_type: type[MessageT],
        upsert: Callable[[MessageT], Awaitable[None]],
    ) -> None:
        try:
            payload = json.loads(raw_msg.data.decode())
            message = model_type.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            await raw_msg.term()
            return

        try:
            await upsert(message)
        except Exception:
            await raw_msg.nak()
            return

        await raw_msg.ack()
