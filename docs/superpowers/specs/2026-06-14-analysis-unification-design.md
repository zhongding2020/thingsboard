# Analysis Module Unification Design

**Date:** 2026-06-14
**Status:** design

## Motivation

The current `/analysis` page (AnalysisView.vue) has two parallel modes — "在线分析" and "手动分析" — that differ only in how data is imported (DB query vs Excel upload). After import, all 4 analysis operations (profile, correlation, regression, recommendation) are identical in logic, yet the codebase maintains 6 nearly-duplicate Vue components and 11 API endpoints (5 online + 5 Excel + 1 upload + 1 submit). This causes:

- 3 pairs of duplicated components (CorrelationChart/ExcelCorrelationChart, etc.)
- Profile card rendering inlined twice in AnalysisView.vue
- Backend has `/analysis/excel/*` prefix for the same functions that `/analysis/*` serves
- Navigation forces the user to switch top-level Tabs between modes before seeing analysis

## Goal

Unify the two modes into a single four-step workflow: import data → preview → configure → generate report. After data is loaded (regardless of source), everything downstream shares the same UI, components, and API paths.

## Design

### Frontend — Four-Step Workflow

AnalysisView.vue is rewritten as a **state-machine-driven single page** with 5 states:

| State | UI | Trigger |
|---|---|---|
| `import` | Two cards: "在线查询" (device selector, time range) + "上传Excel" (drag-drop) | Page load / "重新导入" |
| `preview` | Data table with pagination, Feature/Target color-coded headers, row count display | Data loaded (online query or Excel parsed) |
| `config` | Checkbox-card field selector + Recommendation target/value/constraint inputs | User clicks "确认数据，前往配置" |
| `loading` | Progress indicator, 4 API calls in parallel | User clicks "开始分析" |
| `report` | Left sticky anchor nav + right scrollable report blocks | All 4 API calls complete |

States are forward-only (import → preview → config → report) except from report, where user can go back to config ("调整参数") or import ("重新导入").

```
┌─────────┐  data loaded  ┌─────────┐  confirm   ┌─────────┐  analyze   ┌─────────┐  done  ┌─────────┐
│ import  │ ────────────→ │ preview │ ─────────→ │ config  │ ─────────→ │ loading │ ─────→ │ report  │
└─────────┘               └─────────┘            └─────────┘            └─────────┘        └─────────┘
     ↑                        ↑                       ↑                                      │
     └────────────────────────┴───────────────────────┴──────────────── "重新导入" ──────────┘
                                                                      "调整参数" ────────────┘
```

#### Step 1: import

Replace the two-tab layout with two side-by-side cards:

- **在线查询** card: Reuses AnalysisFilter component (device picker, datetime range). When user clicks "查询数据", calls `POST /analysis/dataset/query` with `{device_id, since?, until?}` → gets `dataset_id`.
- **上传Excel** card: Simplified upload area. When file is dropped, calls `POST /analysis/dataset/upload` (FormData) → gets `dataset_id`.

Both cards are visible simultaneously; the user picks one.

#### Step 2: preview

After `dataset_id` is obtained, call `GET /analysis/dataset/{id}/preview?page=1&size=50` to fetch paginated raw data rows. Display as an Element Plus table:

- Feature columns (numeric) with blue header background
- Target columns (pass/fail or numeric result) with purple header background
- Pagination controls (page size 50)
- "确认数据，前往配置 →" button below the table

The table is read-only. No editing or filtering at this stage.

#### Step 3: config

Auto-infer field roles from dataset metadata (feature vs target, based on value types). Display two checkbox-card grids:

**Feature 字段** — grid of 2 or 3 columns:
```
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│ ☑ temperature       │ │ ☑ conveyor_speed    │ │ ☐ pressure          │
│  min:100  max:300    │ │  min:10  max:100     │ │  min:50  max:200     │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
```

**Target 字段** — same grid layout, purple accent:
```
┌──────────────────────┐ ┌──────────────────────┐
│ ☑ solder_joint_qty  │ │ ☑ voiding_pct       │
│  pass/fail           │ │  min:0  max:5        │
└──────────────────────┘ └──────────────────────┘
```

Each card shows: field name, type hint (numeric / pass_fail / value range), and a checkbox. Selected cards get a blue (feature) or purple (target) border + filled checkbox.

Below the grids: **Recommendation 参数** (collapsible section):
- Target field dropdown (from selected target fields)
- Target value input
- Per-feature constraint sliders (range from profile data min/max, default to full range)

"开始分析" button at bottom triggers step 4.

#### Step 4: report

Single-page scrollable report. Two-column layout:

**Left: sticky anchor nav** (150px wide, `position: sticky; top: 12px`):
- Highlights current section on scroll (IntersectionObserver)
- Click to smooth-scroll to section
- "导出报告" button at bottom

**Right: report content** (5 sections):

1. **📋 数据概览** — Stat cards: sample count, feature count, target count, missing values. Source info (online/Excel, device name, time range).
2. **📊 字段分析** — Profile cards in 2–3 column grid. Each card: field name, mean/σ/min/max, missing rate, IQR outlier count, inline mini-distribution bar.
3. **🔗 相关性** — ECharts heatmap (all feature × all target correlation coefficients). Hover shows r-value and p-value.
4. **📈 回归** — For each target field: ECharts regression plot (scatter + fitted line), R² value, model type selector.
5. **💡 参数推荐** — Recommended parameter values as tag chips, risk notes, "提交到参数管理" button (calls `POST /analysis/recommendation/submit`).

### Backend — Unified dataset_id API

#### New Endpoints

| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| `POST` | `/analysis/dataset/query` | `{device_id, since?, until?}` | `{dataset_id, fields, sample_count}` | Builds dataset from DB, stores in memory with TTL |
| `POST` | `/analysis/dataset/upload` | FormData(file) | `{dataset_id, fields, sample_count}` | Existing Excel upload logic, renamed |
| `GET` | `/analysis/dataset/{id}/preview` | `?page=1&size=50` | `{rows, total, page, fields}` | Paginated raw data + field metadata |

#### Unified Analysis Endpoints (existing, now shared)

| Method | Path | Request | Notes |
|---|---|---|---|
| `POST` | `/analysis/profile` | `{dataset_id}` | Retrieve from memory, call `profile_dataset()` |
| `POST` | `/analysis/correlation` | `{dataset_id, field_x?, field_y?, method?}` | When field_x/y omitted, compute full matrix |
| `POST` | `/analysis/regression` | `{dataset_id, feature_fields, target_field, model_type?}` | Per-target regression |
| `POST` | `/analysis/recommendation` | `{dataset_id, feature_fields, target_field, target_value, constraints?}` | Compute recommended params |
| `POST` | `/analysis/recommendation/submit` | (existing format) | Submit to parameter management |

#### Removed / Deprecated

- `POST /analysis/excel/profile` → merged into `POST /analysis/profile`
- `POST /analysis/excel/correlation` → merged into `POST /analysis/correlation`
- `POST /analysis/excel/regression` → merged into `POST /analysis/regression`
- `POST /analysis/excel/recommendation` → merged into `POST /analysis/recommendation`
- The old online endpoints (`POST /analysis/profile` with `{feature_fields, target_fields, ...}`) are **kept for backward compatibility** but no longer used by the new frontend.

#### Dataset Storage

The existing in-memory dataset storage (`excel.py`: `_dataset_store`, 30-min TTL via `time.monotonic()`) is extended to serve both sources. `POST /analysis/dataset/query` stores its `AnalysisDataset` in the same dict. `save_dataset()` and `get_dataset()` are renamed to be source-agnostic.

#### DatasetBuilder Enhancement

`DatasetBuilder` gains a `build_to_dataset_id()` method that queries the DB and stores the result in-memory, returning a UUID `dataset_id`. This is what `POST /analysis/dataset/query` calls.

### Frontend — Component Changes

#### Files to Delete (3)
- `web/src/components/ExcelCorrelationChart.vue`
- `web/src/components/ExcelRegressionChart.vue`
- `web/src/components/ExcelRecommendationForm.vue`

#### Files to Modify (3)
- `CorrelationChart.vue` → Accept `datasetId: string` + `fields: {features, targets}`, call unified `POST /analysis/correlation`
- `RegressionChart.vue` → Accept `datasetId: string` + fields, call unified `POST /analysis/regression`
- `RecommendationForm.vue` → Accept `datasetId: string` + fields, call unified `POST /analysis/recommendation`

#### Files to Create (2)
- `web/src/components/DataPreviewTable.vue` — Paginated table with Feature/Target color coding
- `web/src/components/FieldCheckboxGrid.vue` — Card grid field selector with checkboxes

#### Files to Majorly Rewrite (1)
- `web/src/views/AnalysisView.vue` — State-machine driven, 4-step workflow

#### API Client Changes
- `web/src/api/analysis.ts` — Add `queryDataset()`, `previewDataset()`, remove `excelProfile()`, `excelCorrelation()`, `excelRegression()`, `excelRecommendation()`
- Existing `uploadExcel()` stays (renamed to `uploadDataset()`)
- `profile()`, `correlation()`, `regression()`, `recommendation()` signature changes to accept `datasetId`

### Non-Goals

- Report export to PDF/HTML (deferred — "导出" button is placeholder)
- Real-time streaming of analysis results
- Saving report snapshots for later comparison
- Modifying the SPC module (separate page at `/spc`)

## Relevant Files

```
web/src/
  views/
    AnalysisView.vue              ← Major rewrite: state-machine workflow
  components/
    AnalysisFilter.vue            ← Keep, reused in import step
    CorrelationChart.vue          ← Modify: accept datasetId
    RegressionChart.vue           ← Modify: accept datasetId
    RecommendationForm.vue        ← Modify: accept datasetId
    DataPreviewTable.vue          ← NEW: paginated raw data table
    FieldCheckboxGrid.vue         ← NEW: checkbox card field selector
    ExcelCorrelationChart.vue     ← DELETE
    ExcelRegressionChart.vue      ← DELETE
    ExcelRecommendationForm.vue   ← DELETE
  api/
    analysis.ts                   ← Modify: unified API functions

src/process_opt/
  analysis/
    dataset.py                    ← Modify: add build_to_dataset_id()
    excel.py                      ← Modify: rename functions, source-agnostic
    service.py                    ← Minor: new DatasetBuilder method
  api/
    app.py                        ← Modify: new routes, remove /excel/* routes
```

## Testing Strategy

### Backend
- `test_dataset_builder.py`: New `build_to_dataset_id()` stores and returns UUID
- `test_dataset_storage.py`: TTL expiry works for both online and Excel datasets
- `test_preview_endpoint.py`: Pagination, field metadata in response
- Existing analysis tests: Verify they still pass with `dataset_id` parameter

### Frontend
- TypeScript types for new request/response shapes
- `vue-tsc --noEmit` must pass
- Manual smoke: import online → preview → config → report; import Excel → same flow

## Data Preview Backend Details

```
GET /api/v1/analysis/dataset/{id}/preview?page=1&size=50

Response:
{
  "rows": [
    {"barcode": "P24-0001", "temperature": 218, "conveyor_speed": 47, ...},
    ...
  ],
  "total": 350,
  "page": 1,
  "size": 50,
  "fields": {
    "features": [
      {"name": "temperature", "type": "numeric", "min": 100, "max": 300},
      ...
    ],
    "targets": [
      {"name": "solder_joint_quality", "type": "pass_fail"},
      {"name": "voiding_pct", "type": "numeric", "min": 0, "max": 5}
    ]
  }
}
```

The `fields` metadata drives the checkbox grid in Step 3 — field names become card labels, type info sets the card subtitle, and pre-selection defaults to all features + all numeric targets.
