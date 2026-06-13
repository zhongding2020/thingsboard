import os
from pathlib import Path
from uuid import uuid4

import nats
import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.app import create_app as create_api_app
from process_opt.common.db import apply_sql_file, create_pool
from process_opt.common.nats_client import JetStreamPublisher
from process_opt.common.repositories import DataRepository
from process_opt.common.settings import Settings
from process_opt.consumer.handler import MessageHandler
from process_opt.consumer.worker import consume_pending_messages
from process_opt.gateway.app import create_app as create_gateway_app


@pytest.mark.asyncio
async def test_http_to_nats_to_database_to_query_api_pipeline() -> None:
    run_id = uuid4().hex
    stream = f"PROCESS_OPT_TEST_{run_id}"
    settings = Settings(
        postgres_dsn=os.environ.get(
            "PROCESS_OPT_TEST_POSTGRES_DSN",
            "postgresql://postgres:postgres@localhost:5432/process_opt",
        ),
        nats_url=os.environ.get("PROCESS_OPT_TEST_NATS_URL", "nats://localhost:4222"),
        nats_stream=stream,
        process_subject=f"process_data.{run_id}",
        inspection_subject=f"inspection_data.{run_id}",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(settings.postgres_dsn)
    publisher = JetStreamPublisher(settings)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        await publisher.connect()
        repo = DataRepository(pool)
        gateway_app = create_gateway_app(settings, publisher)
        process_payload = {
            "message_id": f"process-e2e-{run_id}",
            "barcode": f"E2E-{run_id}",
            "device_id": "D1",
            "processed_at": "2026-06-08T10:00:00Z",
            "params": {"temperature": 180},
        }
        inspection_payload = {
            "message_id": f"inspection-e2e-{run_id}",
            "barcode": f"E2E-{run_id}",
            "station_id": "QA1",
            "inspected_at": "2026-06-08T10:05:00Z",
            "results": {"diameter": 10.2},
        }

        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
            process_response = await client.post(
                "/api/v1/data/process",
                json=process_payload,
                headers={"X-API-Key": settings.gateway_api_key},
            )
            inspection_response = await client.post(
                "/api/v1/data/inspection",
                json=inspection_payload,
                headers={"X-API-Key": settings.gateway_api_key},
            )

        assert process_response.status_code == 202
        assert inspection_response.status_code == 202

        handler = MessageHandler(repo)
        handled = await consume_pending_messages(
            settings,
            handler,
            batch_size=10,
            durable_prefix=f"process-opt-{run_id}",
        )
        assert handled == 2

        api_app = create_api_app(repo)
        async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/analysis/records/E2E-{run_id}")

        assert response.status_code == 200
        assert response.json()["barcode"] == f"E2E-{run_id}"
        assert response.json()["device_id"] == "D1"
        assert response.json()["params"] == {"temperature": 180}
        assert response.json()["station_id"] == "QA1"
        assert response.json()["results"] == {"diameter": 10.2}
    finally:
        await publisher.close()
        nc = await nats.connect(settings.nats_url)
        try:
            js = nc.jetstream()
            await js.delete_stream(settings.nats_stream)
        finally:
            await nc.close()
        await pool.close()
