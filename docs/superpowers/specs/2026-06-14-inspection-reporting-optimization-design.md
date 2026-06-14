# 检测结果上报模块优化设计

## 概述

优化检测结果上报模块，使检测数据结构与工艺参数类同（数值型 + 规格限 + 判定），支持不同设备独立上报工艺参数与检测数据，并在分析侧通过 barcode JOIN。

## 数据模型

### process_summary 变更

```sql
ALTER TABLE process_summary ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
```

### inspection_results 变更

```sql
ALTER TABLE inspection_results ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
```

### results JSONB 格式

原有扁平 key-value 格式废弃，改为自描述数组：

```json
[
  {"name": "voltage", "value": 5.0, "unit": "V", "result": "pass", "usl": 10.0, "lsl": 0.0},
  {"name": "current", "value": 1.2, "unit": "mA", "result": "pass", "usl": 2.0, "lsl": 0.5}
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 检测项目名称 |
| value | float | 实测数值 |
| unit | string | 单位（可选） |
| result | string | pass / fail |
| usl | float | 规格上限（可选） |
| lsl | float | 规格下限（可选） |

### analysis_view 更新

```sql
SELECT p.barcode, p.device_id, p.processed_at, p.params, p.product_model AS process_product_model,
       i.station_id, i.inspected_at, i.results, i.product_model AS inspection_product_model
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
```

## 消息协议

### ProcessMessage

```python
class ProcessMessage(BaseModel):
    message_id: str
    barcode: str
    device_id: str
    processed_at: datetime
    product_model: str = ""           # 新增
    params: dict[str, Any]
```

### InspectionMessage

```python
class InspectionMessage(BaseModel):
    message_id: str
    barcode: str
    station_id: str
    inspected_at: datetime
    product_model: str = ""           # 新增
    results: list[InspectionItem]     # 结构化列表

class InspectionItem(BaseModel):
    name: str
    value: float
    unit: str = ""
    result: str = "pass"
    usl: float | None = None
    lsl: float | None = None
```

## 管道变更

### Gateway

`POST /api/v1/data/process` 和 `POST /api/v1/data/inspection` 端点接受新增字段，原样发布至 NATS。

### Consumer

`DataRepository.upsert_inspection()` 写入 inspection_results 时存储新格式 JSONB。
`DataRepository.upsert_process()` 写入 process_summary 时存储 product_model。

## Mock 数据生成器

### 模板重构

所有 13 种设备类型的 `generate_results()` 输出改为数组格式。每个设备类型 2-4 个检测指标项，value 在 lsl~usl 范围内随机生成，约 5% 超出规格模拟 fail。

示例 — testing-station 生成的 results 数组：

```python
[
    {"name": "voltage", "value": 5.0, "unit": "V", "result": "pass", "usl": 10.0, "lsl": 0.0},
    {"name": "current", "value": 1.2, "unit": "mA", "result": "pass", "usl": 2.0, "lsl": 0.5},
]
```

### 产品型号生成

`generate_inspection_data()` 和 `generate_params()` 新增 `product_model` 参数，从预定义列表 `["A", "B", "C"]` 中随机选取。

### CLI seed-db

适配新格式写入。

## 后端 API

### 数据查询

`GET /api/v1/analysis/records` 新增 `product_model` 查询参数：

```python
class RecordQuery:
    barcode: str | None = None
    device_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    product_model: str | None = None
    page: int = 1
    page_size: int = 20
```

### SPC 分析适配

P-chart 缺陷判定：遍历 results 数组，任一指标 `result == "fail"` 则该 barcode 记为缺陷。

## 数据库迁移

`db/migrations/004_product_model.sql`:

```sql
ALTER TABLE process_summary ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
ALTER TABLE inspection_results ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
DROP VIEW IF EXISTS analysis_view;
CREATE VIEW analysis_view AS
SELECT p.barcode, p.device_id, p.processed_at, p.params, p.product_model AS process_product_model,
       i.station_id, i.inspected_at, i.results, i.product_model AS inspection_product_model
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
```

## 影响范围

| 模块 | 变更 |
|------|------|
| common/schemas.py | ProcessMessage + InspectionMessage 新增字段 |
| common/repositories.py | upsert 适配新字段 |
| gateway/app.py | 透传新字段 |
| consumer/handler.py | 适配新字段 |
| mock/templates.py | results 改为数组格式 |
| mock/generator.py | 新增 product_model 参数 |
| mock/cli.py | seed-db 适配 |
| api/app.py | records 查询加 product_model 过滤 |
| analysis/spc.py | P-chart 解析新 results 格式 |
| analysis/dataset.py | analysis_view 含 product_model |
| db/migrations/ | 新增 004 迁移文件 |
