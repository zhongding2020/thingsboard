# Analysis Module Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify online and Excel analysis into a four-step workflow (import → preview → config → report), eliminate 6 duplicate components, reduce API endpoints from 11 to 7.

**Architecture:** All analysis endpoints accept optional `dataset_id` — when present, retrieve from in-memory store; otherwise use the old DB-backed flow. New endpoints: `POST /analysis/dataset/query`, `POST /analysis/dataset/upload` (renamed from excel/upload), `GET /analysis/dataset/{id}/preview`. Frontend AnalysisView.vue rewritten as state-machine (import/preview/config/loading/report). Three Excel-specific Vue components deleted. Three online components modified to accept `datasetId` prop.

**Tech Stack:** Python/asyncpg/FastAPI (backend), Vue 3 + Element Plus + TypeScript (frontend)

---

## File Structure Map

```
New files:
  web/src/components/DataPreviewTable.vue      — paginated table with Feature/Target color columns
  web/src/components/FieldCheckboxGrid.vue      — checkbox card grid for field selection

Modified files:
  src/process_opt/analysis/dataset.py           — add build_to_dataset_id()
  src/process_opt/analysis/schemas.py           — add dataset_id to AnalysisDatasetRequest
  src/process_opt/api/app.py                    — new routes, unify analysis endpoints, remove /excel/*
  web/src/api/analysis.ts                       — unified API client
  web/src/views/AnalysisView.vue                — total rewrite: state-machine workflow
  web/src/components/CorrelationChart.vue       — accept datasetId + fields props
  web/src/components/RegressionChart.vue        — accept datasetId + fields props
  web/src/components/RecommendationForm.vue     — accept datasetId + fields props

Deleted files:
  web/src/components/ExcelCorrelationChart.vue
  web/src/components/ExcelRegressionChart.vue
  web/src/components/ExcelRecommendationForm.vue
```

---

### Task 1: Add `dataset_id` to AnalysisDatasetRequest schema

**Files:**
- Modify: `src/process_opt/analysis/schemas.py` (line 10-16)

- [ ] **Step 1: Add optional dataset_id field**

```python
class AnalysisDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_fields: list[str] = Field(default=[])
    target_fields: list[str] = Field(default=[])
    missing_strategy: str = "drop_row"
    max_samples: int | None = None
    dataset_id: str | None = None
```

- [ ] **Step 2: Verify no regressions**

Run: `python -m pytest tests/analysis/ -q`
Expected: all existing tests pass (dataset_id is optional, None by default)

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/schemas.py
git commit -m "feat: add optional dataset_id to AnalysisDatasetRequest"
```

---

### Task 2: Add `build_to_dataset_id()` to DatasetBuilder

**Files:**
- Modify: `src/process_opt/analysis/dataset.py` (append at end of DatasetBuilder class)

- [ ] **Step 1: Add method that builds and stores in-memory**

Add this method inside the `DatasetBuilder` class, after `_handle_missing`:

```python
    async def build_to_dataset_id(
        self,
        device_id: str,
        since: datetime | None = None,
    ) -> str:
        from process_opt.analysis.excel import save_dataset

        request = AnalysisDatasetRequest()
        ds = await self.build(request, device_id=device_id, since=since)
        if isinstance(ds, AnalysisError):
            raise AnalysisError(
                code=ds.code,
                message=ds.message,
                suggestion=ds.suggestion,
            )
        return save_dataset(ds)
```

- [ ] **Step 2: Verify method works in a quick test**

Run: `python -m pytest tests/ -q`
Expected: 193 passed (no new failures)

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/dataset.py
git commit -m "feat: add build_to_dataset_id() to DatasetBuilder"
```

---

### Task 3: Add `POST /analysis/dataset/query` and rename upload endpoint

**Files:**
- Modify: `src/process_opt/api/app.py` (inside `if analysis_service is not None:` block)

- [ ] **Step 1: Add dataset/query endpoint**

Insert after the existing excel/upload route handler (around line 410):

```python
        @app.post("/api/v1/analysis/dataset/query")
        async def dataset_query_route(body: dict[str, Any]) -> Any:
            from process_opt.analysis.dataset import DatasetBuilder
            builder = DatasetBuilder(repository._pool)
            device_id = body.get("device_id", "")
            if not device_id:
                raise HTTPException(status_code=400, detail="device_id is required")
            since_raw = body.get("since")
            since = datetime.fromisoformat(since_raw) if since_raw else None
            ds_id = await builder.build_to_dataset_id(device_id, since=since)
            from process_opt.analysis.excel import get_dataset
            ds = get_dataset(ds_id)
            feature_fields = sorted({k for f in ds.features for k in f}) if ds else []
            target_fields = sorted({k for t in ds.targets for k in t}) if ds else []
            return {
                "dataset_id": ds_id,
                "fields": {"features": feature_fields, "targets": target_fields},
                "sample_count": ds.sample_count if ds else 0,
            }
```

- [ ] **Step 2: Rename excel/upload to dataset/upload**

Replace the existing `excel_upload` route:

```python
        @app.post("/api/v1/analysis/dataset/upload")
        async def dataset_upload(file: UploadFile) -> Any:
            from process_opt.analysis.excel import parse_excel, save_dataset
            content = await file.read()
            ds = parse_excel(content)
            ds_id = save_dataset(ds)
            feature_fields = sorted({k for f in ds.features for k in f})
            target_fields = sorted({k for t in ds.targets for k in t})
            return {
                "dataset_id": ds_id,
                "fields": {"features": feature_fields, "targets": target_fields},
                "sample_count": ds.sample_count,
            }
```

- [ ] **Step 3: Add datetime import at top of app.py if missing**

Check `from datetime import datetime` exists at top of `app.py`. If not, add it.

- [ ] **Step 4: Verify endpoints**

Run: `docker compose -f docker-compose.yml up -d --build backend-api`
Then: `curl -s -X POST http://localhost:8000/api/v1/analysis/dataset/query -H 'Content-Type: application/json' -d '{"device_id":"reflow-oven-001"}'`
Expected: returns `{"dataset_id": "...", "fields": {...}, "sample_count": N}`

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/api/app.py
git commit -m "feat: add dataset/query endpoint, rename excel/upload to dataset/upload"
```

---

### Task 4: Add `GET /analysis/dataset/{id}/preview` endpoint

**Files:**
- Modify: `src/process_opt/api/app.py`

- [ ] **Step 1: Add preview endpoint**

Insert after the dataset/upload route:

```python
        @app.get("/api/v1/analysis/dataset/{dataset_id}/preview")
        async def dataset_preview_route(
            dataset_id: str,
            page: int = 1,
            size: int = 50,
        ) -> Any:
            from process_opt.analysis.excel import get_dataset
            ds = get_dataset(dataset_id)
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            total = len(ds.features)
            start = (page - 1) * size
            end = min(start + size, total)

            feature_names = sorted({k for f in ds.features for k in f})
            target_names = sorted({k for t in ds.targets for k in t})

            rows: list[dict[str, Any]] = []
            for i in range(start, end):
                row: dict[str, Any] = {}
                if i < len(ds.metadata):
                    row["_barcode"] = ds.metadata[i].get("barcode", "")
                for fn in feature_names:
                    row[fn] = ds.features[i].get(fn) if i < len(ds.features) else None
                for tn in target_names:
                    row[tn] = ds.targets[i].get(tn) if i < len(ds.targets) else None
                rows.append(row)

            field_meta = {
                "features": [
                    {
                        "name": fn,
                        "type": "numeric",
                        "min": ds.field_summary.get(fn, {}).get("min"),
                        "max": ds.field_summary.get(fn, {}).get("max"),
                    }
                    for fn in feature_names
                ],
                "targets": [
                    {
                        "name": tn,
                        "type": "pass_fail",
                    }
                    for tn in target_names
                ],
            }
            return {
                "rows": rows,
                "total": total,
                "page": page,
                "size": size,
                "fields": field_meta,
            }
```

- [ ] **Step 2: Test preview**

```bash
# Query first
DS_ID=$(curl -s -X POST http://localhost:8000/api/v1/analysis/dataset/query -H 'Content-Type: application/json' -d '{"device_id":"reflow-oven-001"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["dataset_id"])')
# Preview
curl -s "http://localhost:8000/api/v1/analysis/dataset/$DS_ID/preview?page=1&size=3" | python3 -m json.tool | head -20
```
Expected: shows paginated rows and fields metadata

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/api/app.py
git commit -m "feat: add dataset preview endpoint with pagination"
```

---

### Task 5: Unify analysis endpoints to accept `dataset_id`

**Files:**
- Modify: `src/process_opt/api/app.py` (the 4 existing analysis routes: profile, correlation, regression, recommendation)

- [ ] **Step 1: Modify profile route to accept dataset_id**

Replace `profile_route` (line 374):

```python
        @app.post("/api/v1/analysis/profile")
        async def profile_route(body: AnalysisDatasetRequest) -> list[ProfilingResult]:
            if body.dataset_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.profiling import profile_dataset
                ds = get_dataset(body.dataset_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                return profile_dataset(ds)
            return await analysis_service.profile_from_request(body)
```

- [ ] **Step 2: Modify correlation route to accept dataset_id**

Replace `correlation_route` (line 378):

```python
        @app.post("/api/v1/analysis/correlation")
        async def correlation_route(body: dict[str, Any]) -> list[CorrelationResult] | CorrelationResult:
            ds_id = body.get("dataset_id")
            if ds_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.correlation import compute_correlation
                ds = get_dataset(ds_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                field_x = body.get("field_x")
                field_y = body.get("field_y")
                if field_x and field_y:
                    results = compute_correlation(ds, [field_x], [field_y], body.get("method", "pearson"))
                    return results[0]
                feature_cols = sorted({k for f in ds.features for k in f})
                target_cols = sorted({k for t in ds.targets for k in t})
                return compute_correlation(ds, feature_cols, target_cols, body.get("method", "pearson"))
            req = CorrelationRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
            return await analysis_service.correlation(req)
```

- [ ] **Step 3: Modify regression route to accept dataset_id**

Replace `regression_route` (line 386):

```python
        @app.post("/api/v1/analysis/regression")
        async def regression_route(body: dict[str, Any]) -> RegressionResult:
            ds_id = body.get("dataset_id")
            if ds_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.regression import fit_regression
                ds = get_dataset(ds_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                req = RegressionRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
                return fit_regression(ds, req.feature_fields, req.target_field, req.model_type)
            req = RegressionRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
            return await analysis_service.regression(req)
```

- [ ] **Step 4: Modify recommendation route to accept dataset_id**

Replace `recommendation_route` (line 390):

```python
        @app.post("/api/v1/analysis/recommendation")
        async def recommendation_route(body: dict[str, Any]) -> RecommendationResult:
            ds_id = body.get("dataset_id")
            if ds_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.recommendation import compute_recommendation
                ds = get_dataset(ds_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                req = RecommendationRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
                return compute_recommendation(ds, req.feature_fields, req)
            req = RecommendationRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
            return await analysis_service.recommendation(req)
```

- [ ] **Step 5: Run existing tests**

Run: `python -m pytest tests/ -q`
Expected: all existing tests pass (backward compat preserved)

- [ ] **Step 6: Commit**

```bash
git add src/process_opt/api/app.py
git commit -m "feat: unify analysis endpoints to accept optional dataset_id"
```

---

### Task 6: Remove old `/excel/*` routes

**Files:**
- Modify: `src/process_opt/api/app.py`

- [ ] **Step 1: Remove the 5 excel-specific routes**

Delete the following route handlers entirely:
- `excel_upload` (line 398-410) — already replaced by `dataset_upload` in Task 3
- `excel_profile_route` (line 412-419)
- `excel_correlation_route` (line 421-429)
- `excel_regression_route` (line 431-439)
- `excel_recommendation_route` (line 441-449)

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -q`
Expected: all tests pass (no test depends on excel/* routes directly)

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/api/app.py
git commit -m "refactor: remove deprecated excel/* analysis routes"
```

---

### Task 7: Update frontend API client

**Files:**
- Rewrite: `web/src/api/analysis.ts`

- [ ] **Step 1: Write unified API client**

```ts
import client from './client'

export interface DatasetFields {
  features: string[]
  targets: string[]
}

export interface DatasetResult {
  dataset_id: string
  fields: DatasetFields
  sample_count: number
}

export interface FieldMeta {
  name: string
  type: string
  min?: number
  max?: number
}

export interface PreviewResponse {
  rows: Record<string, unknown>[]
  total: number
  page: number
  size: number
  fields: {
    features: FieldMeta[]
    targets: FieldMeta[]
  }
}

export interface CorrelationRequest {
  dataset_id: string
  field_x?: string
  field_y?: string
  method?: string
}

export interface RegressionRequest {
  dataset_id: string
  feature_fields: string[]
  target_field: string
  model_type?: string
}

export interface RecommendationRequest {
  dataset_id: string
  feature_fields: string[]
  target_field: string
  target_value: number
  constraints?: { field: string; min?: number; max?: number }[]
}

export function queryDataset(deviceId: string, since?: string): Promise<DatasetResult> {
  return client.post('/analysis/dataset/query', { device_id: deviceId, since }).then((res) => res.data)
}

export function uploadDataset(file: File): Promise<DatasetResult> {
  const form = new FormData()
  form.append('file', file)
  return client.post('/analysis/dataset/upload', form).then((res) => res.data)
}

export function previewDataset(id: string, page = 1, size = 50): Promise<PreviewResponse> {
  return client.get(`/analysis/dataset/${id}/preview`, { params: { page, size } }).then((res) => res.data)
}

export function profile(datasetId: string): Promise<unknown> {
  return client.post('/analysis/profile', { dataset_id: datasetId }).then((res) => res.data)
}

export function correlation(data: CorrelationRequest): Promise<unknown> {
  return client.post('/analysis/correlation', data).then((res) => res.data)
}

export function regression(data: RegressionRequest): Promise<unknown> {
  return client.post('/analysis/regression', data).then((res) => res.data)
}

export function recommendation(data: RecommendationRequest): Promise<unknown> {
  return client.post('/analysis/recommendation', data).then((res) => res.data)
}

export function submitRecommendation(data?: Record<string, unknown>): Promise<unknown> {
  return client.post('/analysis/recommendation/submit', data).then((res) => res.data)
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/analysis.ts
git commit -m "feat: rewrite API client with unified dataset_id endpoints"
```

---

### Task 8: Create DataPreviewTable component

**Files:**
- Create: `web/src/components/DataPreviewTable.vue`

- [ ] **Step 1: Write DataPreviewTable.vue**

```vue
<template>
  <div class="data-preview">
    <div class="preview-summary">
      <span>共 {{ total }} 条数据 · {{ featureFields.length }} 参数 / {{ targetFields.length }} 结果</span>
      <el-pagination
        v-if="total > size"
        small
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="currentPage"
        @current-change="handlePageChange"
      />
    </div>
    <el-table :data="rows" stripe size="small" v-loading="loading" max-height="420">
      <el-table-column
        v-for="f in featureFields"
        :key="f"
        :label="f"
        :prop="f"
        min-width="120"
      >
        <template #header>
          <span style="color: var(--el-color-primary); font-weight: 600;">{{ f }}</span>
        </template>
        <template #default="{ row }">
          <span class="cell-mono">{{ row[f] != null ? Number(row[f]).toFixed(2) : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        v-for="t in targetFields"
        :key="t"
        :label="t"
        :prop="t"
        min-width="120"
      >
        <template #header>
          <span style="color: #a855f7; font-weight: 600;">{{ t }}</span>
        </template>
        <template #default="{ row }">
          <span class="cell-mono">{{ row[t] ?? '—' }}</span>
        </template>
      </el-table-column>
    </el-table>
    <div class="preview-footer">
      <el-button type="primary" @click="$emit('confirm')">确认数据，前往配置 →</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { FieldMeta } from '@/api/analysis'

const props = defineProps<{
  rows: Record<string, unknown>[]
  total: number
  size: number
  fields: { features: FieldMeta[]; targets: FieldMeta[] }
  loading?: boolean
}>()

defineEmits<{
  'page-change': [page: number]
  confirm: []
}>()

const currentPage = ref(1)

const featureFields = computed(() => props.fields.features.map((f) => f.name))
const targetFields = computed(() => props.fields.targets.map((t) => t.name))

function handlePageChange(page: number) {
  currentPage.value = page
  emit('page-change', page)
}
</script>

<script lang="ts">
import { computed } from 'vue'
const emit = defineEmits<{
  'page-change': [page: number]
  confirm: []
}>()
</script>

<style scoped>
.data-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.cell-mono {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.preview-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
```

Wait — the `defineEmits` usage above has issues (used twice, once without proper access). Let me rewrite cleanly:

```vue
<template>
  <div class="data-preview">
    <div class="preview-summary">
      <span>共 {{ total }} 条数据 · {{ featureCount }} 参数 / {{ targetCount }} 结果</span>
      <el-pagination
        v-if="total > size"
        small
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="$emit('page-change', $event)"
      />
    </div>
    <el-table :data="rows" stripe size="small" v-loading="loading" max-height="420" empty-text="暂无数据">
      <el-table-column
        v-for="f in props.fields.features" :key="f.name" :label="f.name" :prop="f.name" min-width="130"
      >
        <template #header>
          <span class="feature-header">{{ f.name }}</span>
        </template>
        <template #default="{ row }">
          <span class="cell-mono">{{ row[f.name] !== null && row[f.name] !== undefined ? Number(row[f.name]).toFixed(2) : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        v-for="t in props.fields.targets" :key="t.name" :label="t.name" :prop="t.name" min-width="140"
      >
        <template #header>
          <span class="target-header">{{ t.name }}</span>
        </template>
        <template #default="{ row }">
          <el-tag v-if="row[t.name] === 'pass'" size="small" type="success">pass</el-tag>
          <el-tag v-else-if="row[t.name] === 'fail'" size="small" type="danger">fail</el-tag>
          <span v-else class="cell-mono">{{ row[t.name] ?? '—' }}</span>
        </template>
      </el-table-column>
    </el-table>
    <div class="preview-footer">
      <el-button type="primary" @click="$emit('confirm')">确认数据，前往配置 →</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldMeta } from '@/api/analysis'

const props = defineProps<{
  rows: Record<string, unknown>[]
  total: number
  size: number
  page: number
  fields: { features: FieldMeta[]; targets: FieldMeta[] }
  loading?: boolean
}>()

defineEmits<{
  'page-change': [page: number]
  confirm: []
}>()

const featureCount = props.fields.features.length
const targetCount = props.fields.targets.length
</script>

<style scoped>
.data-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.feature-header {
  color: var(--el-color-primary);
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.target-header {
  color: #a855f7;
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.cell-mono {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.preview-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
```

- [ ] **Step 2: Verify component builds**

Run: `cd web && npx vue-tsc --noEmit 2>&1 | head -5`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/DataPreviewTable.vue
git commit -m "feat: add DataPreviewTable component with feature/target color columns"
```

---

### Task 9: Create FieldCheckboxGrid component

**Files:**
- Create: `web/src/components/FieldCheckboxGrid.vue`

- [ ] **Step 1: Write FieldCheckboxGrid.vue**

```vue
<template>
  <div class="field-grid">
    <div class="field-section">
      <h4 class="section-title">📊 参数字段 (Feature)</h4>
      <div class="card-grid">
        <div
          v-for="f in features"
          :key="f.name"
          class="field-card"
          :class="{ selected: selectedFeatures.includes(f.name) }"
          @click="toggleFeature(f.name)"
        >
          <div class="card-checkbox">
            <span v-if="selectedFeatures.includes(f.name)" class="check filled">✓</span>
            <span v-else class="check empty"></span>
          </div>
          <div class="card-body">
            <div class="card-name">{{ f.name }}</div>
            <div class="card-type">{{ f.type }}{{ f.min != null ? ` · ${f.min}–${f.max}` : '' }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="field-section">
      <h4 class="section-title">🎯 结果字段 (Target)</h4>
      <div class="card-grid">
        <div
          v-for="t in targets"
          :key="t.name"
          class="field-card target"
          :class="{ selected: selectedTargets.includes(t.name) }"
          @click="toggleTarget(t.name)"
        >
          <div class="card-checkbox">
            <span v-if="selectedTargets.includes(t.name)" class="check filled target">✓</span>
            <span v-else class="check empty"></span>
          </div>
          <div class="card-body">
            <div class="card-name">{{ t.name }}</div>
            <div class="card-type">{{ t.type }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="field-actions">
      <el-button text size="small" @click="selectAllFeatures">全选参数</el-button>
      <el-button text size="small" @click="selectAllTargets">全选结果</el-button>
      <el-button text size="small" @click="clearAll">清空</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FieldMeta } from '@/api/analysis'

const props = defineProps<{
  fields: { features: FieldMeta[]; targets: FieldMeta[] }
}>()

const emit = defineEmits<{
  'update:selectedFeatures': [names: string[]]
  'update:selectedTargets': [names: string[]]
}>()

const selectedFeatures = ref<string[]>(props.fields.features.map((f) => f.name))
const selectedTargets = ref<string[]>(props.fields.targets.filter((f) => f.type === 'numeric').map((f) => f.name))

function toggleFeature(name: string) {
  const idx = selectedFeatures.value.indexOf(name)
  if (idx >= 0) {
    selectedFeatures.value.splice(idx, 1)
  } else {
    selectedFeatures.value.push(name)
  }
  emit('update:selectedFeatures', [...selectedFeatures.value])
}

function toggleTarget(name: string) {
  const idx = selectedTargets.value.indexOf(name)
  if (idx >= 0) {
    selectedTargets.value.splice(idx, 1)
  } else {
    selectedTargets.value.push(name)
  }
  emit('update:selectedTargets', [...selectedTargets.value])
}

function selectAllFeatures() {
  selectedFeatures.value = props.fields.features.map((f) => f.name)
  emit('update:selectedFeatures', [...selectedFeatures.value])
}

function selectAllTargets() {
  selectedTargets.value = props.fields.targets.map((t) => t.name)
  emit('update:selectedTargets', [...selectedTargets.value])
}

function clearAll() {
  selectedFeatures.value = []
  selectedTargets.value = []
  emit('update:selectedFeatures', [])
  emit('update:selectedTargets', [])
}

defineExpose({ selectedFeatures, selectedTargets })
</script>

<style scoped>
.field-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field-section {
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}
.field-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--el-bg-color);
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.field-card.selected {
  border-color: var(--el-color-primary);
  background: rgba(var(--el-color-primary-rgb), 0.06);
}
.field-card.target.selected {
  border-color: #a855f7;
  background: rgba(168, 85, 247, 0.06);
}
.field-card:hover {
  border-color: var(--el-color-primary-light-3);
}
.card-checkbox {
  flex-shrink: 0;
}
.check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  font-size: 11px;
}
.check.empty {
  border: 2px solid var(--el-border-color-darker);
}
.check.filled {
  background: var(--el-color-primary);
  color: #fff;
  border-color: var(--el-color-primary);
}
.check.filled.target {
  background: #a855f7;
  border-color: #a855f7;
}
.card-body {
  min-width: 0;
}
.card-name {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-type {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  margin-top: 2px;
}
.field-actions {
  display: flex;
  gap: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/FieldCheckboxGrid.vue
git commit -m "feat: add FieldCheckboxGrid component with checkbox cards"
```

---

### Task 10: Modify CorrelationChart to accept datasetId prop

**Files:**
- Modify: `web/src/components/CorrelationChart.vue`

- [ ] **Step 1: Rewrite component to use props**

Full replacement:

```vue
<template>
  <div>
    <div v-if="!autoMode" class="correlation-form">
      <el-form inline>
        <el-form-item label="参数 X">
          <el-select v-model="fieldX" style="width: 180px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数 Y">
          <el-select v-model="fieldY" style="width: 180px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper">
      <div v-if="results.length" class="correlation-results">
        <div v-for="r in results" :key="r.field_x + '|' + r.field_y" class="correlation-card">
          <div class="correlation-pair">{{ r.field_x }} × {{ r.field_y }}</div>
          <div class="correlation-stats">
            <span>r = {{ r.coefficient.toFixed(4) }}</span>
            <span>p = {{ r.p_value.toFixed(4) }}</span>
          </div>
          <el-progress
            :percentage="Math.abs(r.coefficient) * 100"
            :color="r.coefficient > 0 ? '#3b82f6' : '#ef4444'"
            :stroke-width="8"
          />
        </div>
      </div>
      <el-empty v-else description="选择参数后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { correlation } from '@/api/analysis'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const fieldX = ref('')
const fieldY = ref('')
const results = ref<{ field_x: string; field_y: string; coefficient: number; p_value: number; method: string }[]>([])

const allFields = computed(() => [...props.featureFields, ...props.targetFields])

async function handleCompute() {
  if (!fieldX.value || !fieldY.value) return
  loading.value = true
  try {
    const r = await correlation({
      dataset_id: props.datasetId,
      field_x: fieldX.value,
      field_y: fieldY.value,
      method: 'pearson',
    }) as { field_x: string; field_y: string; coefficient: number; p_value: number; method: string }
    results.value = [r]
  } finally {
    loading.value = false
  }
}

watch(() => props.autoMode, (v) => {
  if (v) {
    autoCompute()
  }
}, { immediate: true })

watch(() => [props.datasetId, props.featureFields.length, props.targetFields.length], () => {
  if (props.autoMode) {
    autoCompute()
  }
})

async function autoCompute() {
  if (!props.datasetId || !props.featureFields.length || !props.targetFields.length) return
  loading.value = true
  try {
    results.value = await correlation({
      dataset_id: props.datasetId,
      method: 'pearson',
    }) as unknown as { field_x: string; field_y: string; coefficient: number; p_value: number; method: string }[]
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.correlation-form {
  margin-bottom: 12px;
}
.chart-wrapper {
  min-height: 120px;
}
.correlation-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.correlation-card {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
}
.correlation-pair {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin-bottom: 4px;
}
.correlation-stats {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
</style>
```

- [ ] **Step 2: Verify type-check**

Run: `cd web && npx vue-tsc --noEmit 2>&1 | head -5`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/CorrelationChart.vue
git commit -m "feat: refactor CorrelationChart to accept datasetId and fields props"
```

---

### Task 11: Modify RegressionChart to accept datasetId prop

**Files:**
- Modify: `web/src/components/RegressionChart.vue`

- [ ] **Step 1: Rewrite component**

Full replacement:

```vue
<template>
  <div>
    <div v-if="!autoMode" class="regression-form">
      <el-form inline>
        <el-form-item label="目标结果">
          <el-select v-model="targetField" style="width: 180px">
            <el-option v-for="f in props.targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper">
      <div v-for="r in results" :key="r.target" class="regression-card">
        <div class="regression-target">{{ r.target }}</div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="R²">{{ r.r_squared.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="RMSE">{{ r.rmse.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ r.model_type }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <el-empty v-if="!results.length && !loading" description="选择参数后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { regression } from '@/api/analysis'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const targetField = ref('')
const results = ref<{ target: string; r_squared: number; rmse: number; model_type: string }[]>([])

async function handleCompute() {
  if (!targetField.value || !props.featureFields.length) return
  loading.value = true
  try {
    const r = await regression({
      dataset_id: props.datasetId,
      feature_fields: props.featureFields,
      target_field: targetField.value,
      model_type: 'linear',
    }) as { r_squared: number; rmse: number; model_type: string }
    results.value = [{ target: targetField.value, ...r }]
  } finally {
    loading.value = false
  }
}

watch(() => props.autoMode, (v) => {
  if (v) autoCompute()
}, { immediate: true })

watch(() => [props.datasetId, props.featureFields.length, props.targetFields.length], () => {
  if (props.autoMode) autoCompute()
})

async function autoCompute() {
  if (!props.datasetId || !props.featureFields.length || !props.targetFields.length) return
  loading.value = true
  const out: { target: string; r_squared: number; rmse: number; model_type: string }[] = []
  try {
    for (const t of props.targetFields) {
      const r = await regression({
        dataset_id: props.datasetId,
        feature_fields: props.featureFields,
        target_field: t,
        model_type: 'linear',
      }) as { r_squared: number; rmse: number; model_type: string }
      out.push({ target: t, ...r })
    }
    results.value = out
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.regression-form {
  margin-bottom: 12px;
}
.chart-wrapper {
  min-height: 120px;
}
.regression-card {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
  margin-bottom: 8px;
}
.regression-target {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/RegressionChart.vue
git commit -m "feat: refactor RegressionChart to accept datasetId and fields props"
```

---

### Task 12: Modify RecommendationForm to accept datasetId prop

**Files:**
- Modify: `web/src/components/RecommendationForm.vue`

- [ ] **Step 1: Rewrite component**

Since RecommendationForm is the largest component (174 lines), the key change is replacing the Pinia store dependency with `props`:

```vue
<template>
  <div>
    <div class="rec-form">
      <el-form label-width="100px">
        <el-form-item label="目标字段">
          <el-select v-model="cfg.targetField" style="width: 200px">
            <el-option v-for="f in props.targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标值">
          <el-input-number v-model="cfg.targetValue" :min="0" :step="0.1" />
        </el-form-item>
        <el-form-item v-for="f in props.featureFields" :key="f" :label="f">
          <el-slider v-model="cfg.constraints[f]" :min="0" :max="500" :step="0.5" style="width: 260px" />
          <span class="slider-val">{{ cfg.constraints[f].toFixed(1) }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算推荐</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div v-if="result" class="rec-result">
      <h4>推荐参数</h4>
      <div v-for="(v, k) in result.recommended_parameters" :key="k" class="rec-row">
        <span class="rec-name">{{ k }}</span>
        <span class="rec-value">{{ v.toFixed(1) }}</span>
      </div>
      <div class="rec-prediction">预期目标值: {{ result.predicted_target.toFixed(4) }}</div>
      <div v-if="result.risk_notes.length" class="risk-notes">
        <p v-for="(n, i) in result.risk_notes" :key="i" class="risk-note">⚠ {{ n }}</p>
      </div>
      <el-button type="success" size="small" @click="handleSubmit" style="margin-top: 12px;">提交到参数管理</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { recommendation, submitRecommendation } from '@/api/analysis'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
}>()

const loading = ref(false)
const result = ref<{
  recommended_parameters: Record<string, number>
  predicted_target: number
  risk_notes: string[]
} | null>(null)

const cfg = reactive<{
  targetField: string
  targetValue: number
  constraints: Record<string, number>
}>({
  targetField: '',
  targetValue: 0,
  constraints: {},
})

async function handleCompute() {
  if (!cfg.targetField || !props.featureFields.length) return
  loading.value = true
  try {
    const constraints = Object.entries(cfg.constraints).map(([field, max]) => ({
      field,
      max: max || undefined,
    }))
    result.value = await recommendation({
      dataset_id: props.datasetId,
      feature_fields: props.featureFields,
      target_field: cfg.targetField,
      target_value: cfg.targetValue,
      constraints,
    }) as typeof result.value
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!result.value) return
  await submitRecommendation({
    device_type: 'imported',
    parameters: result.value.recommended_parameters,
  })
}
</script>

<style scoped>
.rec-form {
  margin-bottom: 16px;
}
.slider-val {
  margin-left: 10px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.rec-result {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 14px;
  border: 1px solid var(--el-border-color-light);
}
.rec-result h4 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
}
.rec-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid var(--el-border-color-light);
}
.rec-name {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: var(--el-color-primary);
}
.rec-value {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
}
.rec-prediction {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 8px;
}
.risk-notes {
  margin-top: 8px;
}
.risk-note {
  font-size: 11px;
  color: var(--el-color-warning);
  margin: 2px 0;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/RecommendationForm.vue
git commit -m "feat: refactor RecommendationForm to accept datasetId and fields props"
```

---

### Task 13: Delete 3 Excel-specific components

**Files:**
- Delete: `web/src/components/ExcelCorrelationChart.vue`
- Delete: `web/src/components/ExcelRegressionChart.vue`
- Delete: `web/src/components/ExcelRecommendationForm.vue`

- [ ] **Step 1: Delete files**

Run:
```bash
rm web/src/components/ExcelCorrelationChart.vue
rm web/src/components/ExcelRegressionChart.vue
rm web/src/components/ExcelRecommendationForm.vue
```

- [ ] **Step 2: Verify no imports reference these files**

Run: `cd web && rg "ExcelCorrelation\|ExcelRegression\|ExcelRecommendation" --type vue --type ts`
Expected: no results (only AnalysisView.vue may reference them, but we'll rewrite it next)

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ExcelCorrelationChart.vue web/src/components/ExcelRegressionChart.vue web/src/components/ExcelRecommendationForm.vue
git commit -m "refactor: delete Excel-specific chart components (unified into base components)"
```

---

### Task 14: Rewrite AnalysisView.vue as state-machine workflow

**Files:**
- Rewrite: `web/src/views/AnalysisView.vue`

- [ ] **Step 1: Write the new AnalysisView.vue**

Due to the component's size (~280 lines), here is the complete rewritten version:

```vue
<template>
  <div class="analysis">
    <div class="analysis-header">
      <h2 class="page-title">参数调优</h2>
      <p class="page-desc">工艺参数统计分析与优化</p>
    </div>

    <!-- Step 1: Import -->
    <div v-if="state === 'import'" class="step-wrap">
      <div class="import-cards">
        <el-card shadow="hover" class="import-card" :class="{ active: importMode === 'db' }" @click="importMode = 'db'">
          <div class="import-icon">🗄️</div>
          <h3>在线查询</h3>
          <p>从数据库查询设备历史数据</p>
          <div v-if="importMode === 'db'" class="import-body">
            <el-form inline>
              <el-form-item label="设备">
                <el-select v-model="filterDevice" placeholder="选择设备" style="width: 200px">
                  <el-option v-for="d in devices" :key="d" :label="d" :value="d" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleOnlineQuery" :loading="loading">查询数据</el-button>
              </el-form-item>
            </el-form>
            <div v-if="importError" class="import-error">{{ importError }}</div>
          </div>
        </el-card>
        <el-card shadow="hover" class="import-card" :class="{ active: importMode === 'excel' }" @click="importMode = 'excel'">
          <div class="import-icon">📂</div>
          <h3>上传 Excel</h3>
          <p>拖拽 .xlsx / .xls 文件解析数据</p>
          <div v-if="importMode === 'excel'" class="import-body">
            <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls" :on-change="handleFileChange" :file-list="fileList">
              <div class="upload-hint">
                <el-icon size="20"><UploadFilled /></el-icon>
                <span>拖拽或点击选择文件</span>
              </div>
            </el-upload>
            <el-button type="primary" @click="handleExcelUpload" :loading="loading" :disabled="!fileList.length" style="margin-top: 8px;">
              上传解析
            </el-button>
            <div v-if="importError" class="import-error">{{ importError }}</div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- Step 2: Preview -->
    <div v-if="state === 'preview'" class="step-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">2</span>
          <span class="step-title">数据预览</span>
        </div>
        <el-button text size="small" @click="goImport">← 重新导入</el-button>
      </div>
      <DataPreviewTable
        :rows="previewRows"
        :total="previewTotal"
        :size="50"
        :page="previewPage"
        :fields="previewFields"
        :loading="previewLoading"
        @page-change="handlePreviewPage"
        @confirm="goConfig"
      />
    </div>

    <!-- Step 3: Config -->
    <div v-if="state === 'config'" class="step-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">3</span>
          <span class="step-title">配置分析参数</span>
        </div>
        <el-button text size="small" @click="state = 'preview'">← 返回预览</el-button>
      </div>
      <FieldCheckboxGrid
        ref="fieldGridRef"
        :fields="previewFields"
        @update:selected-features="selectedFeatures = $event"
        @update:selected-targets="selectedTargets = $event"
      />
      <div class="config-actions">
        <el-button type="primary" size="large" @click="goReport" :loading="analyzing">🔍 开始分析</el-button>
      </div>
    </div>

    <!-- Step 4: Loading -->
    <div v-if="state === 'loading'" class="step-wrap loading-state">
      <el-icon class="is-loading" size="28"><Loading /></el-icon>
      <p>正在执行分析... {{ loadingProgress }}</p>
    </div>

    <!-- Step 5: Report -->
    <div v-if="state === 'report'" class="report-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">4</span>
          <span class="step-title">分析报告</span>
        </div>
        <div class="step-actions">
          <el-button text size="small" @click="state = 'config'">调整参数</el-button>
          <el-button text size="small" @click="goImport">重新导入</el-button>
        </div>
      </div>
      <div class="report-layout">
        <nav class="report-nav">
          <a v-for="item in navItems" :key="item.id" :href="'#' + item.id" class="nav-item" :class="{ active: activeNav === item.id }" @click.prevent="scrollTo(item.id)">
            {{ item.icon }} {{ item.label }}
          </a>
        </nav>
        <div class="report-content" @scroll="onReportScroll" ref="reportContentRef">
          <section id="report-overview">
            <h3>📋 数据概览</h3>
            <el-row :gutter="12">
              <el-col :span="6"><el-card><div class="stat-num">{{ sampleCount }}</div><div class="stat-label">样本数</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: var(--el-color-primary)">{{ selectedFeatures.length }}</div><div class="stat-label">参数字段</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: #a855f7">{{ selectedTargets.length }}</div><div class="stat-label">结果字段</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: var(--el-color-warning)">{{ missingCount }}</div><div class="stat-label">缺失值</div></el-card></el-col>
            </el-row>
          </section>
          <section id="report-profile">
            <h3>📊 字段分析</h3>
            <div v-if="profileData.length" class="profile-grid">
              <el-card v-for="stat in profileData" :key="stat.field" class="profile-card" shadow="hover">
                <template #header>
                  <span class="profile-field">{{ stat.field }}</span>
                </template>
                <div class="profile-stats">
                  <div class="profile-stat"><span>Mean</span><span>{{ stat.mean?.toFixed(4) ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Std</span><span>{{ stat.std?.toFixed(4) ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Min</span><span>{{ stat.min ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Max</span><span>{{ stat.max ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Missing</span><span>{{ stat.missing_count }} ({{ (stat.missing_rate * 100).toFixed(1) }}%)</span></div>
                </div>
              </el-card>
            </div>
            <el-empty v-else description="无分析数据" :image-size="60" />
          </section>
          <section id="report-correlation">
            <h3>🔗 相关性</h3>
            <CorrelationChart :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" :auto-mode="true" />
          </section>
          <section id="report-regression">
            <h3>📈 回归分析</h3>
            <RegressionChart :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" :auto-mode="true" />
          </section>
          <section id="report-recommendation">
            <h3>💡 参数推荐</h3>
            <RecommendationForm :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" />
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, computed, onMounted, nextTick } from 'vue'
import { queryDataset, uploadDataset, previewDataset, profile as apiProfile, type PreviewResponse } from '@/api/analysis'
import { listDevices as fetchDevices } from '@/api/records'
import DataPreviewTable from '@/components/DataPreviewTable.vue'
import FieldCheckboxGrid from '@/components/FieldCheckboxGrid.vue'
import CorrelationChart from '@/components/CorrelationChart.vue'
import RegressionChart from '@/components/RegressionChart.vue'
import RecommendationForm from '@/components/RecommendationForm.vue'
import { UploadFilled, Loading } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

type Step = 'import' | 'preview' | 'config' | 'loading' | 'report'

const state = ref<Step>('import')
const importMode = ref<'db' | 'excel'>('db')
const loading = ref(false)
const importError = ref('')
const analyzing = ref(false)
const loadingProgress = ref('')

const devices = ref<string[]>([])
const filterDevice = ref('')
const fileList = ref<UploadFile[]>([])

const datasetId = ref<string | null>(null)
const sampleCount = ref(0)

const previewRows = ref<Record<string, unknown>[]>([])
const previewTotal = ref(0)
const previewPage = ref(1)
const previewLoading = ref(false)
const previewFields = ref<PreviewResponse['fields']>({ features: [], targets: [] })

const selectedFeatures = ref<string[]>([])
const selectedTargets = ref<string[]>([])

const profileData = ref<{ field: string; mean: number | null; std: number | null; min: number | null; max: number | null; missing_count: number; missing_rate: number }[]>([])
const missingCount = ref(0)
const fieldGridRef = ref<InstanceType<typeof FieldCheckboxGrid> | null>(null)

const activeNav = ref('report-overview')
const reportContentRef = ref<HTMLElement | null>(null)

const navItems = [
  { id: 'report-overview', icon: '📋', label: '数据概览' },
  { id: 'report-profile', icon: '📊', label: '字段分析' },
  { id: 'report-correlation', icon: '🔗', label: '相关性' },
  { id: 'report-regression', icon: '📈', label: '回归' },
  { id: 'report-recommendation', icon: '💡', label: '推荐' },
]

async function loadDevices() {
  try {
    devices.value = await fetchDevices()
    if (devices.value.length && !filterDevice.value) {
      filterDevice.value = devices.value[0]
    }
  } catch {
    // silent
  }
}

function handleFileChange(file: UploadFile) {
  fileList.value = [file]
  importError.value = ''
}

async function handleOnlineQuery() {
  if (!filterDevice.value) return
  loading.value = true
  importError.value = ''
  try {
    const r = await queryDataset(filterDevice.value)
    setDataset(r, 'db')
  } catch (e: any) {
    importError.value = e?.response?.data?.message || e?.message || '查询失败'
  } finally {
    loading.value = false
  }
}

async function handleExcelUpload() {
  const f = fileList.value[0]?.raw
  if (!f) return
  loading.value = true
  importError.value = ''
  try {
    const r = await uploadDataset(f)
    setDataset(r, 'excel')
  } catch (e: any) {
    importError.value = e?.response?.data?.message || e?.message || '上传失败'
  } finally {
    loading.value = false
  }
}

function setDataset(r: { dataset_id: string; fields: { features: string[]; targets: string[] }; sample_count: number }, _source: string) {
  datasetId.value = r.dataset_id
  sampleCount.value = r.sample_count
  state.value = 'preview'
  loadPreview()
}

async function loadPreview() {
  if (!datasetId.value) return
  previewLoading.value = true
  try {
    const r = await previewDataset(datasetId.value, previewPage.value, 50)
    previewRows.value = r.rows
    previewTotal.value = r.total
    previewFields.value = r.fields
  } finally {
    previewLoading.value = false
  }
}

async function handlePreviewPage(page: number) {
  previewPage.value = page
  await loadPreview()
}

function goConfig() {
  state.value = 'config'
  selectedFeatures.value = previewFields.value.features.map((f) => f.name)
  selectedTargets.value = previewFields.value.targets.filter((f) => f.type === 'numeric').map((f) => f.name)
}

async function goReport() {
  if (!datasetId.value || !selectedFeatures.value.length || !selectedTargets.value.length) return
  state.value = 'loading'
  analyzing.value = true
  loadingProgress.value = ''
  try {
    loadingProgress.value = '1/4 字段分析...'
    const pf = await apiProfile(datasetId.value) as { field: string; mean: number | null; std: number | null; min: number | null; max: number | null; missing_count: number; missing_rate: number }[]
    profileData.value = pf
    missingCount.value = pf.reduce((s, x) => s + (x.missing_count || 0), 0)

    // Correlation, regression, and recommendation are rendered by their components in autoMode
    // They will auto-compute when they mount with datasetId + fields props

    state.value = 'report'
    await nextTick()
    // Activate first nav item
    activeNav.value = 'report-overview'
  } finally {
    analyzing.value = false
    loadingProgress.value = ''
  }
}

function goImport() {
  state.value = 'import'
  datasetId.value = null
  previewRows.value = []
  previewFields.value = { features: [], targets: [] }
  selectedFeatures.value = []
  selectedTargets.value = []
  profileData.value = []
  importError.value = ''
  fileList.value = []
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  activeNav.value = id
}

function onReportScroll() {
  const el = reportContentRef.value
  if (!el) return
  for (const item of [...navItems].reverse()) {
    const section = document.getElementById(item.id)
    if (section && section.offsetTop <= el.scrollTop + 100) {
      activeNav.value = item.id
      break
    }
  }
}

onMounted(loadDevices)
</script>

<style scoped>
.analysis-header { margin-bottom: 16px; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0 0 2px; color: var(--el-text-color-primary); }
.page-desc { font-size: 12px; color: var(--el-text-color-secondary); margin: 0; }

.step-wrap { margin-top: 12px; }
.step-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: var(--el-color-primary); border-radius: 50%; color: #fff; font-size: 12px; font-weight: 600; margin-right: 8px; }
.step-title { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); }
.step-actions { display: flex; gap: 8px; }

.import-cards { display: flex; gap: 16px; }
.import-card { flex: 1; padding: 4px; cursor: pointer; border: 2px solid transparent; transition: border-color 0.2s; }
.import-card.active { border-color: var(--el-color-primary); }
.import-card h3 { margin: 4px 0 2px; font-size: 15px; }
.import-card p { font-size: 12px; color: var(--el-text-color-secondary); margin: 0 0 8px; }
.import-icon { font-size: 24px; }
.import-body { margin-top: 8px; }
.import-error { color: var(--el-color-danger); font-size: 12px; margin-top: 8px; }
.upload-hint { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 12px; color: var(--el-text-color-secondary); padding: 12px; }

.config-actions { margin-top: 20px; display: flex; justify-content: flex-end; }

.loading-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 200px; gap: 12px; font-size: 14px; color: var(--el-text-color-secondary); }

.report-wrap { margin-top: 12px; }
.report-layout { display: flex; gap: 16px; margin-top: 12px; }
.report-nav { width: 140px; flex-shrink: 0; }
.report-nav .nav-item { display: block; padding: 6px 8px; font-size: 12px; color: var(--el-text-color-secondary); text-decoration: none; border-left: 2px solid transparent; cursor: pointer; transition: all 0.2s; }
.report-nav .nav-item:hover { color: var(--el-color-primary); }
.report-nav .nav-item.active { color: var(--el-color-primary); border-left-color: var(--el-color-primary); font-weight: 500; }
.report-content { flex: 1; max-height: calc(100vh - 200px); overflow-y: auto; }
.report-content section { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-light); }
.report-content section:last-child { border-bottom: none; }
.report-content h3 { font-size: 15px; font-weight: 600; margin: 0 0 12px; }

.stat-num { font-family: 'Fira Code', monospace; font-size: 24px; font-weight: 700; text-align: center; }
.stat-label { font-size: 11px; color: var(--el-text-color-secondary); text-align: center; margin-top: 4px; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.profile-card { }
.profile-card :deep(.el-card__header) { padding: 8px 12px; }
.profile-field { font-family: 'Fira Code', monospace; font-size: 13px; font-weight: 500; color: var(--el-color-primary); }
.profile-stats { display: flex; flex-direction: column; gap: 4px; }
.profile-stat { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; border-bottom: 1px solid var(--el-border-color-light); }
.profile-stat span:first-child { color: var(--el-text-color-secondary); }
.profile-stat span:last-child { font-family: 'Fira Code', monospace; font-weight: 500; }
</style>
```

- [ ] **Step 2: Verify type-check**

Run: `cd web && npx vue-tsc --noEmit 2>&1`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/src/views/AnalysisView.vue
git commit -m "feat: rewrite AnalysisView as state-machine workflow (import→preview→config→report)"
```

---

### Task 15: Remove AnalysisFilter import and Pinia store dependency cleanup

**Files:**
- Modify: `web/src/views/AnalysisView.vue` (already handled in Task 14 — the new version doesn't import AnalysisFilter or use Pinia)

- [ ] **Step 1: Verify AnalysisFilter is not imported elsewhere**

Run: `cd web && rg "AnalysisFilter" --type vue --type ts`
Expected: no results (it was only used by AnalysisView.vue)

If there are still references, remove them. The AnalysisFilter component stays in the codebase but is no longer imported — it can be removed in a future cleanup.

- [ ] **Step 2: Commit (if changes needed)**

If no changes needed, skip.

---

### Task 16: Final verification

**Files:** — (verification only)

- [ ] **Step 1: Rebuild backend and run tests**

Run:
```bash
docker compose -f docker-compose.yml up -d --build backend-api
python -m pytest tests/ -q
```
Expected: 193 passed

- [ ] **Step 2: Type-check frontend**

Run: `cd web && npx vue-tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Build frontend**

Run: `cd web && npx vite build`
Expected: builds successfully

- [ ] **Step 4: Rebuild docker**

Run: `docker compose -f docker-compose.yml up -d --build`
Expected: all containers healthy

- [ ] **Step 5: Smoke test**

1. Open `http://localhost:8000`, navigate to 参数调优
2. Click "在线查询" → select device → click "查询数据" → verify table shows data → click "确认数据，前往配置"
3. Verify checkbox grid shows feature/target fields → select some → click "开始分析" → verify report loads
4. Go back, try "上传 Excel" → verify same flow
5. Navigate to 仪表盘, 原始数据, 线体拓扑, 参数管理 — verify no regressions

- [ ] **Step 6: Commit any final changes**

```bash
git add -A
git commit -m "chore: final verification, all tests pass, type-check clean"
```
