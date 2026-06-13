import asyncio

from process_opt.common.db import create_pool
from process_opt.common.repositories import DataRepository
from process_opt.common.settings import Settings
from process_opt.consumer.handler import MessageHandler
from process_opt.consumer.worker import consume_pending_messages


async def run_once(settings: Settings) -> int:
    pool = await create_pool(settings.postgres_dsn)
    try:
        repository = DataRepository(pool)
        handler = MessageHandler(repository)
        return await consume_pending_messages(settings, handler, batch_size=500)
    finally:
        await pool.close()


async def _run_forever(settings: Settings, sleep_seconds: float = 1.0) -> None:
    while True:
        await run_once(settings)
        await asyncio.sleep(sleep_seconds)


def main() -> None:
    asyncio.run(_run_forever(Settings()))
