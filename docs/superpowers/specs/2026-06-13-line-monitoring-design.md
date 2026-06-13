# Line Monitoring Design

**Date:** 2026-06-13
**Status:** design

## Motivation

The current system identifies devices by free-form `device_id` strings in `process_summary` with no metadata registry, no production-line hierarchy, and no way to manage device attributes. Workshop operators need to group devices into production lines, track line-level SPC health, and maintain device metadata (type, icon, description, responsible person).

## Scope

- Production line CRUD (name, responsible person, location)
- Device registry CRUD (name, type, icon, description, line assignment)
- Line-level SPC aggregation view (device count, normal/abnormal summary, Cpk overview per device)
- Navigation restructure: line as top-level menu, device as drill-down; replace "设备监控" sidebar item with "线体监控"
- Mock generator adapted to query or auto-register devices

## Non-Goals

- Real-time topology diagram with device positions (deferred)
- Device-to-device dependency modeling
- Historical line-level trend comparison
- Modifying `process_summary` or `inspection_results` schema

## Data Model

### New Table: `production_lines`

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | |
| `name` | TEXT | NOT NULL UNIQUE | Line display name |
| `responsible` | TEXT | NOT NULL | Person responsible |
| `location` | TEXT | NULL | Physical location (e.g. "A栋2层") |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### New Table: `device_registry`

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | TEXT | PK | Matches `process_summary.device_id` |
| `line_id` | UUID | FK → production_lines.id, ON DELETE SET NULL | Nullable: unassigned devices allowed |
| `name` | TEXT | NOT NULL | Human-readable device name |
| `type` | TEXT | NOT NULL | Device type (e.g. reflow-oven, injection-molder) |
| `icon` | TEXT | NULL | Element Plus icon name for display |
| `description` | TEXT | NULL | Functional description |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### Relationships

```
production_lines 1 ──── N device_registry
device_registry   1 : 1 process_summary (loose match via device_id)
```

No FK from `process_summary` to `device_registry` — data messages may arrive before device registration.

### Migration

File: `db/migrations/002_lines_devices.sql`

Creates both tables, inserts a default line "默认产线", and backfills existing device_ids from `process_summary`:

```sql
INSERT INTO production_lines (name, responsible, location)
VALUES ('默认产线', '管理员', '未分配');

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

## Backend API

### Line Management (`/api/v1/lines`)

| Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/lines` | — | `list[LineResponse]` (includes `device_count`) | List all lines |
| `GET` | `/lines/{id}` | — | `LineDetailResponse` (line + device list) | Single line detail |
| `POST` | `/lines` | `{name, responsible, location}` | `LineResponse` (201) | Create line |
| `PUT` | `/lines/{id}` | `{name?, responsible?, location?}` | `LineResponse` | Update line |
| `DELETE` | `/lines/{id}` | — | 204 or 409 | 409 if devices still assigned |

### Line Monitoring Aggregation

| Method | Path | Response | Notes |
|---|---|---|---|
| `GET` | `/lines/{id}/monitor` | `LineMonitorResponse` | All devices in line with SPC overview per device |

`LineMonitorResponse`: `{line: LineResponse, summary: LineSummary, devices: list[DeviceSpcSummary]}`

`LineSummary`: `{device_count, normal_count, abnormal_count, marginal_count, no_spec_count, status}` where `status` is the worst status across all devices — if any device is abnormal → "abnormal", else if any marginal → "marginal", else if any no_spec → "no_spec", else "normal". Lines with no devices have status "empty".

`DeviceSpcSummary`: `{device_id, device_name, type, status, worst_cpk, param_count, outlier_total}` — computed from `compute_overview()` per device via `POST /spc?field=null`, cached for 30s server-side to avoid redundant query overload.

### Device Registry CRUD (`/api/v1/devices`)

| Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/devices` | `?line_id=` (optional) | `list[DeviceResponse]` | List with optional line filter |
| `GET` | `/devices/{id}` | — | `DeviceResponse` | Single device detail |
| `PUT` | `/devices/{id}` | `{name?, type?, icon?, description?, line_id?}` | `DeviceResponse` | Update device attributes |
| `DELETE` | `/devices/{id}` | — | 204 | Remove from registry only (data preserved) |

### SPC Enhancement

`POST /api/v1/analysis/spc` — `SpcRequest` gains optional `line_id: str | None` field. When provided, filters `process_summary` to devices belonging to that line.

### Pydantic Schemas

New schemas in a new module `process_opt.analysis.line_schemas.py`:

```python
class LineCreate(BaseModel):
    name: str
    responsible: str
    location: str | None = None

class LineUpdate(BaseModel):
    name: str | None = None
    responsible: str | None = None
    location: str | None = None

class LineResponse(BaseModel):
    id: str
    name: str
    responsible: str
    location: str | None
    device_count: int
    created_at: datetime

class LineDetailResponse(LineResponse):
    devices: list[DeviceResponse]

class DeviceResponse(BaseModel):
    id: str
    line_id: str | None
    line_name: str | None
    name: str
    type: str
    icon: str | None
    description: str | None

class DeviceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    icon: str | None = None
    description: str | None = None
    line_id: str | None = None
```

### Repository Layer

New repository class `LineDeviceRepository` in `process_opt.common.repositories`:

- `list_lines()` — JOIN with device_registry for device_count
- `get_line(id)` — line + related devices
- `create_line(data)` — INSERT
- `update_line(id, data)` — UPDATE
- `delete_line(id)` — DELETE with FK check
- `list_devices(line_id?)` — with optional JOIN to production_lines
- `get_device(id)` — single device with line_name
- `update_device(id, data)` — UPDATE device_registry
- `delete_device(id)` — DELETE from device_registry only
- `get_devices_by_line(line_id)` — for SPC filtering and monitoring

## Frontend

### Route Changes

| Path | Component | Menu Label | Change |
|---|---|---|---|
| `/lines` | `LinesView.vue` | 线体监控 | **New** — line list + management |
| `/lines/:id` | `LineDetailView.vue` | (sub-page) | **New** — line detail + device list |
| `/spc` | `SpcView.vue` | (via drill-down) | **Enhanced** — accepts `line` + `device` params |
| — | `SpcView.vue` | (removed) | **Removed** — "设备监控" menu entry removed |

`/dashboard`, `/data`, `/analysis`, `/parameters`, `/settings` unchanged.

### Sidebar Menu

```
仪表盘
线体监控                 ← replaces 设备监控
原始数据
参数调优
参数管理
设置
```

Sidebar header/sub-lines: when "线体监控" is active and sidebar is expanded, show collapsed sub-items for each line (fetched on mount, max 5 visible).

### Components

#### `LinesView.vue` (线体列表 `/lines`)
- Table: line name (link → /lines/:id), responsible, location, device count, status indicator (normal/abnormal based on worst device Cpk)
- Header button: "+ 新建线体" opens Dialog with name/responsible/location form
- Row actions: edit (dialog), delete (confirm dialog, blocked if devices assigned)
- Status: computed from `LineSummary.status` (worst status across all devices: abnormal > marginal > no_spec > normal; empty line shows "empty")

#### `LineDetailView.vue` (线体详情 `/lines/:id`)
- Header: line name, responsible, location, edit button
- Overview cards: device count, normal/abnormal ratio, worst Cpk
- Device list table: name (link → /spc?line=X&device=Y), type, icon, status, Cpk
- Row actions: edit device (dialog with name/type/icon/description/line assignment)
- "管理设备" button: opens dialog to assign/unassign devices to this line

#### `SpcView.vue` (增强 `/spc?line=X&device=Y`)
- Breadcrumb: 线体监控 > SMT-01 > 回流焊-01
- Device info bar: type, description, edit button (opens device edit dialog)
- Existing SPC chart grid unchanged
- Device selector in filter bar now scoped to line devices (when `line` param present), or show all when stand-alone

### API Client

New module `web/src/api/lines.ts`:
```typescript
export function listLines(): Promise<LineResponse[]>
export function getLine(id: string): Promise<LineDetailResponse>
export function createLine(data: CreateLineRequest): Promise<LineResponse>
export function updateLine(id: string, data: UpdateLineRequest): Promise<LineResponse>
export function deleteLine(id: string): Promise<void>
export function getLineMonitor(id: string): Promise<LineMonitorResponse>
export function listDevices(lineId?: string): Promise<DeviceResponse[]>
export function getDevice(id: string): Promise<DeviceResponse>
export function updateDevice(id: string, data: UpdateDeviceRequest): Promise<DeviceResponse>
export function deleteDevice(id: string): Promise<void>
```

## Mock Generator Adaptation

`process_opt.mock.generator.generate_pair()` currently sets `device_id = device_type`. Updated logic:

1. On first call per `device_type`, query `device_registry` for devices matching that type
2. If found, use that `device_id`
3. If not found, auto-register: `INSERT INTO device_registry` with `id = f"{device_type}-001"`, assign to default line
4. Auto-registration is idempotent (ON CONFLICT DO NOTHING)

This way mock devices appear in the registry and can be assigned to lines via the UI.

## Testing Strategy

### Unit Tests
- `test_line_repository.py`: CRUD operations, FK constraint enforcement, device counting
- `test_schemas.py`: LineCreate/Update validation, LineResponse serialization
- `test_line_monitor.py`: Aggregation logic, empty line, line with mixed-status devices

### Integration Tests
- `test_lines_api.py`: Full CRUD cycle via HTTP, 409 on delete with assigned devices
- `test_devices_api.py`: Device update, line assignment changes
- `test_spc_with_line.py`: SPC query filtered by line_id returns only line devices

### Mock Adaptation Tests
- `test_generator.py`: Auto-registration of new device types, idempotency
