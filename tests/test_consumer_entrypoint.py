from typing import Any

import pytest

from process_opt.common.settings import Settings
from process_opt.consumer.main import run_once


class FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeRepository:
    def __init__(self, pool: FakePool) -> None:
        self.pool = pool


class FakeHandler:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository


@pytest.mark.asyncio
async def test_run_once_wires_consumer_dependencies_and_closes_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(postgres_dsn="postgresql://example/db")
    pool = FakePool()
    calls: dict[str, Any] = {}

    async def fake_create_pool(dsn: str) -> FakePool:
        calls["dsn"] = dsn
        return pool

    async def fake_consume_pending_messages(consumed_settings: Settings, handler: FakeHandler) -> int:
        calls["settings"] = consumed_settings
        calls["handler"] = handler
        return 7

    monkeypatch.setattr("process_opt.consumer.main.create_pool", fake_create_pool)
    monkeypatch.setattr("process_opt.consumer.main.DataRepository", FakeRepository)
    monkeypatch.setattr("process_opt.consumer.main.MessageHandler", FakeHandler)
    monkeypatch.setattr("process_opt.consumer.main.consume_pending_messages", fake_consume_pending_messages)

    handled = await run_once(settings)

    assert handled == 7
    assert calls["dsn"] == settings.postgres_dsn
    assert isinstance(calls["handler"], FakeHandler)
    assert calls["handler"].repository.pool is pool
    assert calls["settings"] is settings
    assert pool.closed
