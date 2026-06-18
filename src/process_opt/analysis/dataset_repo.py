from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

from process_opt.analysis.schemas import AnalysisDataset


DEFAULT_TTL = 30  # minutes


class DatasetRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def initialize(self) -> None:
        pass  # Table created by init-db.sql

    async def save(self, dataset: AnalysisDataset, name: str = "", ttl: int = DEFAULT_TTL) -> str:
        data = dataset.model_dump_json()
        expires = datetime.now(timezone.utc) + timedelta(minutes=ttl)
        id_ = str(uuid.uuid4())
        await self.pool.execute(
            "INSERT INTO datasets (id, name, data, created_at, expires_at) VALUES ($1, $2, $3::jsonb, now(), $4)",
            id_, name, data, expires,
        )
        return id_

    async def get(self, dataset_id: str) -> AnalysisDataset | None:
        row = await self.pool.fetchrow(
            "SELECT data FROM datasets WHERE id = $1 AND expires_at > now()", dataset_id
        )
        if row is None:
            return None
        return AnalysisDataset.model_validate_json(row["data"])

    async def purge_expired(self) -> int:
        result = await self.pool.execute("DELETE FROM datasets WHERE expires_at <= now()")
        return int(result.split()[-1]) if result else 0
