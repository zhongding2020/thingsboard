import json
from typing import Any, Protocol

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import StreamConfig

from process_opt.common.errors import PublishError
from process_opt.common.settings import Settings


class Publisher(Protocol):
    async def publish(self, subject: str, payload: dict[str, Any]) -> None: ...


class JetStreamPublisher:
    def __init__(self, settings: Settings, nc: NATS | None = None) -> None:
        self._settings = settings
        self._nc = nc
        self._js: JetStreamContext | None = None
        self._owns_connection = nc is None

    async def connect(self) -> None:
        if self._nc is None:
            self._nc = await nats.connect(self._settings.nats_url)
        self._js = self._nc.jetstream()
        await self._ensure_stream()

    async def publish(self, subject: str, payload: dict[str, Any]) -> None:
        if self._js is None:
            await self.connect()
        if self._js is None:
            raise PublishError("JetStream is not connected")
        try:
            await self._js.publish(subject, json.dumps(payload).encode(), stream=self._settings.nats_stream)
        except Exception as exc:
            raise PublishError("Failed to publish message") from exc

    async def close(self) -> None:
        if self._nc is not None and self._owns_connection:
            await self._nc.close()
        self._nc = None
        self._js = None

    async def _ensure_stream(self) -> None:
        if self._js is None:
            raise PublishError("JetStream is not connected")
        config = StreamConfig(
            name=self._settings.nats_stream,
            subjects=[self._settings.process_subject, self._settings.inspection_subject],
        )
        try:
            await self._js.add_stream(config=config)
        except Exception:
            await self._js.update_stream(config=config)
