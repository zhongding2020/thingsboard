import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from process_opt.common.db import apply_sql_file, create_pool
from process_opt.common.repositories import DataRepository
from process_opt.common.schemas import InspectionItem, InspectionMessage, ProcessMessage


@pytest.mark.asyncio
async def test_repository_upserts_and_returns_joined_analysis_record() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        await repo.upsert_process(
            ProcessMessage(
                message_id="m1",
                barcode="B1",
                device_id="D1",
                processed_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
                params={"temperature": 180},
            )
        )
        await repo.upsert_process(
            ProcessMessage(
                message_id="m2",
                barcode="B1",
                device_id="D2",
                processed_at=datetime(2026, 6, 8, 10, 1, tzinfo=UTC),
                params={"temperature": 181},
            )
        )
        await repo.upsert_inspection(
            InspectionMessage(
                message_id="m3",
                barcode="B1",
                station_id="QA1",
                inspected_at=datetime(2026, 6, 8, 10, 5, tzinfo=UTC),
                results={"diameter": 10.1},
            )
        )

        row = await repo.get_analysis_record("B1")
        assert row is not None
        assert row["barcode"] == "B1"
        assert row["device_id"] == "D2"
        assert row["params"]["temperature"] == 181
        assert row["results"]["diameter"] == 10.1
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_query_records_returns_paginated_results() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        await repo.upsert_process(
            ProcessMessage(
                message_id="m1", barcode="B1", device_id="reflow-oven",
                processed_at=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
                params={"temperature": 180, "speed": 50},
            )
        )
        await repo.upsert_process(
            ProcessMessage(
                message_id="m2", barcode="B2", device_id="reflow-oven",
                processed_at=datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
                params={"temperature": 190},
            )
        )
        await repo.upsert_inspection(
            InspectionMessage(
                message_id="m3", barcode="B1", station_id="QA1",
                inspected_at=datetime(2026, 6, 10, 8, 5, tzinfo=UTC),
                results={"solder": "pass"},
            )
        )

        # All records
        result = await repo.query_records(page=1, page_size=10)
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 10

        # Filter by barcode
        result = await repo.query_records(barcode="B1", page=1, page_size=10)
        assert result["total"] == 1
        assert result["items"][0]["barcode"] == "B1"
        assert result["items"][0]["params"] == {"temperature": 180, "speed": 50}
        assert result["items"][0]["results"] == {"solder": "pass"}

        # Filter by device_id
        await repo.upsert_process(
            ProcessMessage(
                message_id="m4", barcode="B3", device_id="injection-molder",
                processed_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
                params={"pressure": 100},
            )
        )
        result = await repo.query_records(device_id="injection-molder", page=1, page_size=10)
        assert result["total"] == 1
        assert result["items"][0]["device_id"] == "injection-molder"

        # Filter by time range
        result = await repo.query_records(
            start_time=datetime(2026, 6, 10, 8, 30, tzinfo=UTC),
            end_time=datetime(2026, 6, 10, 9, 30, tzinfo=UTC),
            page=1, page_size=10,
        )
        assert result["total"] == 1
        assert result["items"][0]["barcode"] == "B2"

        # Pagination
        result = await repo.query_records(page=1, page_size=1)
        assert len(result["items"]) == 1
        assert result["total"] == 3
        assert result["page"] == 1
        assert result["page_size"] == 1

        result = await repo.query_records(page=2, page_size=1)
        assert len(result["items"]) == 1
        assert result["total"] == 3

        # No match
        result = await repo.query_records(barcode="NONEXIST", page=1, page_size=10)
        assert result["total"] == 0
        assert result["items"] == []
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_query_records_empty_database_returns_empty_list() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        result = await repo.query_records(page=1, page_size=10)
        assert result["total"] == 0
        assert result["items"] == []
        assert result["page"] == 1
        assert result["page_size"] == 10
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_list_devices_returns_distinct_device_ids() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        await repo.upsert_process(
            ProcessMessage(
                message_id="m1", barcode="B1", device_id="reflow-oven",
                processed_at=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
                params={"t": 180},
            )
        )
        await repo.upsert_process(
            ProcessMessage(
                message_id="m2", barcode="B2", device_id="injection-molder",
                processed_at=datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
                params={"p": 100},
            )
        )
        # Same device_id again — should be deduplicated
        await repo.upsert_process(
            ProcessMessage(
                message_id="m3", barcode="B3", device_id="reflow-oven",
                processed_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
                params={"t": 190},
            )
        )

        devices = await repo.list_devices()
        assert sorted(devices) == ["injection-molder", "reflow-oven"]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_upsert_process_with_product_model() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        migration_004 = Path(__file__).parents[2] / "db" / "migrations" / "004_product_model.sql"
        await apply_sql_file(pool, migration_004)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        msg = ProcessMessage(
            message_id="pm1", barcode="PM-TEST-001", device_id="D1",
            processed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            product_model="A",
            params={"temp": 220},
        )
        await repo.upsert_process(msg)
        row = await repo.get_analysis_record("PM-TEST-001")
        assert row is not None
        assert row.get("process_product_model") == "A"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_upsert_inspection_with_items() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        migration_004 = Path(__file__).parents[2] / "db" / "migrations" / "004_product_model.sql"
        await apply_sql_file(pool, migration_004)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        msg = InspectionMessage(
            message_id="im1", barcode="IM-TEST-001", station_id="S1",
            inspected_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            product_model="B",
            results=[InspectionItem(name="voltage", value=5.0, result="pass", usl=10.0, lsl=0.0)],
        )
        await repo.upsert_inspection(msg)
        row = await repo.get_analysis_record("IM-TEST-001")
        assert row is not None
        assert row.get("inspection_product_model") == "B"
        assert isinstance(row["results"], list)
        assert row["results"][0]["name"] == "voltage"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_query_records_with_product_model() -> None:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        migration_004 = Path(__file__).parents[2] / "db" / "migrations" / "004_product_model.sql"
        await apply_sql_file(pool, migration_004)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results")

        repo = DataRepository(pool)
        proc_msg = ProcessMessage(
            message_id="q1", barcode="Q-TEST-001", device_id="D1",
            processed_at=datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC),
            product_model="A",
            params={"temp": 220},
        )
        await repo.upsert_process(proc_msg)
        insp_msg = InspectionMessage(
            message_id="q2", barcode="Q-TEST-001", station_id="S1",
            inspected_at=datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC),
            product_model="A",
            results=[InspectionItem(name="v", value=5.0, result="pass")],
        )
        await repo.upsert_inspection(insp_msg)

        result = await repo.query_records(product_model="A")
        assert len(result["items"]) > 0
        assert result["items"][0]["process_product_model"] == "A"
    finally:
        await pool.close()
