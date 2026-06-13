# Line Monitoring Design

**Date:** 2026-06-13
**Status:** implemented (updated 2026-06-14)

## Motivation

The current system identifies devices by free-form `device_id` strings in `process_summary` with no metadata registry, no production-line hierarchy, and no way to manage device attributes. Workshop operators need to group devices into production lines, track line-level SPC health, and maintain device metadata (type, icon, description, responsible person).

## Scope

- Production line CRUD (name, responsible person, location)
- Device registry CRUD (name, type, icon, description, line assignment, sort_order)
- Line-level SPC aggregation view (device count, normal/abnormal summary, Cpk overview per device)
- Topology-based card layout with drag-and-drop device reordering and cross-line device reassignment
- Navigation restructure: line as top-level menu ("线体拓扑"), device as drill-down; replaced "设备监控" sidebar item
- Mock generator adapted to query or auto-register devices; supports `--db-dsn` and `--device-count` options
- Device type → icon presets with Chinese labels (13 device types)

## What Was Built (Deviations from Original Spec)

| Item | Original Design | Actual Implementation |
|---|---|---|
| LinesView | Table-based line list | Card-based topology layout with drag-and-drop |
| Device ordering | None | `sort_order` INTEGER column with `PUT /lines/{id}/reorder` |
| Line detail | Separate LineDetailView | Implemented with overview cards + device table + manage dialog |
| Sidebar sub-items | Collapsed line sub-items | Omitted (simpler UX, lines shown on main page) |
| Device icons | Manual per-device | Centralized `device-icons.ts` with type→icon+label maps |
| `ensure_device_exists` | `<device_type>-001` single device | `{type}-{index:03d}` format, matches `--device-count` seeding |
| Monitoring cache | 30s server-side cache | Direct aggregation per request (no cache, acceptable latency) |
| SpcRequest.line_id | Filter to line devices | Validates device membership in line, not used for multi-device SPC |
| Pydantic response models | Strict LineMonitorResponse etc | Raw dict returns (KISS, type-safe enough for Python API) |
| Delete line blocking | 409 if devices assigned | Same (409) |

## Data Model

### Table: `production_lines`

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | |
| `name` | TEXT | NOT NULL UNIQUE | Line display name |
| `responsible` | TEXT | NOT NULL | Person responsible |
| `location` | TEXT | NULL | Physical location (e.g. "A栋2层") |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### Table: `device_registry`

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | TEXT | PK | Matches `process_summary.device_id` |
| `line_id` | UUID | FK → production_lines.id, ON DELETE SET NULL | Nullable: unassigned devices allowed |
| `name` | TEXT | NOT NULL | Human-readable device name |
| `type` | TEXT | NOT NULL | Device type (e.g. reflow-oven, laser-cutter) |
| `icon` | TEXT | NULL | Element Plus icon name for display |
| `description` | TEXT | NULL | Functional description |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | Position within line (used by drag-drop reorder) |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### Relationships

```
production_lines 1 ──── N device_registry  (FK line_id, ON DELETE SET NULL)
device_registry   1 : 1 process_summary     (loose match via device_id, NO FK)
```

### Migrations

| File | Content |
|---|---|
| `db/migrations/001_initial.sql` | process_summary, inspection_results, analysis_view |
| `db/migrations/002_lines_devices.sql` | CREATE production_lines + device_registry, insert 默认产线, backfill existing device_ids |
| `db/migrations/003_device_sort_order.sql` | ALTER TABLE device_registry ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0 |

Applied on backend startup via `apply_sql_file()` in `main.py`.

## Backend API

### Line Management (`/api/v1/lines`)

| Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/lines` | — | `list[dict]` with `device_count` | List all lines |
| `GET` | `/lines/{id}` | — | `dict` (line + `devices` list) | Single line detail |
| `POST` | `/lines` | `{name, responsible, location?}` | `dict` (201) | Create line |
| `PUT` | `/lines/{id}` | `{name?, responsible?, location?}` | `dict` | Update line |
| `DELETE` | `/lines/{id}` | — | 204 or 409 | 409 if devices still assigned |

### Device Reordering

| Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|
| `PUT` | `/lines/{line_id}/reorder` | `{device_ids: [id1, id2, ...]}` | 204 | Sets sort_order for each device; also handles cross-line reassignment |

### Line Monitoring Aggregation

| Method | Path | Response | Notes |
|---|---|---|---|
| `GET` | `/lines/{id}/monitor` | `{line, summary, devices}` | All devices in line with SPC overview per device |

`summary`: `{device_count, normal_count, abnormal_count, marginal_count, no_spec_count, status}` where `status` is the worst status across all devices (abnormal > marginal > no_spec > normal > empty).

### Device Registry CRUD (`/api/v1/devices`)

| Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/devices?line_id=` | — | `list[dict]` | List with optional line filter |
| `GET` | `/devices/{id}` | — | `dict` | Single device detail |
| `PUT` | `/devices/{id}` | `{name?, type?, icon?, description?, line_id?}` | `dict` | Update device (move between lines) |
| `DELETE` | `/devices/{id}` | — | 204 | Remove from registry only (data preserved) |

### SPC Enhancement

`POST /api/v1/analysis/spc` — `SpcRequest` has optional `line_id: str | None` field. When provided, validates that `device_id` belongs to the specified line. `AnalysisService.spc()` passes `device_id` and `since` filters to `DatasetBuilder.build()`.

### Repository Layer

`LineDeviceRepository` in `process_opt.common.repositories`:

| Method | Purpose |
|---|---|
| `list_lines()` | JOIN device_registry for device_count |
| `get_line(id)` | Line with device count |
| `create_line(name, responsible, location)` | INSERT |
| `update_line(id, name?, responsible?, location?)` | Dynamic SET clause |
| `delete_line(id)` | Returns False if devices assigned |
| `list_devices(line_id?)` | With JOIN to production_lines for line_name |
| `get_device(id)` | Single device with line_name |
| `update_device(id, name?, type?, icon?, description?, line_id?)` | Dynamic SET clause |
| `delete_device(id)` | DELETE from device_registry only |
| `get_devices_by_line(line_id)` | Returns device IDs list for SPC filtering |
| `ensure_device_exists(device_id, device_type)` | Idempotent INSERT (ON CONFLICT DO NOTHING) |
| `reorder_devices(line_id, device_ids)` | UPDATE sort_order in transaction loop |

## Frontend

### Route Changes

| Path | Component | Menu Label |
|---|---|---|
| `/dashboard` | DashboardView.vue | 仪表盘 |
| `/lines` | LinesView.vue | 线体拓扑 |
| `/lines/:id` | LineDetailView.vue | (sub-page) |
| `/data` | DataView.vue | 原始数据 |
| `/analysis` | AnalysisView.vue | 参数调优 |
| `/parameters` | ParametersView.vue | 参数管理 |
| `/spc` | SpcView.vue | (via drill-down) |
| `/settings` | SettingsView.vue | 设置 |
| `/guide` | GuideView.vue | (无菜单入口) |

### Components

#### `LinesView.vue` (线体拓扑 `/lines`)

Card-based topology layout, not a table:

- Each production line renders as a card section with header (name, responsible, location, status badge)
- Devices displayed as small icon-labeled cards within the line section
- HTML5 drag-and-drop: devices can be reordered within a line (auto-saves via `PUT /lines/{id}/reorder`)
- Devices can be dragged to another line's section to reassign
- "+ 新建线体" button opens create dialog
- Edit/delete actions on each line
- Dynamic device type icons via `<component :is="deviceIcon(type)" />`

#### `LineDetailView.vue` (线体详情 `/lines/:id`)

- Header: line name, responsible, location, edit button
- Overview cards: device count, normal/abnormal ratio
- Device list table with edit/manage dialogs
- Back link to `/lines`

#### `SpcView.vue` (增强 `/spc?line=X&device=Y`)

- Breadcrumb: 线体拓扑 > line_name > device_name
- Device info bar: type (Chinese label from `device-icons.ts`), description, edit button (opens device edit dialog)
- All 6 SPC charts + parameter overview + USL/LSL spec inputs unchanged
- Filter bar scoped to line devices when `line` query param present

### API Client

`web/src/api/lines.ts` exports:

```typescript
listLines(): Promise<LineResponse[]>
getLine(id: string): Promise<LineDetailResponse>
createLine(data: CreateLineRequest): Promise<LineResponse>
updateLine(id: string, data: UpdateLineRequest): Promise<LineResponse>
deleteLine(id: string): Promise<void>
getLineMonitor(id: string): Promise<LineMonitorResponse>
listDevices(lineId?: string): Promise<DeviceResponse[]>
getDevice(id: string): Promise<DeviceResponse>
updateDevice(id: string, data: UpdateDeviceRequest): Promise<DeviceResponse>
deleteDevice(id: string): Promise<void>
```

### Device Type Icons

`web/src/utils/device-icons.ts` — centralized mapping:

| Device Type | Icon Component | Chinese Label |
|---|---|---|
| `reflow-oven` | Platform | 回流焊 |
| `injection-molder` | Setting | 注塑机 |
| `pick-and-place` | VideoCamera | 贴片机 |
| `wave-solder` | Sunny | 波峰焊 |
| `cnc-drill` | Aim | CNC钻孔 |
| `3d-printer` | Printer | 3D打印机 |
| `testing-station` | Monitor | 测试站 |
| `laser-cutter` | MagicStick | 激光切割 |
| `coating-machine` | Brush | 涂覆机 |
| `xray-inspection` | Search | X光检测 |
| `oven-curing` | Histogram | 固化炉 |
| `wire-bonder` | Link | 引线键合 |
| `ultrasonic-cleaner` | Refresh | 超声清洗 |
| _(fallback)_ | Cpu | (raw type string) |

## Mock Data

### Production Baseline

| Metric | Value |
|---|---|
| Device types | 13 |
| Production lines | 20 |
| Registered devices | 391 |
| Process records | 13,014 |
| Consumer batch size | 500 |

### Mock Generator

`process_opt.mock.generator` adapted with:
- `--db-dsn` option: connect to PostgreSQL for device registry queries
- `--device-count N`: register N devices per type in `device_registry`
- `--count N`: seed N records per call
- Device ID format: `{type}-{index:03d}` (e.g. `reflow-oven-001`)
- 7→13 device templates with type-specific param distributions and fail conditions

## Relevant Files

```
db/migrations/
  001_initial.sql                     process_summary, inspection_results base tables
  002_lines_devices.sql               production_lines + device_registry DDL
  003_device_sort_order.sql           ALTER TABLE add sort_order column
src/process_opt/
  analysis/
    line_schemas.py                   LineCreate/Update/Response, DeviceResponse/Update, etc. (Pydantic)
    dataset.py                        build() gained device_id/since filtering
    service.py                        spc() passes filters, checks AnalysisError
  common/
    repositories.py                   LineDeviceRepository (~200 lines appended)
  api/
    app.py                            Line/device CRUD routes, reorder, monitor, SpcRequest.line_id
    main.py                           Migration runner + LineDeviceRepository wiring
  mock/
    templates.py                      13 device templates with type-specific params & results
    generator.py                      Type-specific fail conditions, 13 types
web/src/
  api/lines.ts                        Frontend API client (TypeScript)
  utils/device-icons.ts               Type → Icon + Label maps
  views/
    LinesView.vue                     Topology card layout with drag-and-drop
    LineDetailView.vue                Line detail + device management
    SpcView.vue                       Enhanced with breadcrumb, device info bar, editing
  router/index.ts                     Added /lines + /lines/:id routes
  components/AppLayout.vue            Sidebar changed to "线体拓扑" /lines
tests/
  analysis/
    test_line_schemas.py              7 tests: LineCreate/Update/Response, DeviceUpdate, MonitorResponse
    test_line_repository.py           12 tests: CRUD, reorder, idempotent ensure, FK enforcement
  api/
    test_lines_api.py                 7 tests: HTTP integration for lines/devices APIs
docs/superpowers/
  specs/2026-06-13-line-monitoring-design.md   This document
  plans/2026-06-13-line-monitoring-plan.md     18-task implementation plan
```

## Verification

- Backend tests: **193 passed** (174 original + 19 new line/device tests)
- Frontend type-check: `vue-tsc --noEmit` passes clean
- Docker deployment: `docker compose up -d --build backend-api` succeeds
- API smoke: `GET /api/v1/lines` returns 20 lines; `GET /api/v1/devices` returns 391 devices
- Monitoring: `GET /api/v1/lines/{id}/monitor` returns aggregated SPC per device
- Reordering: `PUT /api/v1/lines/{id}/reorder` persists via sort_order column
