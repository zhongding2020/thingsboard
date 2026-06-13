from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import asyncpg
import pytest
import pytest_asyncio

from process_opt.common.db import apply_sql_file, create_pool
from process_opt.parameters.errors import InvalidTransitionError
from process_opt.parameters.repository import ParameterRepository
from process_opt.parameters.schemas import (
    ParameterItemCreate,
    ParameterSetCreate,
    ParameterStatus,
)
from process_opt.parameters.service import ParameterService


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
async def test_create_draft_creates_draft_set_with_create_event(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)

    draft = await service.create_draft(parameter_create)

    assert draft.status == ParameterStatus.DRAFT
    assert draft.version == 1

    async with pool.acquire() as connection:
        events = await connection.fetch(
            "SELECT event_type, actor FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            draft.id,
        )
    assert len(events) == 1
    assert events[0]["event_type"] == "create"
    assert events[0]["actor"] == "alice"


@pytest.mark.asyncio
async def test_submit_transitions_draft_to_proposed(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)

    proposed = await service.submit(draft.id, actor="alice", note="ready for review")

    assert proposed.status == ParameterStatus.PROPOSED

    async with pool.acquire() as connection:
        events = await connection.fetch(
            "SELECT event_type, actor FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            draft.id,
        )
    assert [row["event_type"] for row in events] == ["create", "submit"]


@pytest.mark.asyncio
async def test_approve_transitions_proposed_to_approved(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")

    approved = await service.approve(draft.id, actor="bob", note="looks good")

    assert approved.status == ParameterStatus.APPROVED
    assert approved.approved_by == "bob"

    async with pool.acquire() as connection:
        events = await connection.fetch(
            "SELECT event_type, actor FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            draft.id,
        )
    assert [row["event_type"] for row in events] == ["create", "submit", "approve"]


@pytest.mark.asyncio
async def test_reject_transitions_proposed_to_rejected(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")

    rejected = await service.reject(draft.id, actor="bob", note="wrong values")

    assert rejected.status == ParameterStatus.REJECTED

    async with pool.acquire() as connection:
        events = await connection.fetch(
            "SELECT event_type, actor FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            draft.id,
        )
    assert [row["event_type"] for row in events] == ["create", "submit", "reject"]


@pytest.mark.asyncio
async def test_activate_archives_old_active_and_activates_new(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")
    first = await service.approve(draft.id, actor="bob")
    activated1 = await service.activate(first.id, actor="carol")

    assert activated1.status == ParameterStatus.ACTIVE

    draft2 = await service.create_draft(parameter_create.model_copy(update={"name": "Line A v2"}))
    await service.submit(draft2.id, actor="alice")
    second = await service.approve(draft2.id, actor="bob")
    activated2 = await service.activate(second.id, actor="carol")

    assert activated2.status == ParameterStatus.ACTIVE

    async with pool.acquire() as connection:
        old_row = await connection.fetchrow(
            "SELECT status FROM parameter_sets WHERE id = $1",
            first.id,
        )
    assert old_row["status"] == ParameterStatus.ARCHIVED.value

    async with pool.acquire() as connection:
        old_events = await connection.fetch(
            "SELECT event_type FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            first.id,
        )
    assert old_events[-1]["event_type"] == "archive"

    async with pool.acquire() as connection:
        new_events = await connection.fetch(
            "SELECT event_type FROM parameter_set_events WHERE set_id = $1 ORDER BY id",
            second.id,
        )
    assert new_events[-1]["event_type"] == "activate"


@pytest.mark.asyncio
async def test_get_latest_returns_active_set_with_items_and_checksum(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")
    approved = await service.approve(draft.id, actor="bob")
    await service.activate(approved.id, actor="carol")

    result = await service.get_latest("soldering-oven")

    assert result is not None
    assert result.parameter_set.status == ParameterStatus.ACTIVE
    assert len(result.items) == 2
    assert result.items[0].param_key == "temperature"
    assert result.items[0].param_value == 180
    assert isinstance(result.checksum, str)
    assert len(result.checksum) == 32


@pytest.mark.asyncio
async def test_get_latest_checksum_matches_md5_of_items_json(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")
    approved = await service.approve(draft.id, actor="bob")
    await service.activate(approved.id, actor="carol")

    result = await service.get_latest("soldering-oven")
    assert result is not None

    item_dicts = [item.model_dump(mode="json") for item in result.items]
    expected = hashlib.md5(
        json.dumps(item_dicts, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()
    assert result.checksum == expected


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_no_active_set(
    pool: asyncpg.Pool,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)

    result = await service.get_latest("nonexistent-device")

    assert result is None


@pytest.mark.asyncio
async def test_record_confirmation_persists_device_confirmation(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)
    await service.submit(draft.id, actor="alice")
    approved = await service.approve(draft.id, actor="bob")
    activated = await service.activate(approved.id, actor="carol")

    await service.record_confirmation(
        device_id="oven-1",
        device_type="soldering-oven",
        parameter_set_id=activated.id,
        parameter_version=activated.version,
        status="applied",
        message="applied successfully",
    )

    async with pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT status FROM parameter_confirmations WHERE device_id = $1",
            "oven-1",
        )
    assert len(rows) == 1
    assert rows[0]["status"] == "applied"


@pytest.mark.asyncio
async def test_invalid_transition_raises_invalid_transition_error(
    pool: asyncpg.Pool,
    parameter_create: ParameterSetCreate,
) -> None:
    repo = ParameterRepository(pool)
    service = ParameterService(repo)
    draft = await service.create_draft(parameter_create)

    with pytest.raises(InvalidTransitionError) as exc_info:
        await service.approve(draft.id, actor="bob")

    assert exc_info.value.code == "INVALID_TRANSITION"
