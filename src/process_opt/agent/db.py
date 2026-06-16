from __future__ import annotations

"""Helper for agent-generated code to query production data."""


def query(sql: str) -> list[dict]:
    """Execute SQL query against the production database."""
    import asyncio
    import os

    import asyncpg

    dsn = os.environ.get(
        "PROCESS_OPT_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )

    async def _run():
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(sql)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_run())
