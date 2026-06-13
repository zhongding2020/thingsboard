import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from process_opt.common.db import apply_sql_file, create_pool
from process_opt.parameters.repository import ParameterRepository
from process_opt.parameters.schemas import ParameterItemCreate, ParameterSetCreate, ParameterStatus


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute(
                """
                TRUNCATE
                  parameter_confirmations,
                  parameter_set_events,
                  parameter_items,
                  parameter_sets
                RESTART IDENTITY
                """
            )
        yield pool
    finally:
        await pool.close()


@pytest.fixture
def parameter_create() -> ParameterSetCreate:
    return ParameterSetCreate(
        name="Line A defaults",
        device_type="soldering-oven",
        source="engineering",
        created_by="alice",
        note="initial rollout",
        items=[
            ParameterItemCreate(
                param_key="temperature",
                param_value=180,
                unit="C",
                data_type="number",
                min_value=150,
                max_value=220,
                description="Peak temperature",
            ),
            ParameterItemCreate(
                param_key="profile",
                param_value={"ramp": "slow"},
                data_type="object",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_create_set_stores_draft_parameter_set_with_items(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)

    created = await repo.create_set(parameter_create)
    loaded = await repo.get_set(created.id)
    items = await repo.list_items(created.id)

    assert loaded == created
    assert created.version == 1
    assert created.status == ParameterStatus.DRAFT
    assert len(items) == 2
    assert items[0].param_key == "temperature"
    assert items[0].param_value == 180
    assert items[1].param_key == "profile"
    assert items[1].param_value == {"ramp": "slow"}


@pytest.mark.asyncio
async def test_next_version_increments_for_same_device_type(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)

    first = await repo.create_set(parameter_create)
    second = await repo.create_set(parameter_create.model_copy(update={"name": "Line A defaults v2"}))

    assert first.version == 1
    assert second.version == 2
    assert await repo.next_version("soldering-oven") == 3


@pytest.mark.asyncio
async def test_add_event_records_lifecycle_events(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    created = await repo.create_set(parameter_create)

    for event_type in ["create", "submit", "approve", "activate", "archive"]:
        await repo.add_event(created.id, event_type, actor="alice", note=f"{event_type} note")

    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT event_type, actor, note
            FROM parameter_set_events
            WHERE set_id = $1
            ORDER BY id
            """,
            created.id,
        )

    assert [row["event_type"] for row in rows] == ["create", "submit", "approve", "activate", "archive"]
    assert all(row["actor"] == "alice" for row in rows)
    assert rows[2]["note"] == "approve note"


@pytest.mark.asyncio
async def test_insert_confirmation_records_fetch_apply_and_failure(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    created = await repo.create_set(parameter_create)

    for status in ["fetched", "applied", "failed"]:
        await repo.insert_confirmation(
            device_id="oven-1",
            device_type="soldering-oven",
            parameter_set_id=created.id,
            parameter_version=created.version,
            status=status,
            message=f"{status} message",
        )

    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT device_id, device_type, parameter_set_id, parameter_version, status, message
            FROM parameter_confirmations
            ORDER BY id
            """
        )

    assert [row["status"] for row in rows] == ["fetched", "applied", "failed"]
    assert all(row["device_id"] == "oven-1" for row in rows)
    assert rows[2]["message"] == "failed message"


@pytest.mark.asyncio
async def test_get_latest_active_returns_active_set_for_device_type(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    created = await repo.create_set(parameter_create)
    await repo.update_status(created.id, ParameterStatus.APPROVED, actor="bob")
    await repo.update_status(created.id, ParameterStatus.ACTIVE, actor="carol")

    active = await repo.get_latest_active("soldering-oven")

    assert active is not None
    assert active.id == created.id
    assert active.status == ParameterStatus.ACTIVE
