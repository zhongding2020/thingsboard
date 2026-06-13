from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.main import create_api_app_from_settings
from process_opt.common.db import apply_sql_file
from process_opt.common.schemas import InspectionMessage, ProcessMessage


@pytest.mark.asyncio
async def test_analysis_profile_returns_field_list() -> None:
    run_id = uuid4().hex
    barcode = f"INTG-{run_id}"
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"

    app = create_api_app_from_settings()

    async with app.router.lifespan_context(app):
        pool = app.state.pool
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as conn:
            for table in ["inspection_results", "process_summary"]:
                await conn.execute(f"DELETE FROM {table}")

        repo = app.state.repository

        await repo.upsert_process(ProcessMessage(
            message_id=f"msg-{run_id}",
            barcode=barcode,
            device_id="D1",
            processed_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
            params={"temperature": 180, "pressure": 5.0},
        ))
        await repo.upsert_inspection(InspectionMessage(
            message_id=f"ins-{run_id}",
            barcode=barcode,
            station_id="QA1",
            inspected_at=datetime(2026, 6, 13, 10, 5, tzinfo=UTC),
            results={"diameter": 10.2, "thickness": 2.5},
        ))

        dataset = {
            "feature_fields": ["temperature", "pressure"],
            "target_fields": ["diameter", "thickness"],
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/analysis/profile", json=dataset)

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        fields = {item["field"] for item in data}
        assert fields == {"temperature", "pressure", "diameter", "thickness"}
