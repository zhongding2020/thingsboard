import json
from pathlib import Path
from typing import TypeAlias

import asyncpg

Pool: TypeAlias = asyncpg.Pool


async def _init_connection(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
        format="text",
    )


async def create_pool(dsn: str) -> Pool:
    return await asyncpg.create_pool(dsn=dsn, init=_init_connection)


async def apply_sql_file(pool: Pool, path: Path) -> None:
    sql = path.read_text()
    async with pool.acquire() as connection:
        await connection.execute(sql)
