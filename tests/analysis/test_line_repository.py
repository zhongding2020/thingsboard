import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from process_opt.common.db import apply_sql_file, create_pool
from process_opt.common.repositories import LineDeviceRepository


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path_001 = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    migration_path_002 = Path(__file__).parents[2] / "db" / "migrations" / "002_lines_devices.sql"
    p = await create_pool(dsn)
    try:
        await apply_sql_file(p, migration_path_001)
        await apply_sql_file(p, migration_path_002)
        async with p.acquire() as connection:
            await connection.execute("TRUNCATE device_registry, production_lines CASCADE")
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def repo(pool: asyncpg.Pool) -> LineDeviceRepository:
    return LineDeviceRepository(pool)


class TestLineCRUD:
    @pytest.mark.asyncio
    async def test_create_and_list(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("测试线A", "测试工", "测试位置")
        assert line["name"] == "测试线A"
        assert line["responsible"] == "测试工"
        assert line["device_count"] == 0

        lines = await repo.list_lines()
        names = [l["name"] for l in lines]
        assert "测试线A" in names

    @pytest.mark.asyncio
    async def test_get_line(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("测试线B", "李工", None)
        fetched = await repo.get_line(line["id"])
        assert fetched is not None
        assert fetched["name"] == "测试线B"

    @pytest.mark.asyncio
    async def test_update_line(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("测试线C", "王工", "老位置")
        updated = await repo.update_line(line["id"], name="测试线C-改", responsible=None, location="新位置")
        assert updated is not None
        assert updated["name"] == "测试线C-改"
        assert updated["location"] == "新位置"
        assert updated["responsible"] == "王工"

    @pytest.mark.asyncio
    async def test_delete_line_without_devices(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("待删线", "赵工", None)
        ok = await repo.delete_line(line["id"])
        assert ok is True
        assert await repo.get_line(line["id"]) is None

    @pytest.mark.asyncio
    async def test_delete_line_with_devices_rejected(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("有线设备", "孙工", None)
        await repo.ensure_device_exists("test-dev-1", "tester")
        await repo.update_device("test-dev-1", None, None, None, None, line["id"])
        ok = await repo.delete_line(line["id"])
        assert ok is False


class TestDeviceCRUD:
    @pytest.mark.asyncio
    async def test_list_all_devices(self, repo: LineDeviceRepository) -> None:
        await repo.ensure_device_exists("test-dev-2", "tester")
        devices = await repo.list_devices()
        ids = [d["id"] for d in devices]
        assert "test-dev-2" in ids

    @pytest.mark.asyncio
    async def test_list_devices_by_line(self, repo: LineDeviceRepository) -> None:
        line = await repo.create_line("设备管理线", "周工", None)
        await repo.ensure_device_exists("test-dev-3", "tester")
        await repo.update_device("test-dev-3", None, None, None, None, line["id"])
        devices = await repo.list_devices(line_id=line["id"])
        assert any(d["id"] == "test-dev-3" for d in devices)

    @pytest.mark.asyncio
    async def test_update_device(self, repo: LineDeviceRepository) -> None:
        await repo.ensure_device_exists("test-dev-4", "tester")
        updated = await repo.update_device("test-dev-4", "改名设备", "new-type", "Cpu", "描述", None)
        assert updated is not None
        assert updated["name"] == "改名设备"
        assert updated["type"] == "new-type"
        assert updated["icon"] == "Cpu"

    @pytest.mark.asyncio
    async def test_delete_device(self, repo: LineDeviceRepository) -> None:
        await repo.ensure_device_exists("test-dev-5", "tester")
        ok = await repo.delete_device("test-dev-5")
        assert ok is True
        assert await repo.get_device("test-dev-5") is None

    @pytest.mark.asyncio
    async def test_ensure_device_exists_idempotent(self, repo: LineDeviceRepository) -> None:
        await repo.ensure_device_exists("test-dev-6", "tester")
        await repo.ensure_device_exists("test-dev-6", "tester")
        device = await repo.get_device("test-dev-6")
        assert device is not None
        assert device["type"] == "tester"
