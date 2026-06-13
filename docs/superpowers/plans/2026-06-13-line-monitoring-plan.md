# Line Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production line management, device registry, and line-level SPC monitoring to the existing process optimization platform.

**Architecture:** New PostgreSQL tables `production_lines` and `device_registry` with FK relationships; new `LineDeviceRepository` for CRUD; new `/lines` and `/devices` API routes; new `LinesView` and `LineDetailView` frontend pages; enhanced `SpcView` with line-context breadcrumb; sidebar menu restructured.

**Tech Stack:** PostgreSQL (asyncpg), FastAPI, Pydantic, Vue 3 + Element Plus + TypeScript, Pinia, axios

---

## File Structure Map

```
New files:
  db/migrations/002_lines_devices.sql          — DDL for production_lines + device_registry
  src/process_opt/analysis/line_schemas.py     — Pydantic models for lines/devices
  tests/analysis/test_line_schemas.py          — schema validation tests
  tests/analysis/test_line_repository.py       — repository CRUD tests
  tests/api/test_lines_api.py                  — HTTP API integration tests
  web/src/api/lines.ts                         — frontend API client
  web/src/views/LinesView.vue                  — line list + management page
  web/src/views/LineDetailView.vue             — line detail + device list page

Modified files:
  src/process_opt/analysis/schemas.py:127-132  — SpcRequest add line_id
  src/process_opt/analysis/service.py:100-136  — spc() filtering logic
  src/process_opt/analysis/dataset.py:18-28    — DatasetBuilder add device_id/since filter
  src/process_opt/common/repositories.py       — add LineDeviceRepository class
  src/process_opt/api/app.py                   — register line/device routes + monitor
  src/process_opt/api/main.py                  — pass LineDeviceRepository to create_app
  web/src/router/index.ts                      — add /lines, /lines/:id routes
  web/src/components/AppLayout.vue             — change menu item label, add line sub-items
  web/src/views/SpcView.vue                    — breadcrumb, device info bar, line-scoped
  src/process_opt/mock/generator.py            — query/register device_registry
```

---

### Task 1: Create SQL migration file

**Files:**
- Create: `db/migrations/002_lines_devices.sql`

- [ ] **Step 1: Write migration SQL**

```sql
CREATE TABLE IF NOT EXISTS production_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  responsible TEXT NOT NULL,
  location TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS device_registry (
  id TEXT PRIMARY KEY,
  line_id UUID REFERENCES production_lines(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  icon TEXT,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO production_lines (name, responsible, location)
VALUES ('默认产线', '管理员', '未分配')
ON CONFLICT (name) DO NOTHING;

INSERT INTO device_registry (id, line_id, name, type, icon, description)
SELECT DISTINCT
  ps.device_id,
  (SELECT id FROM production_lines WHERE name = '默认产线'),
  ps.device_id,
  ps.device_id,
  'Monitor',
  '自动从历史数据回填'
FROM process_summary ps
WHERE NOT EXISTS (SELECT 1 FROM device_registry dr WHERE dr.id = ps.device_id);
```

- [ ] **Step 2: Verify migration applies cleanly**

Run: `docker compose -f docker-compose.yml up -d postgres && sleep 3 && docker exec thingsboard-postgres-1 psql -U postgres -d process_opt -f - < db/migrations/002_lines_devices.sql`

Expected: `CREATE TABLE` × 2, `INSERT 0 1`, `INSERT 0 N` (N = distinct device_ids)

- [ ] **Step 3: Commit**

```bash
git add db/migrations/002_lines_devices.sql
git commit -m "feat: add production_lines and device_registry tables"
```

---

### Task 2: Apply migration on startup

**Files:**
- Modify: `src/process_opt/api/main.py`

- [ ] **Step 1: Add migration runner in main.py**

The `main()` function in `src/process_opt/api/main.py` should apply migrations before creating the app. Read current `main.py`:

```python
# existing imports
from process_opt.common.db import create_pool, apply_sql_file

async def main() -> None:
    settings = Settings()
    pool = await create_pool(settings.postgres_dsn)
    try:
        # Apply migration
        migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"
        for fpath in sorted(migrations_dir.glob("*.sql")):
            await apply_sql_file(pool, fpath)

        repository = DataRepository(pool)
        ...
```

The migration files are applied in sorted order (001_initial.sql first, then 002_lines_devices.sql). The `apply_sql_file` function already exists in `db.py` and executes raw SQL.

- [ ] **Step 2: Verify by restarting backend-api**

Run: `docker compose -f docker-compose.yml up -d --build backend-api && sleep 5 && docker exec thingsboard-postgres-1 psql -U postgres -d process_opt -c "\dt production_lines"`

Expected: Table `production_lines` exists and contains "默认产线".

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/api/main.py
git commit -m "feat: apply DB migrations on backend startup"
```

---

### Task 3: Create Pydantic schemas for lines and devices

**Files:**
- Create: `src/process_opt/analysis/line_schemas.py`

- [ ] **Step 1: Write the schemas**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    responsible: str = Field(min_length=1)
    location: str | None = None


class LineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1)
    responsible: str | None = Field(default=None, min_length=1)
    location: str | None = None


class LineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    responsible: str
    location: str | None
    device_count: int
    created_at: datetime
    updated_at: datetime


class DeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    line_id: str | None
    line_name: str | None
    name: str
    type: str
    icon: str | None
    description: str | None


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    icon: str | None = None
    description: str | None = None
    line_id: str | None = None


class LineDetailResponse(LineResponse):
    devices: list[DeviceResponse]


class DeviceSpcSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    device_name: str
    type: str
    status: str  # normal | marginal | abnormal | no_spec
    worst_cpk: float | None
    param_count: int
    outlier_total: int


class LineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_count: int
    normal_count: int
    abnormal_count: int
    marginal_count: int
    no_spec_count: int
    status: str  # abnormal > marginal > no_spec > normal > empty


class LineMonitorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: LineResponse
    summary: LineSummary
    devices: list[DeviceSpcSummary]
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/analysis/line_schemas.py
git commit -m "feat: add line and device Pydantic schemas"
```

---

### Task 4: Write schema tests

**Files:**
- Create: `tests/analysis/test_line_schemas.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from pydantic import ValidationError
from process_opt.analysis.line_schemas import (
    LineCreate, LineUpdate, LineResponse, DeviceResponse,
    DeviceUpdate, LineDetailResponse, DeviceSpcSummary,
    LineSummary, LineMonitorResponse,
)
from datetime import datetime, timezone


class TestLineCreate:
    def test_valid_line(self):
        lc = LineCreate(name="SMT-01", responsible="张工", location="A栋2层")
        assert lc.name == "SMT-01"
        assert lc.responsible == "张工"
        assert lc.location == "A栋2层"

    def test_location_optional(self):
        lc = LineCreate(name="SMT-01", responsible="张工")
        assert lc.location is None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            LineCreate(name="", responsible="张工")

    def test_empty_responsible_rejected(self):
        with pytest.raises(ValidationError):
            LineCreate(name="SMT-01", responsible="")


class TestLineUpdate:
    def test_all_fields_optional(self):
        lu = LineUpdate()
        assert lu.name is None
        assert lu.responsible is None
        assert lu.location is None

    def test_partial_update(self):
        lu = LineUpdate(name="新名称")
        assert lu.name == "新名称"
        assert lu.responsible is None


class TestLineResponse:
    def test_serialization(self):
        now = datetime.now(timezone.utc)
        lr = LineResponse(
            id="uuid-1", name="SMT-01", responsible="张工",
            location="A栋", device_count=3,
            created_at=now, updated_at=now,
        )
        d = lr.model_dump()
        assert d["id"] == "uuid-1"
        assert d["device_count"] == 3


class TestDeviceUpdate:
    def test_update_line_assignment(self):
        du = DeviceUpdate(line_id="line-1")
        assert du.line_id == "line-1"
        assert du.name is None


class TestLineMonitorResponse:
    def test_valid_response(self):
        now = datetime.now(timezone.utc)
        line = LineResponse(
            id="l1", name="SMT-01", responsible="张工",
            location=None, device_count=2,
            created_at=now, updated_at=now,
        )
        summary = LineSummary(
            device_count=2, normal_count=1, abnormal_count=1,
            marginal_count=0, no_spec_count=0, status="abnormal",
        )
        devices = [
            DeviceSpcSummary(
                device_id="d1", device_name="回流焊-01",
                type="reflow-oven", status="normal",
                worst_cpk=1.5, param_count=3, outlier_total=2,
            ),
            DeviceSpcSummary(
                device_id="d2", device_name="贴片机-03",
                type="pick-and-place", status="abnormal",
                worst_cpk=0.8, param_count=2, outlier_total=12,
            ),
        ]
        resp = LineMonitorResponse(line=line, summary=summary, devices=devices)
        assert resp.summary.status == "abnormal"
        assert len(resp.devices) == 2
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/analysis/test_line_schemas.py -v`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add tests/analysis/test_line_schemas.py
git commit -m "test: add line and device schema tests"
```

---

### Task 5: Add LineDeviceRepository

**Files:**
- Modify: `src/process_opt/common/repositories.py` (append at end)

- [ ] **Step 1: Add LineDeviceRepository class**

```python
class LineDeviceRepository:
    """Repository for production_lines and device_registry tables."""

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def list_lines(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT l.id, l.name, l.responsible, l.location,
                       l.created_at, l.updated_at,
                       COUNT(d.id) AS device_count
                FROM production_lines l
                LEFT JOIN device_registry d ON d.line_id = l.id
                GROUP BY l.id
                ORDER BY l.name
            """)
        return [dict(r) for r in rows]

    async def get_line(self, line_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT l.id, l.name, l.responsible, l.location,
                       l.created_at, l.updated_at,
                       COUNT(d.id) AS device_count
                FROM production_lines l
                LEFT JOIN device_registry d ON d.line_id = l.id
                WHERE l.id = $1
                GROUP BY l.id
            """, line_id)
        return dict(row) if row else None

    async def create_line(self, name: str, responsible: str, location: str | None) -> dict[str, Any]:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                INSERT INTO production_lines (name, responsible, location)
                VALUES ($1, $2, $3)
                RETURNING id, name, responsible, location, created_at, updated_at
            """, name, responsible, location)
        result = dict(row)
        result["device_count"] = 0
        return result

    async def update_line(self, line_id: str, name: str | None,
                          responsible: str | None, location: str | None) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = [line_id]
        idx = 2
        if name is not None:
            fields.append(f"name = ${idx}")
            params.append(name)
            idx += 1
        if responsible is not None:
            fields.append(f"responsible = ${idx}")
            params.append(responsible)
            idx += 1
        if location is not None:
            fields.append(f"location = ${idx}")
            params.append(location)
            idx += 1
        if not fields:
            return await self.get_line(line_id)
        fields.append("updated_at = now()")
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(f"""
                UPDATE production_lines
                SET {', '.join(fields)}
                WHERE id = $1
                RETURNING id, name, responsible, location, created_at, updated_at
            """, *params)
        if row is None:
            return None
        result = await self.get_line(line_id)
        return result

    async def delete_line(self, line_id: str) -> bool:
        async with self._pool.acquire() as connection:
            device_count = await connection.fetchval(
                "SELECT COUNT(*) FROM device_registry WHERE line_id = $1", line_id
            )
            if device_count and device_count > 0:
                return False
            result = await connection.execute(
                "DELETE FROM production_lines WHERE id = $1", line_id
            )
        return result != "DELETE 0"

    async def list_devices(self, line_id: str | None = None) -> list[dict[str, Any]]:
        async with self._pool.acquire() as connection:
            if line_id is not None:
                rows = await connection.fetch("""
                    SELECT d.id, d.line_id, l.name AS line_name,
                           d.name, d.type, d.icon, d.description
                    FROM device_registry d
                    LEFT JOIN production_lines l ON l.id = d.line_id
                    WHERE d.line_id = $1
                    ORDER BY d.name
                """, line_id)
            else:
                rows = await connection.fetch("""
                    SELECT d.id, d.line_id, l.name AS line_name,
                           d.name, d.type, d.icon, d.description
                    FROM device_registry d
                    LEFT JOIN production_lines l ON l.id = d.line_id
                    ORDER BY d.name
                """)
        return [dict(r) for r in rows]

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT d.id, d.line_id, l.name AS line_name,
                       d.name, d.type, d.icon, d.description
                FROM device_registry d
                LEFT JOIN production_lines l ON l.id = d.line_id
                WHERE d.id = $1
            """, device_id)
        return dict(row) if row else None

    async def update_device(self, device_id: str, name: str | None, type_: str | None,
                            icon: str | None, description: str | None,
                            line_id: str | None) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = [device_id]
        idx = 2
        if name is not None:
            fields.append(f"name = ${idx}")
            params.append(name)
            idx += 1
        if type_ is not None:
            fields.append(f"type = ${idx}")
            params.append(type_)
            idx += 1
        if icon is not None:
            fields.append(f"icon = ${idx}")
            params.append(icon)
            idx += 1
        if description is not None:
            fields.append(f"description = ${idx}")
            params.append(description)
            idx += 1
        if line_id is not None:
            fields.append(f"line_id = ${idx}")
            params.append(line_id)
            idx += 1
        if not fields:
            return await self.get_device(device_id)
        fields.append("updated_at = now()")
        async with self._pool.acquire() as connection:
            await connection.execute(f"""
                UPDATE device_registry SET {', '.join(fields)} WHERE id = $1
            """, *params)
        return await self.get_device(device_id)

    async def delete_device(self, device_id: str) -> bool:
        async with self._pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM device_registry WHERE id = $1", device_id
            )
        return result != "DELETE 0"

    async def get_devices_by_line(self, line_id: str) -> list[str]:
        """Return device IDs for a line. Used by SPC filtering."""
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT id FROM device_registry WHERE line_id = $1 ORDER BY id",
                line_id,
            )
        return [r["id"] for r in rows]

    async def ensure_device_exists(self, device_id: str, device_type: str) -> None:
        """Idempotent device registration for mock generator."""
        async with self._pool.acquire() as connection:
            await connection.execute("""
                INSERT INTO device_registry (id, line_id, name, type, icon, description)
                VALUES ($1, (SELECT id FROM production_lines WHERE name = '默认产线'),
                        $1, $2, 'Monitor', '自动注册')
                ON CONFLICT (id) DO NOTHING
            """, device_id, device_type)
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/common/repositories.py
git commit -m "feat: add LineDeviceRepository for line and device CRUD"
```

---

### Task 6: Write LineDeviceRepository tests

**Files:**
- Create: `tests/analysis/test_line_repository.py`

- [ ] **Step 1: Write repository tests**

```python
import pytest
from process_opt.common.db import create_pool
from process_opt.common.repositories import LineDeviceRepository


@pytest.fixture
async def pool():
    p = await create_pool("postgresql://postgres:postgres@localhost:5432/process_opt")
    yield p
    await p.close()


@pytest.fixture
async def repo(pool):
    r = LineDeviceRepository(pool)
    # Ensure tables exist by applying migration
    from pathlib import Path
    from process_opt.common.db import apply_sql_file
    migration = Path(__file__).parent.parent.parent / "db" / "migrations" / "002_lines_devices.sql"
    await apply_sql_file(pool, migration)
    return r


class TestLineCRUD:
    @pytest.mark.anyio
    async def test_create_and_list(self, repo):
        line = await repo.create_line("测试线A", "测试工", "测试位置")
        assert line["name"] == "测试线A"
        assert line["responsible"] == "测试工"
        assert line["device_count"] == 0

        lines = await repo.list_lines()
        names = [l["name"] for l in lines]
        assert "测试线A" in names

    @pytest.mark.anyio
    async def test_get_line(self, repo):
        line = await repo.create_line("测试线B", "李工", None)
        fetched = await repo.get_line(line["id"])
        assert fetched is not None
        assert fetched["name"] == "测试线B"

    @pytest.mark.anyio
    async def test_update_line(self, repo):
        line = await repo.create_line("测试线C", "王工", "老位置")
        updated = await repo.update_line(line["id"], name="测试线C-改", responsible=None, location="新位置")
        assert updated is not None
        assert updated["name"] == "测试线C-改"
        assert updated["location"] == "新位置"
        assert updated["responsible"] == "王工"  # unchanged

    @pytest.mark.anyio
    async def test_delete_line_without_devices(self, repo):
        line = await repo.create_line("待删线", "赵工", None)
        ok = await repo.delete_line(line["id"])
        assert ok is True
        assert await repo.get_line(line["id"]) is None

    @pytest.mark.anyio
    async def test_delete_line_with_devices_rejected(self, repo):
        line = await repo.create_line("有线设备", "孙工", None)
        await repo.ensure_device_exists("test-dev-1", "tester")
        await repo.update_device("test-dev-1", None, None, None, None, line["id"])
        ok = await repo.delete_line(line["id"])
        assert ok is False  # blocked because device assigned


class TestDeviceCRUD:
    @pytest.mark.anyio
    async def test_list_all_devices(self, repo):
        await repo.ensure_device_exists("test-dev-2", "tester")
        devices = await repo.list_devices()
        ids = [d["id"] for d in devices]
        assert "test-dev-2" in ids

    @pytest.mark.anyio
    async def test_list_devices_by_line(self, repo):
        line = await repo.create_line("设备管理线", "周工", None)
        await repo.ensure_device_exists("test-dev-3", "tester")
        await repo.update_device("test-dev-3", None, None, None, None, line["id"])
        devices = await repo.list_devices(line_id=line["id"])
        assert any(d["id"] == "test-dev-3" for d in devices)

    @pytest.mark.anyio
    async def test_update_device(self, repo):
        await repo.ensure_device_exists("test-dev-4", "tester")
        updated = await repo.update_device("test-dev-4", "改名设备", "new-type", "Cpu", "描述", None)
        assert updated is not None
        assert updated["name"] == "改名设备"
        assert updated["type"] == "new-type"
        assert updated["icon"] == "Cpu"

    @pytest.mark.anyio
    async def test_delete_device(self, repo):
        await repo.ensure_device_exists("test-dev-5", "tester")
        ok = await repo.delete_device("test-dev-5")
        assert ok is True
        assert await repo.get_device("test-dev-5") is None

    @pytest.mark.anyio
    async def test_ensure_device_exists_idempotent(self, repo):
        await repo.ensure_device_exists("test-dev-6", "tester")
        await repo.ensure_device_exists("test-dev-6", "tester")  # should not raise
        device = await repo.get_device("test-dev-6")
        assert device is not None
        assert device["type"] == "tester"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/analysis/test_line_repository.py -v`
Expected: 10 passed

- [ ] **Step 3: Commit**

```bash
git add tests/analysis/test_line_repository.py
git commit -m "test: add LineDeviceRepository tests"
```

---

### Task 7: Add device_id filtering to DatasetBuilder

**Files:**
- Modify: `src/process_opt/analysis/dataset.py:26-28`

- [ ] **Step 1: Add optional device_id and since filtering in build()**

```python
from __future__ import annotations

from datetime import datetime
from statistics import mean, median
from typing import Any

import asyncpg

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, AnalysisDatasetRequest


def _stat(values: list[float], strategy: str) -> float:
    if strategy == "mean":
        return mean(values)
    return median(values)


class DatasetBuilder:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def build(
        self, request: AnalysisDatasetRequest,
        device_id: str | None = None,
        since: datetime | None = None,
    ) -> AnalysisDataset | AnalysisError:
        query = "SELECT * FROM analysis_view"
        conditions: list[str] = []
        params: list[Any] = []
        idx = 0

        if device_id is not None:
            idx += 1
            conditions.append(f"device_id = ${idx}")
            params.append(device_id)
        if since is not None:
            idx += 1
            conditions.append(f"processed_at >= ${idx}")
            params.append(since)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY barcode"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        # ... rest unchanged ...
```

Full replacement of the `build()` signature and query section only — the rest (field checking, row processing, missing handling) remains identical.

- [ ] **Step 2: Update AnalysisService to pass device_id and since**

In `src/process_opt/analysis/service.py`, modify `spc()`:

```python
async def spc(self, request: SpcRequest) -> SpcResult:
    from process_opt.analysis.spc import build_spc_result
    overview_req = AnalysisDatasetRequest(
        feature_fields=[],
        target_fields=[],
        max_samples=None,
        missing_strategy="mean",
    )
    overview_dataset = await self._builder.build(
        overview_req,
        device_id=request.device_id,
        since=request.since,
    )

    field = request.field
    if field is not None:
        field_req = AnalysisDatasetRequest(
            feature_fields=[field],
            target_fields=[],
            max_samples=None,
            missing_strategy="mean",
        )
        field_dataset = await self._builder.build(
            field_req,
            device_id=request.device_id,
            since=request.since,
        )
        if field not in {f for feat in field_dataset.features for f in feat}:
            existing = sorted({f for feat in overview_dataset.features for f in feat})
            raise AnalysisError(
                code="FIELD_NOT_FOUND",
                message=f"Field '{field}' not found in data",
                suggestion=f"Available fields: {existing}",
            )
    else:
        field_dataset = overview_dataset

    return build_spc_result(
        overview_dataset=overview_dataset,
        field_dataset=field_dataset,
        field=field,
        usl=request.usl,
        lsl=request.lsl,
        target=request.target,
    )
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `python -m pytest tests/analysis/ -v`
Expected: 73 passed (no change from baseline)

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/analysis/dataset.py src/process_opt/analysis/service.py
git commit -m "feat: add device_id and since filtering to DatasetBuilder and SPC"
```

---

### Task 8: Add line_id to SpcRequest and wire into app.py route

**Files:**
- Modify: `src/process_opt/analysis/schemas.py:127-132`
- Modify: `src/process_opt/api/app.py` (spc route)

- [ ] **Step 1: Add line_id to SpcRequest**

```python
class SpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    field: str | None = None
    line_id: str | None = None  # NEW
    usl: float | None = None
    lsl: float | None = None
    target: float | None = None
    since: datetime | None = None
```

- [ ] **Step 2: Update spc route in app.py to resolve line_id → device_ids**

The SPC route needs access to `LineDeviceRepository` when `line_id` is provided. Add a new `LineDeviceRepositoryProtocol` and parameter.

In `src/process_opt/api/app.py`, add protocol and route logic:

```python
class LineDeviceRepositoryProtocol(Protocol):
    async def get_devices_by_line(self, line_id: str) -> list[str]: ...


def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisServiceProtocol | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
) -> FastAPI:
```

In the `spc_route` handler:

```python
@app.post("/api/v1/analysis/spc")
async def spc_route(body: SpcRequest) -> SpcResult:
    if body.line_id is not None and line_device_repo is not None:
        device_ids = await line_device_repo.get_devices_by_line(body.line_id)
        if not device_ids:
            raise HTTPException(status_code=404, detail="No devices in line")
        # Return aggregated result for the first device, or iterate
        # For now, return SPC for first device when line_id is given
        body = body.model_copy(update={"device_id": device_ids[0]})
    return await analysis_service.spc(body)
```

Wait — this requires `analysis_service` to be not None when line_id routes are used. Actually, looking at the current code more carefully, the spc route is already inside `if analysis_service is not None:`. So we need both `analysis_service` and `line_device_repo` for the enhanced route. Let me handle this properly.

Better approach: when `line_id` is given but device_id is not, the route resolves device_ids from the line and builds a response for the first device. When both are given, device_id takes precedence and line_id is used for breadcrumb context only.

```python
@app.post("/api/v1/analysis/spc")
async def spc_route(body: SpcRequest) -> SpcResult:
    if body.line_id is not None and line_device_repo is not None:
        line_devices = await line_device_repo.get_devices_by_line(body.line_id)
        if body.device_id not in line_devices:
            # device_id must belong to the line when line_id is specified
            raise HTTPException(status_code=404, detail="Device not in specified line")
    return await analysis_service.spc(body)
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/schemas.py src/process_opt/api/app.py
git commit -m "feat: add line_id to SpcRequest, validate device-line membership"
```

---

### Task 9: Add line/device CRUD API routes

**Files:**
- Modify: `src/process_opt/api/app.py` (add routes after repository block)

- [ ] **Step 1: Add line and device routes**

These go inside `create_app()`, inside a new `if line_device_repo is not None:` block that wraps both the SPC enhancement and the new routes.

```python
if line_device_repo is not None:

    @app.get("/api/v1/lines")
    async def list_lines_route() -> list[dict[str, Any]]:
        return await line_device_repo.list_lines()

    @app.get("/api/v1/lines/{line_id}")
    async def get_line_route(line_id: str) -> dict[str, Any]:
        line = await line_device_repo.get_line(line_id)
        if line is None:
            raise HTTPException(status_code=404, detail="Line not found")
        devices = await line_device_repo.list_devices(line_id=line_id)
        line["devices"] = devices
        return line

    @app.post("/api/v1/lines", status_code=status.HTTP_201_CREATED)
    async def create_line_route(body: dict[str, Any]) -> dict[str, Any]:
        from process_opt.analysis.line_schemas import LineCreate
        lc = LineCreate(**body)
        return await line_device_repo.create_line(lc.name, lc.responsible, lc.location)

    @app.put("/api/v1/lines/{line_id}")
    async def update_line_route(line_id: str, body: dict[str, Any]) -> dict[str, Any]:
        from process_opt.analysis.line_schemas import LineUpdate
        lu = LineUpdate(**body)
        result = await line_device_repo.update_line(line_id, lu.name, lu.responsible, lu.location)
        if result is None:
            raise HTTPException(status_code=404, detail="Line not found")
        return result

    @app.delete("/api/v1/lines/{line_id}")
    async def delete_line_route(line_id: str) -> Response:
        ok = await line_device_repo.delete_line(line_id)
        if not ok:
            raise HTTPException(status_code=409, detail="Line has assigned devices")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/v1/devices")
    async def list_devices_route(line_id: str | None = None) -> list[dict[str, Any]]:
        return await line_device_repo.list_devices(line_id=line_id)

    @app.get("/api/v1/devices/{device_id}")
    async def get_device_route(device_id: str) -> dict[str, Any]:
        device = await line_device_repo.get_device(device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return device

    @app.put("/api/v1/devices/{device_id}")
    async def update_device_route(device_id: str, body: dict[str, Any]) -> dict[str, Any]:
        from process_opt.analysis.line_schemas import DeviceUpdate
        du = DeviceUpdate(**body)
        result = await line_device_repo.update_device(
            device_id, du.name, du.type, du.icon, du.description, du.line_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return result

    @app.delete("/api/v1/devices/{device_id}")
    async def delete_device_route(device_id: str) -> Response:
        ok = await line_device_repo.delete_device(device_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Device not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 2: Also add the line monitoring aggregation route**

```python
    @app.get("/api/v1/lines/{line_id}/monitor")
    async def line_monitor_route(line_id: str, repository=repository, analysis_service=analysis_service) -> dict[str, Any]:
        if analysis_service is None:
            raise HTTPException(status_code=501, detail="Analysis service not available")
        line = await line_device_repo.get_line(line_id)
        if line is None:
            raise HTTPException(status_code=404, detail="Line not found")
        devices = await line_device_repo.list_devices(line_id=line_id)

        device_summaries: list[dict[str, Any]] = []
        normal = abnormal = marginal = no_spec = 0

        for device in devices:
            from process_opt.analysis.schemas import SpcRequest
            try:
                result = await analysis_service.spc(SpcRequest(
                    device_id=device["id"],
                ))
            except HTTPException:
                continue
            if not result.overview:
                continue
            statuses = [ov.status for ov in result.overview]
            if "abnormal" in statuses:
                dev_status = "abnormal"
            elif "marginal" in statuses:
                dev_status = "marginal"
            elif "no_spec" in statuses:
                dev_status = "no_spec"
            else:
                dev_status = "normal"
            cpks = [ov.cpk for ov in result.overview if ov.cpk is not None]
            device_summaries.append({
                "device_id": device["id"],
                "device_name": device["name"],
                "type": device["type"],
                "status": dev_status,
                "worst_cpk": min(cpks) if cpks else None,
                "param_count": len(result.overview),
                "outlier_total": sum(ov.outlier_count for ov in result.overview),
            })
            if dev_status == "abnormal":
                abnormal += 1
            elif dev_status == "marginal":
                marginal += 1
            elif dev_status == "no_spec":
                no_spec += 1
            else:
                normal += 1

        if abnormal > 0:
            line_status = "abnormal"
        elif marginal > 0:
            line_status = "marginal"
        elif no_spec > 0:
            line_status = "no_spec"
        elif normal > 0:
            line_status = "normal"
        else:
            line_status = "empty"

        return {
            "line": line,
            "summary": {
                "device_count": len(devices),
                "normal_count": normal,
                "abnormal_count": abnormal,
                "marginal_count": marginal,
                "no_spec_count": no_spec,
                "status": line_status,
            },
            "devices": device_summaries,
        }
```

- [ ] **Step 3: Restructure create_app() signature and call site**

The existing `create_app()` signature must be updated:

```python
def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisServiceProtocol | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
) -> FastAPI:
```

And the existing spc route that's inside `if analysis_service is not None:` should be enhanced to validate line membership:

```python
@app.post("/api/v1/analysis/spc")
async def spc_route(body: SpcRequest) -> SpcResult:
    if body.line_id is not None and line_device_repo is not None:
        line_devices = await line_device_repo.get_devices_by_line(body.line_id)
        if body.device_id not in line_devices:
            raise HTTPException(status_code=404, detail="Device not in specified line")
    return await analysis_service.spc(body)
```

- [ ] **Step 4: Wire LineDeviceRepository in main.py**

In `src/process_opt/api/main.py`, update `create_app()` call:

```python
from process_opt.common.repositories import DataRepository, LineDeviceRepository

async def main() -> None:
    settings = Settings()
    pool = await create_pool(settings.postgres_dsn)
    try:
        # Apply migrations
        migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"
        for fpath in sorted(migrations_dir.glob("*.sql")):
            await apply_sql_file(pool, fpath)

        repository = DataRepository(pool)
        line_device_repo = LineDeviceRepository(pool)
        # ... existing parameter_service, analysis_service setup ...
        app = create_app(
            repository=repository,
            parameter_service=parameter_service,
            analysis_service=analysis_service,
            line_device_repo=line_device_repo,
        )
        # ...
```

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/api/app.py src/process_opt/api/main.py
git commit -m "feat: add line/device CRUD API routes and monitoring endpoint"
```

---

### Task 10: Write API integration tests

**Files:**
- Create: `tests/api/test_lines_api.py`

- [ ] **Step 1: Write API tests**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from process_opt.api.app import create_app
from process_opt.common.repositories import DataRepository, LineDeviceRepository
from process_opt.common.db import create_pool


@pytest.fixture
async def pool():
    p = await create_pool("postgresql://postgres:postgres@localhost:5432/process_opt")
    from pathlib import Path
    from process_opt.common.db import apply_sql_file
    migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
    for fpath in sorted(migrations_dir.glob("*.sql")):
        await apply_sql_file(p, fpath)
    yield p
    await p.close()


@pytest.fixture
async def client(pool):
    ldr = LineDeviceRepository(pool)
    app = create_app(line_device_repo=ldr)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestLinesAPI:
    @pytest.mark.anyio
    async def test_create_line(self, client):
        resp = await client.post("/api/v1/lines", json={
            "name": "APITest线", "responsible": "测试", "location": "车间A"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "APITest线"
        assert "id" in data

    @pytest.mark.anyio
    async def test_list_lines(self, client):
        resp = await client.get("/api/v1/lines")
        assert resp.status_code == 200
        lines = resp.json()
        assert any(l["name"] == "默认产线" for l in lines)

    @pytest.mark.anyio
    async def test_get_line_404(self, client):
        resp = await client.get("/api/v1/lines/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_409_with_devices(self, client):
        # 默认产线 has devices from backfill
        resp = await client.get("/api/v1/lines")
        lines = resp.json()
        default_line = next(l for l in lines if l["name"] == "默认产线")
        resp = await client.delete(f"/api/v1/lines/{default_line['id']}")
        assert resp.status_code == 409


class TestDevicesAPI:
    @pytest.mark.anyio
    async def test_list_devices(self, client):
        resp = await client.get("/api/v1/devices")
        assert resp.status_code == 200
        devices = resp.json()
        ids = [d["id"] for d in devices]
        assert "reflow-oven" in ids or "injection-molder" in ids

    @pytest.mark.anyio
    async def test_update_device(self, client):
        resp = await client.put("/api/v1/devices/reflow-oven", json={
            "name": "回流焊-01", "type": "reflow-oven", "icon": "Platform"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "回流焊-01"
        assert data["icon"] == "Platform"

    @pytest.mark.anyio
    async def test_get_device_404(self, client):
        resp = await client.get("/api/v1/devices/nonexistent")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/api/test_lines_api.py -v`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_lines_api.py
git commit -m "test: add line/device API integration tests"
```

---

### Task 11: Create frontend API client for lines

**Files:**
- Create: `web/src/api/lines.ts`

- [ ] **Step 1: Write the API client**

```ts
import client from './client'

export interface LineResponse {
  id: string
  name: string
  responsible: string
  location: string | null
  device_count: number
  created_at: string
  updated_at: string
}

export interface DeviceResponse {
  id: string
  line_id: string | null
  line_name: string | null
  name: string
  type: string
  icon: string | null
  description: string | null
}

export interface LineDetailResponse extends LineResponse {
  devices: DeviceResponse[]
}

export interface CreateLineRequest {
  name: string
  responsible: string
  location?: string
}

export interface UpdateLineRequest {
  name?: string
  responsible?: string
  location?: string
}

export interface UpdateDeviceRequest {
  name?: string
  type?: string
  icon?: string
  description?: string
  line_id?: string
}

export function listLines(): Promise<LineResponse[]> {
  return client.get('/lines').then((res) => res.data)
}

export function getLine(id: string): Promise<LineDetailResponse> {
  return client.get(`/lines/${id}`).then((res) => res.data)
}

export function createLine(data: CreateLineRequest): Promise<LineResponse> {
  return client.post('/lines', data).then((res) => res.data)
}

export function updateLine(id: string, data: UpdateLineRequest): Promise<LineResponse> {
  return client.put(`/lines/${id}`, data).then((res) => res.data)
}

export function deleteLine(id: string): Promise<void> {
  return client.delete(`/lines/${id}`)
}

export function listDevices(lineId?: string): Promise<DeviceResponse[]> {
  const params = lineId ? { line_id: lineId } : {}
  return client.get('/devices', { params }).then((res) => res.data)
}

export function getDevice(id: string): Promise<DeviceResponse> {
  return client.get(`/devices/${id}`).then((res) => res.data)
}

export function updateDevice(id: string, data: UpdateDeviceRequest): Promise<DeviceResponse> {
  return client.put(`/devices/${id}`, data).then((res) => res.data)
}

export function deleteDevice(id: string): Promise<void> {
  return client.delete(`/devices/${id}`)
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/lines.ts
git commit -m "feat: add frontend API client for lines and devices"
```

---

### Task 12: Create LinesView.vue (line list page)

**Files:**
- Create: `web/src/views/LinesView.vue`

- [ ] **Step 1: Write LinesView component** (approximately 220 lines)

The page shows a table of production lines with CRUD operations. Uses Element Plus table, dialog for create/edit, confirm for delete.

```vue
<template>
  <div class="lines-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">线体监控</h2>
        <p class="page-desc">生产线管理 & 设备聚合监控</p>
      </div>
      <el-button type="primary" @click="openCreate">+ 新建线体</el-button>
    </div>

    <el-card class="lines-table-card">
      <el-table :data="lines" stripe size="small" v-loading="loading" empty-text="暂无产线，点击上方按钮创建">
        <el-table-column prop="name" label="线体名称" min-width="140" class-name="cell-mono">
          <template #default="{ row }">
            <router-link :to="`/lines/${row.id}`" class="line-link">{{ row.name }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="responsible" label="责任人" width="100" class-name="cell-mono" />
        <el-table-column prop="location" label="位置" width="120" class-name="cell-mono">
          <template #default="{ row }">{{ row.location || '—' }}</template>
        </el-table-column>
        <el-table-column prop="device_count" label="设备数" width="80" class-name="cell-mono" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button text size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text size="small" type="danger" @click="handleDelete(row)" :disabled="row.device_count > 0">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑线体' : '新建线体'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="线体名称">
          <el-input v-model="form.name" placeholder="如 SMT-01" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="form.responsible" placeholder="负责人姓名" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="如 A栋2层" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">{{ editing ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listLines, createLine, updateLine, deleteLine, type LineResponse } from '@/api/lines'

const lines = ref<LineResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<LineResponse | null>(null)
const form = ref({ name: '', responsible: '', location: '' })

async function loadLines() {
  loading.value = true
  try { lines.value = await listLines() } finally { loading.value = false }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', responsible: '', location: '' }
  dialogVisible.value = true
}

function openEdit(row: LineResponse) {
  editing.value = row
  form.value = { name: row.name, responsible: row.responsible, location: row.location || '' }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editing.value) {
      await updateLine(editing.value.id, form.value)
    } else {
      await createLine(form.value)
    }
    dialogVisible.value = false
    await loadLines()
  } finally { saving.value = false }
}

async function handleDelete(row: LineResponse) {
  await deleteLine(row.id)
  await loadLines()
}

onMounted(loadLines)
</script>

<style scoped>
.lines-view { display: flex; flex-direction: column; gap: 12px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 2px 0 0; }
.line-link { color: var(--el-color-primary); text-decoration: none; font-family: 'Fira Code', monospace; }
.line-link:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/views/LinesView.vue
git commit -m "feat: add LinesView page for line list and management"
```

---

### Task 13: Create LineDetailView.vue (line detail + device list)

**Files:**
- Create: `web/src/views/LineDetailView.vue`

- [ ] **Step 1: Write LineDetailView component** (approximately 260 lines)

```vue
<template>
  <div class="line-detail-view">
    <div class="page-header">
      <div>
        <router-link to="/lines" class="back-link">← 返回线体列表</router-link>
        <h2 class="page-title">{{ line?.name || '加载中...' }}</h2>
        <p class="page-desc">责任人: {{ line?.responsible }} · 位置: {{ line?.location || '未设置' }}</p>
      </div>
      <el-button v-if="line" text @click="openEditLine">编辑线体</el-button>
    </div>

    <div v-if="line" class="overview-cards">
      <el-card><div class="stat-value">{{ devices.length }}</div><div class="stat-label">设备总数</div></el-card>
      <el-card><div class="stat-value" style="color:#059669">{{ normalCount }}</div><div class="stat-label">正常</div></el-card>
      <el-card><div class="stat-value" style="color:#DC2626">{{ abnormalCount }}</div><div class="stat-label">异常</div></el-card>
      <el-card><div class="stat-value" style="color:#D97706">{{ marginalCount }}</div><div class="stat-label">边缘</div></el-card>
    </div>

    <el-card class="devices-card">
      <template #header>
        <div class="devices-header">
          <span>设备列表</span>
          <el-button size="small" @click="openManageDevices">管理设备</el-button>
        </div>
      </template>
      <el-table :data="devices" stripe size="small" v-loading="loading" empty-text="暂无设备">
        <el-table-column prop="name" label="设备名称" min-width="140" class-name="cell-mono">
          <template #default="{ row }">
            <router-link :to="`/spc?line=${line!.id}&device=${row.id}`" class="device-link">
              <el-icon v-if="row.icon" size="14"><component :is="row.icon" /></el-icon>
              {{ row.name }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="设备类型" width="140" class-name="cell-mono" />
        <el-table-column prop="description" label="描述" min-width="160" class-name="cell-mono">
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button text size="small" @click="openEditDevice(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Line edit dialog -->
    <el-dialog v-model="lineDialogVisible" title="编辑线体" width="480px">
      <el-form :model="lineForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="lineForm.name" /></el-form-item>
        <el-form-item label="责任人"><el-input v-model="lineForm.responsible" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="lineForm.location" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="lineDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveLine" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Device edit dialog -->
    <el-dialog v-model="deviceDialogVisible" title="编辑设备" width="480px">
      <el-form :model="deviceForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="deviceForm.name" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="deviceForm.type" /></el-form-item>
        <el-form-item label="图标"><el-input v-model="deviceForm.icon" placeholder="Element Plus icon name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="deviceForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Manage devices dialog -->
    <el-dialog v-model="manageDialogVisible" title="管理设备" width="560px">
      <el-table :data="allDevices" stripe size="small">
        <el-table-column prop="name" label="设备" class-name="cell-mono" />
        <el-table-column prop="line_name" label="所属线体" width="140" class-name="cell-mono">
          <template #default="{ row }">{{ row.line_name || '未分配' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button v-if="row.line_id !== line!.id" text size="small" type="primary" @click="assignDevice(row)">分配到本线</el-button>
            <el-button v-else text size="small" type="danger" @click="unassignDevice(row)">移出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { getLine, updateLine, listDevices, updateDevice, type LineDetailResponse, type DeviceResponse } from '@/api/lines'

const route = useRoute()
const line = ref<LineDetailResponse | null>(null)
const devices = ref<DeviceResponse[]>([])
const allDevices = ref<DeviceResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const lineDialogVisible = ref(false)
const deviceDialogVisible = ref(false)
const manageDialogVisible = ref(false)
const editingDevice = ref<DeviceResponse | null>(null)
const lineForm = ref({ name: '', responsible: '', location: '' })
const deviceForm = ref({ name: '', type: '', icon: '', description: '' })

const normalCount = computed(() => 0) // will be replaced by monitor endpoint later
const abnormalCount = computed(() => 0)
const marginalCount = computed(() => 0)

async function loadLine() {
  loading.value = true
  try {
    const id = route.params.id as string
    line.value = await getLine(id)
    devices.value = line.value.devices
  } finally { loading.value = false }
}

function openEditLine() {
  if (!line.value) return
  lineForm.value = { name: line.value.name, responsible: line.value.responsible, location: line.value.location || '' }
  lineDialogVisible.value = true
}

async function saveLine() {
  if (!line.value) return
  saving.value = true
  try {
    await updateLine(line.value.id, lineForm.value)
    lineDialogVisible.value = false
    await loadLine()
  } finally { saving.value = false }
}

function openEditDevice(device: DeviceResponse) {
  editingDevice.value = device
  deviceForm.value = {
    name: device.name, type: device.type, icon: device.icon || '',
    description: device.description || '',
  }
  deviceDialogVisible.value = true
}

async function saveDevice() {
  if (!editingDevice.value) return
  saving.value = true
  try {
    await updateDevice(editingDevice.value.id, deviceForm.value)
    deviceDialogVisible.value = false
    await loadLine()
  } finally { saving.value = false }
}

async function openManageDevices() {
  allDevices.value = await listDevices()
  manageDialogVisible.value = true
}

async function assignDevice(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: line.value!.id })
  await loadLine()
  allDevices.value = await listDevices()
}

async function unassignDevice(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: null as unknown as string })
  await loadLine()
  allDevices.value = await listDevices()
}

onMounted(loadLine)
</script>

<style scoped>
.line-detail-view { display: flex; flex-direction: column; gap: 12px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 2px 0 0; }
.back-link { font-size: 12px; color: var(--el-text-color-secondary); text-decoration: none; }
.back-link:hover { color: var(--el-color-primary); }
.overview-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.overview-cards .el-card { text-align: center; padding: 0; }
.overview-cards :deep(.el-card__body) { padding: 16px 8px; }
.stat-value { font-family: 'Fira Code', monospace; font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.devices-header { display: flex; justify-content: space-between; align-items: center; }
.device-link { color: var(--el-color-primary); text-decoration: none; display: flex; align-items: center; gap: 4px; font-family: 'Fira Code', monospace; }
.device-link:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/views/LineDetailView.vue
git commit -m "feat: add LineDetailView page with device management"
```

---

### Task 14: Enhance SpcView.vue with line context

**Files:**
- Modify: `web/src/views/SpcView.vue` (add breadcrumb, device info bar, line-scoped devices)

- [ ] **Step 1: Add breadcrumb and device info bar at top of template**

Add after the `<div class="spc-view">` opening tag:

```vue
<div v-if="route.query.line && route.query.device" class="spc-breadcrumb">
  <router-link to="/lines" class="bc-link">线体监控</router-link>
  <span class="bc-sep">›</span>
  <router-link :to="`/lines/${route.query.line}`" class="bc-link">{{ lineName || route.query.line }}</router-link>
  <span class="bc-sep">›</span>
  <span class="bc-current">{{ deviceInfo?.name || route.query.device }}</span>
  <el-button v-if="deviceInfo" text size="small" @click="editingDevice = true" style="margin-left:auto">编辑设备</el-button>
</div>

<div v-if="deviceInfo" class="device-info-bar">
  <span class="info-item"><span class="info-label">类型</span> {{ deviceInfo.type }}</span>
  <span v-if="deviceInfo.description" class="info-item"><span class="info-label">描述</span> {{ deviceInfo.description }}</span>
</div>
```

- [ ] **Step 2: Add script logic for device context**

Add imports:

```ts
import { useRoute } from 'vue-router'
import { getDevice, updateDevice, type DeviceResponse } from '@/api/lines'

const route = useRoute()
const deviceInfo = ref<DeviceResponse | null>(null)
const lineName = ref('')
const editingDevice = ref(false)
```

Add a watcher or onMounted logic to load device info when route params change:

```ts
import { watchEffect } from 'vue'

watchEffect(async () => {
  const deviceId = route.query.device as string | undefined
  if (deviceId) {
    try {
      deviceInfo.value = await getDevice(deviceId)
      if (deviceInfo.value?.line_id) {
        const line = await getLine(deviceInfo.value.line_id)
        lineName.value = line.name
      }
    } catch { deviceInfo.value = null }
  } else {
    deviceInfo.value = null
    lineName.value = ''
  }
})
```

For the device selector: when `line` param present, populate device list from line devices instead of all devices:

```ts
// In onMounted, replace listDevices() call:
if (route.query.line) {
  const lineDevices = await listDevices(route.query.line as string)
  devices.value = lineDevices.map(d => d.id)
} else {
  devices.value = await listDevices().then(ds => ds.map(d => d.id))
}
```

Actually, let's keep it simple: always load all device IDs for the selector, but when line is present, filter `process_summary` by device. The existing `devices` ref from `listDevices()` from `@/api/records` is a `string[]`. Let's just add a computed filter:

```ts
const filteredDevices = computed(() => {
  if (!route.query.line) return devices.value
  // If we have line-scoped devices loaded, use those
  return devices.value // For now, show all; the API filters by line
})
```

Actually, the simplest enhancement: when `route.query.line` is present, load devices scoped to that line to populate the device selector:

```ts
// Add import
import { listDevices as listLineDevices } from '@/api/lines'

// Modify the device loading in onMounted:
const lineId = route.query.line as string | undefined
if (lineId) {
  try {
    const lineDevs = await listLineDevices(lineId)
    devices.value = lineDevs.map(d => d.id)
    // Auto-select the device from URL
    const target = route.query.device as string | undefined
    if (target && lineDevs.some(d => d.id === target)) {
      filter.deviceId = target
    }
  } catch { /* fall through to loadAll */ }
}
if (!devices.value.length) {
  devices.value = await listDevices()
}

// Also show all registered devices for standalone mode
```

- [ ] **Step 3: Add CSS for breadcrumb and info bar**

```css
.spc-breadcrumb {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--el-fill-color-light);
  border-radius: 6px; font-size: 12px;
}
.bc-link { color: var(--el-color-primary); text-decoration: none; }
.bc-link:hover { text-decoration: underline; }
.bc-sep { color: var(--el-text-color-placeholder); }
.bc-current { color: var(--el-text-color-primary); font-weight: 500; }
.device-info-bar {
  display: flex; gap: 24px; padding: 4px 12px;
  font-size: 12px; color: var(--el-text-color-regular);
}
.info-label { color: var(--el-text-color-secondary); margin-right: 4px; }
```

- [ ] **Step 4: Commit**

```bash
git add web/src/views/SpcView.vue
git commit -m "feat: add line-context breadcrumb and device info to SpcView"
```

---

### Task 15: Update router to add new routes

**Files:**
- Modify: `web/src/router/index.ts`

- [ ] **Step 1: Add new routes**

```ts
children: [
  { path: 'dashboard', component: () => import('@/views/DashboardView.vue') },
  { path: 'data', component: () => import('@/views/DataView.vue') },
  { path: 'spc', component: () => import('@/views/SpcView.vue') },
  { path: 'lines', component: () => import('@/views/LinesView.vue') },
  { path: 'lines/:id', component: () => import('@/views/LineDetailView.vue') },
  { path: 'guide', component: () => import('@/views/GuideView.vue') },
  { path: 'analysis', component: () => import('@/views/AnalysisView.vue') },
  { path: 'parameters', component: () => import('@/views/ParametersView.vue') },
  { path: 'settings', component: () => import('@/views/SettingsView.vue') },
],
```

- [ ] **Step 2: Verify no type errors**

Run: `cd web && npx vue-tsc --noEmit`
Expected: no output (clean)

- [ ] **Step 3: Commit**

```bash
git add web/src/router/index.ts
git commit -m "feat: add /lines and /lines/:id routes"
```

---

### Task 16: Update sidebar menu label

**Files:**
- Modify: `web/src/components/AppLayout.vue`

- [ ] **Step 1: Change menu item for 设备监控 → 线体监控**

```vue
<el-menu-item index="/lines">
  <el-icon><TrendCharts /></el-icon>
  <template #title>线体监控</template>
</el-menu-item>
```

Replace the existing menu item at index `/spc` with index `/lines`.

Also remove the old `/spc` entry since SPC is now reached via `/lines/:id` → drill-down.

- [ ] **Step 2: Commit**

```bash
git add web/src/components/AppLayout.vue
git commit -m "feat: change sidebar menu from 设备监控 to 线体监控"
```

---

### Task 17: Adapt mock generator to register devices

**Files:**
- Modify: `src/process_opt/mock/generator.py`
- Modify: `src/process_opt/mock/sender.py` (or cli.py) — add DB pool access

- [ ] **Step 1: Add device registration to mock CLI**

Since the mock generator is a standalone CLI (not a service with DB pool), we add DB access for device registration. The simplest approach: add a `--db-dsn` option to the CLI for seed/stream commands, and auto-register on first use.

In `src/process_opt/mock/cli.py`:

```python
import asyncio
from pathlib import Path

@click.option("--db-dsn", default=None, help="PostgreSQL DSN for device registration")
@click.option("--device-count", default=500, help="Number of devices to pre-register per type")
def seed(count, device_type, gateway_url, api_key, db_dsn, device_count):
    if db_dsn:
        asyncio.run(_register_devices(db_dsn, device_type, device_count))
    # ... existing seed logic ...


async def _register_devices(dsn: str, device_type: str, count: int) -> None:
    from process_opt.common.db import create_pool
    from process_opt.common.repositories import LineDeviceRepository
    pool = await create_pool(dsn)
    try:
        repo = LineDeviceRepository(pool)
        for i in range(1, count + 1):
            await repo.ensure_device_exists(f"{device_type}-{i:03d}", device_type)
    finally:
        await pool.close()
```

- [ ] **Step 2: Update mock sender/generator to use real device IDs**

In `generate_pair()`, instead of `"device_id": device_type`, query or use registered ID:

```python
def generate_pair(device_type: str, barcode: str, device_index: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    message_id = str(uuid4())
    params = generate_params(device_type)
    results = generate_results(device_type, params)
    now = datetime.now(UTC)

    process_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "device_id": f"{device_type}-{device_index:03d}",
        "processed_at": now.isoformat(),
        "params": params,
    }
    # ... rest unchanged ...
```

Update `seed` command to pass `device_index` cycling through registered count:

```python
asyncio.run(send_batch(
    [generate_pair(device_type, f"MOCK-{uuid4().hex[:8].upper()}", (i % device_count) + 1)
     for i in range(count)],
    gateway_url, api_key,
))
```

- [ ] **Step 3: Test by re-seeding data**

Run: `docker compose -f docker-compose.yml exec postgres psql -U postgres -d process_opt -c "SELECT COUNT(*) FROM device_registry;"`

Expected: devices exist in registry

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/mock/generator.py src/process_opt/mock/cli.py
git commit -m "feat: mock generator registers devices and uses per-type device IDs"
```

---

### Task 18: Final integration test — run full stack

- [ ] **Step 1: Rebuild and restart all services**

Run: `docker compose -f docker-compose.yml up -d --build`

- [ ] **Step 2: Re-seed mock data with device registration**

Run: `.venv/bin/process-opt-mock seed --count 100 --device-type reflow-oven --gateway-url http://localhost:8001 --api-key change-me --db-dsn postgresql://postgres:postgres@localhost:5432/process_opt --device-count 10`

- [ ] **Step 3: Verify API endpoints**

Run:
```bash
curl -s http://localhost:8000/api/v1/lines | python3 -m json.tool
curl -s http://localhost:8000/api/v1/devices | python3 -m json.tool
```

Expected: lines and devices returned with correct data.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: all tests pass (baseline + new line/device tests)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: complete line monitoring feature — DB, API, frontend, mock adaptation"
```
