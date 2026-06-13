# Raw Data Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paginated raw data browsing page with barcode/device/time-range filtering.

**Architecture:** Backend adds two query methods to existing `DataRepository` + two GET routes to the API; frontend adds a new Vue view, a new API client module, and a sidebar nav entry. No new DB tables or containers.

**Tech Stack:** asyncpg, FastAPI, Vue 3 + Element Plus + axios

---

### Task 1: Repository — query_records and list_devices

**Files:**
- Modify: `src/process_opt/common/repositories.py`
- Test: `tests/common/test_repositories.py`

- [ ] **Step 1: Write failing test for query_records**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m pytest tests/common/test_repositories.py::test_query_records_returns_paginated_results -v
```
Expected: FAIL — `DataRepository` has no method `query_records`

- [ ] **Step 3: Write failing test for list_devices**

```python
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
```

- [ ] **Step 4: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m pytest tests/common/test_repositories.py::test_list_devices_returns_distinct_device_ids -v
```
Expected: FAIL — `DataRepository` has no method `list_devices`

- [ ] **Step 5: Implement query_records and list_devices in DataRepository**

Add to `src/process_opt/common/repositories.py`:

```python
from datetime import datetime

async def query_records(
    self,
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []
    idx = 0

    if barcode is not None:
        idx += 1
        conditions.append(f"barcode = ${idx}")
        params.append(barcode)
    if device_id is not None:
        idx += 1
        conditions.append(f"device_id = ${idx}")
        params.append(device_id)
    if start_time is not None:
        idx += 1
        conditions.append(f"processed_at >= ${idx}")
        params.append(start_time)
    if end_time is not None:
        idx += 1
        conditions.append(f"processed_at <= ${idx}")
        params.append(end_time)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    offset = (page - 1) * page_size

    async with self._pool.acquire() as connection:
        rows = await connection.fetch(
            f"""
            SELECT barcode, device_id, processed_at, params,
                   station_id, inspected_at, results,
                   COUNT(*) OVER() AS total_count
            FROM analysis_view
            WHERE {where_clause}
            ORDER BY processed_at DESC
            OFFSET ${idx + 1} LIMIT ${idx + 2}
            """,
            *params,
            offset,
            page_size,
        )

    if not rows:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    total = rows[0]["total_count"]
    items = [
        {
            "barcode": r["barcode"],
            "device_id": r["device_id"],
            "processed_at": r["processed_at"],
            "params": r["params"],
            "station_id": r["station_id"],
            "inspected_at": r["inspected_at"],
            "results": r["results"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def list_devices(self) -> list[str]:
    async with self._pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT DISTINCT device_id FROM process_summary ORDER BY device_id"
        )
    return [r["device_id"] for r in rows]
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/common/test_repositories.py -v
```
Expected: Both new tests PASS (plus existing test still passes = 4 total)

- [ ] **Step 7: Update AnalysisRepository protocol in app.py**

In `src/process_opt/api/app.py`, add to the `AnalysisRepository` protocol:

```python
class AnalysisRepository(Protocol):
    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None: ...
    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]: ...
    async def list_devices(self) -> list[str]: ...
```

Add `from datetime import datetime` to imports.

---

### Task 2: API routes — records list and devices list

**Files:**
- Modify: `src/process_opt/api/app.py`
- Test: `tests/api/test_app.py`

- [ ] **Step 1: Add query_records and list_devices to FakeRepository**

In `tests/api/test_app.py`, add to `FakeRepository`:

```python
async def query_records(
    self,
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    items = list(self.records.values())
    if barcode:
        items = [r for r in items if r["barcode"] == barcode]
    if device_id:
        items = [r for r in items if r["device_id"] == device_id]
    if start_time:
        items = [r for r in items if r["processed_at"] >= start_time]
    if end_time:
        items = [r for r in items if r["processed_at"] <= end_time]
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": items[start:end], "total": total, "page": page, "page_size": page_size}

async def list_devices(self) -> list[str]:
    return sorted(set(r["device_id"] for r in self.records.values()))
```

- [ ] **Step 2: Write failing test for query_records API**

```python
@pytest.mark.asyncio
async def test_query_records_returns_paginated_list() -> None:
    app = create_app(FakeRepository())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/records")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["barcode"] == "B1"
    assert data["page"] == 1
    assert data["page_size"] == 20
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m pytest tests/api/test_app.py::test_query_records_returns_paginated_list -v
```
Expected: FAIL — 404 or method not found

- [ ] **Step 4: Write failing test for query_records with filters**

```python
@pytest.mark.asyncio
async def test_query_records_filters_by_parameters() -> None:
    repository = FakeRepository()
    repository.records["B2"] = {
        "barcode": "B2",
        "device_id": "injection-molder",
        "processed_at": datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        "params": {"pressure": 150},
        "station_id": None,
        "inspected_at": None,
        "results": None,
    }
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Filter by device
        r = await client.get("/api/v1/analysis/records", params={"device_id": "injection-molder"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["device_id"] == "injection-molder"

        # Filter by barcode
        r = await client.get("/api/v1/analysis/records", params={"barcode": "B1"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

        # Filter by time range
        r = await client.get(
            "/api/v1/analysis/records",
            params={
                "start_time": "2026-06-09T00:00:00Z",
                "end_time": "2026-06-09T23:59:59Z",
            },
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

        # Pagination
        r = await client.get("/api/v1/analysis/records", params={"page": 1, "page_size": 1})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1
        assert r.json()["total"] == 2

        # No match
        r = await client.get("/api/v1/analysis/records", params={"barcode": "NONEXIST"})
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []
```

- [ ] **Step 5: Write failing test for list_devices API**

```python
@pytest.mark.asyncio
async def test_list_devices_returns_device_ids() -> None:
    repository = FakeRepository()
    repository.records["B2"] = {
        "barcode": "B2",
        "device_id": "injection-molder",
        "processed_at": datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        "params": {"pressure": 150},
        "station_id": None,
        "inspected_at": None,
        "results": None,
    }
    app = create_app(repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/devices")

    assert response.status_code == 200
    assert response.json() == ["D1", "injection-molder"]
```

- [ ] **Step 6: Implement API routes**

In `src/process_opt/api/app.py`, add to the `if repository is not None:` block, after the existing `get_analysis_record` route:

```python
@app.get("/api/v1/analysis/records")
async def query_records_route(
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Any:
    return await repository.query_records(barcode, device_id, start_time, end_time, page, page_size)


@app.get("/api/v1/analysis/devices")
async def list_devices_route() -> Any:
    return await repository.list_devices()
```

Add `from datetime import datetime` at the top of `app.py` if not already present.

- [ ] **Step 7: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/api/test_app.py -v
```
Expected: All 5 tests PASS (existing 3 + 3 new)

---

### Task 3: Frontend — API client module

**Files:**
- Create: `web/src/api/records.ts`

- [ ] **Step 1: Write the API client**

```typescript
import client from './client'

export interface RecordsQuery {
  barcode?: string
  device_id?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

export interface AnalysisRecord {
  barcode: string
  device_id: string
  processed_at: string
  params: Record<string, number | string>
  station_id: string | null
  inspected_at: string | null
  results: Record<string, string | number> | null
}

export interface RecordsResponse {
  items: AnalysisRecord[]
  total: number
  page: number
  page_size: number
}

export function queryRecords(params: RecordsQuery): Promise<RecordsResponse> {
  return client.get('/analysis/records', { params }).then((res) => res.data)
}

export function listDevices(): Promise<string[]> {
  return client.get('/analysis/devices').then((res) => res.data)
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
npm run typecheck
```
Expected: No errors

---

### Task 4: Frontend — DataView component

**Files:**
- Create: `web/src/views/DataView.vue`

- [ ] **Step 1: Verify existing patterns**

Read `web/src/views/AnalysisView.vue` to confirm pattern:
```bash
cat web/src/views/AnalysisView.vue
```

- [ ] **Step 2: Write the DataView component**

```vue
<template>
  <div class="data-view">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="条码">
          <el-input v-model="filters.barcode" placeholder="精确条码" clearable />
        </el-form-item>
        <el-form-item label="设备">
          <el-select v-model="filters.device_id" placeholder="全部设备" clearable>
            <el-option
              v-for="d in devices"
              :key="d"
              :label="d"
              :value="d"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="处理时间">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            :shortcuts="timeShortcuts"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table
        :data="records"
        v-loading="loading"
        style="width: 100%"
        :default-expand-all="false"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail-panel">
              <el-descriptions title="工艺参数" :column="1" border size="small">
                <el-descriptions-item
                  v-for="(val, key) in row.params"
                  :key="key"
                  :label="key"
                >
                  {{ val }}
                </el-descriptions-item>
              </el-descriptions>
              <el-descriptions
                v-if="row.results"
                title="检测结果"
                :column="1"
                border
                size="small"
                class="results-desc"
              >
                <el-descriptions-item
                  v-for="(val, key) in row.results"
                  :key="key"
                  :label="key"
                >
                  <el-tag
                    :type="val === 'pass' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ val }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
              <el-empty v-else description="暂无检测数据" />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="barcode" label="条码" width="200" />
        <el-table-column prop="device_id" label="设备" width="160" />
        <el-table-column prop="processed_at" label="处理时间" width="180" />
        <el-table-column prop="inspected_at" label="检测时间" width="180" />
        <el-table-column label="参数数" width="80">
          <template #default="{ row }">
            {{ Object.keys(row.params).length }}
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <template v-if="row.results">
              <el-tag
                v-if="allPass(row.results)"
                type="success"
                size="small"
              >
                pass
              </el-tag>
              <el-tag v-else type="danger" size="small">fail</el-tag>
            </template>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          :disabled="loading"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchRecords"
          @size-change="fetchRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { queryRecords, listDevices, type AnalysisRecord } from '@/api/records'

const loading = ref(false)
const records = ref<AnalysisRecord[]>([])
const devices = ref<string[]>([])

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const filters = reactive({
  barcode: '',
  device_id: '',
})

const timeRange = ref<[Date, Date] | null>(null)

const timeShortcuts = [
  { text: '最近1小时', value: () => [new Date(Date.now() - 3600000), new Date()] },
  { text: '最近24小时', value: () => [new Date(Date.now() - 86400000), new Date()] },
  { text: '最近7天', value: () => [new Date(Date.now() - 604800000), new Date()] },
]

function allPass(results: Record<string, string | number>): boolean {
  return Object.values(results).every((v) => v === 'pass')
}

async function fetchRecords() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.barcode) params.barcode = filters.barcode
    if (filters.device_id) params.device_id = filters.device_id
    if (timeRange.value) {
      params.start_time = timeRange.value[0].toISOString()
      params.end_time = timeRange.value[1].toISOString()
    }
    const data = await queryRecords(params)
    records.value = data.items
    pagination.total = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchRecords()
}

function handleReset() {
  filters.barcode = ''
  filters.device_id = ''
  timeRange.value = null
  pagination.page = 1
  fetchRecords()
}

onMounted(async () => {
  try {
    devices.value = await listDevices()
  } catch {
    // Silently fail — devices list is not critical
  }
  await fetchRecords()
})
</script>

<style scoped>
.data-view {
  padding: 20px;
}
.filter-card {
  margin-bottom: 16px;
}
.table-card {
  min-height: 300px;
}
.detail-panel {
  padding: 12px 24px;
}
.results-desc {
  margin-top: 16px;
}
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
```

- [ ] **Step 3: Verify Vue build compiles**

Run:
```bash
npm run build
```
Expected: No errors

---

### Task 5: Frontend — router and sidebar navigation

**Files:**
- Modify: `web/src/router/index.ts`
- Modify: `web/src/components/AppLayout.vue`

- [ ] **Step 1: Add `/data` route**

In `web/src/router/index.ts`, add to the children array:
```typescript
{ path: 'data', component: () => import('@/views/DataView.vue') },
```

- [ ] **Step 2: Add sidebar menu item**

In `web/src/components/AppLayout.vue`, import `DocumentCopy` icon at the top:
```typescript
import { Monitor, DataAnalysis, Setting, Tools, DocumentCopy } from '@element-plus/icons-vue'
```

Add menu item after the Parameters entry and before Settings:
```html
<el-menu-item index="/data">
  <el-icon><DocumentCopy /></el-icon>
  <span>原始数据</span>
</el-menu-item>
```

- [ ] **Step 3: Verify build**

Run:
```bash
npm run build
```
Expected: No errors

- [ ] **Step 4: Run full test suite**

Run:
```bash
.venv/bin/python -m pytest -v
```
Expected: All tests pass (159 total = 154 existing + 5 new)
