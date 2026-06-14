# 检测结果上报模块优化 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强检测数据结构为自描述数组格式（name/value/result/usl/lsl），新增 product_model 字段到 process_summary 和 inspection_results，适配数据管道、分析模块和 mock 生成器。

**Architecture:** DB migration → Message schemas → Repository → DatasetBuilder/SPC → Mock → API → 全量测试。DatasetBuilder 需解析新的 results 数组格式并展平为分析模块可用的 feats/targets。

**Tech Stack:** PostgreSQL 15 + asyncpg, Pydantic v2, NATS JetStream, FastAPI, scikit-learn

---

### Task 1: DB 迁移（004_product_model.sql）

**Files:**
- Create: `db/migrations/004_product_model.sql`
- Modify: `src/process_opt/common/db.py`（无需改动，已自动扫描 migrations 目录）

- [ ] **Step 1: 创建迁移文件**

```sql
ALTER TABLE process_summary ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
ALTER TABLE inspection_results ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
DROP VIEW IF EXISTS analysis_view;
CREATE VIEW analysis_view AS
SELECT
  p.barcode,
  p.device_id,
  p.processed_at,
  p.params,
  p.product_model AS process_product_model,
  i.station_id,
  i.inspected_at,
  i.results,
  i.product_model AS inspection_product_model
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
```

- [ ] **Step 2: 写迁移测试**

在 `tests/test_entrypoints.py` 或 `tests/integration/` 中增加验证。在现有测试框架中，迁移通过 `src/process_opt/api/main.py` 的 lifespan 自动应用。

去 `tests/api/test_app.py` 增加一个简单验证：

```python
# 在 test_app.py 末尾添加
async def test_analysis_view_has_product_model(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/analysis/records?page_size=1")
    assert resp.status_code == 200
    data = resp.json()
    if data["items"]:
        item = data["items"][0]
        # analysis_view 中的字段（数据库有值时才有）
        assert "process_product_model" in item or "inspection_product_model" in item
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/api/test_app.py::test_analysis_view_has_product_model -v --asyncio-mode=auto 2>&1 | tail -15
```

预期：PASS（前提是 PostgreSQL 运行且有数据）

- [ ] **Step 4: Commit**

```bash
git add db/migrations/004_product_model.sql tests/api/test_app.py
git commit -m "feat: add product_model columns and update analysis_view"
```

---

### Task 2: 消息协议更新

**Files:**
- Modify: `src/process_opt/common/schemas.py`

- [ ] **Step 1: 更新 schemas.py**

```python
class InspectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    value: float
    unit: str = ""
    result: str = Field(default="pass", pattern="^(pass|fail)$")
    usl: float | None = None
    lsl: float | None = None


class ProcessMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    processed_at: datetime
    product_model: str = ""
    params: dict[str, Any]

    @field_validator("params")
    @classmethod
    def params_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("params must not be empty")
        return value


class InspectionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    station_id: str = Field(min_length=1)
    inspected_at: datetime
    product_model: str = ""
    results: list[InspectionItem]

    @field_validator("results")
    @classmethod
    def results_not_empty(cls, value: list[InspectionItem]) -> list[InspectionItem]:
        if not value:
            raise ValueError("results must not be empty")
        return value
```

- [ ] **Step 2: 写测试 `tests/common/test_schemas.py`**

```python
def test_inspection_item_valid():
    item = InspectionItem(name="voltage", value=5.0, result="pass", usl=10.0, lsl=0.0)
    assert item.name == "voltage"
    assert item.value == 5.0
    assert item.usl == 10.0

def test_inspection_item_invalid_result():
    with pytest.raises(ValidationError):
        InspectionItem(name="v", value=1.0, result="unknown")

def test_inspection_message_with_items():
    msg = InspectionMessage(
        message_id="m1", barcode="B001", station_id="S1",
        inspected_at=datetime(2026, 1, 1, 12, 0, 0),
        product_model="A",
        results=[
            InspectionItem(name="voltage", value=5.0, result="pass"),
        ],
    )
    assert msg.product_model == "A"
    assert len(msg.results) == 1

def test_process_message_with_product_model():
    msg = ProcessMessage(
        message_id="m1", barcode="B001", device_id="D1",
        processed_at=datetime(2026, 1, 1, 12, 0, 0),
        product_model="A",
        params={"temp": 220},
    )
    assert msg.product_model == "A"

def test_inspection_message_results_empty():
    with pytest.raises(ValidationError):
        InspectionMessage(
            message_id="m1", barcode="B001", station_id="S1",
            inspected_at=datetime(2026, 1, 1, 12, 0, 0),
            results=[],
        )

def test_inspection_message_to_json():
    msg = InspectionMessage(
        message_id="m1", barcode="B001", station_id="S1",
        inspected_at=datetime(2026, 1, 1, 12, 0, 0),
        results=[InspectionItem(name="v", value=5.0, result="pass")],
    )
    data = msg.model_dump(mode="json")
    assert isinstance(data["results"], list)
    assert data["results"][0]["name"] == "v"
    assert data["results"][0]["value"] == 5.0
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/common/test_schemas.py -v 2>&1 | tail -20
```

预期：所有 test_schemas 测试 PASS

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/common/schemas.py tests/common/test_schemas.py
git commit -m "feat: add InspectionItem model, product_model to ProcessMessage/InspectionMessage"
```

---

### Task 3: Gateway + Consumer + Repository 管道适配

**Files:**
- Modify: `src/process_opt/gateway/app.py`（无需改动代码，schema 变更自动生效）
- Modify: `src/process_opt/common/repositories.py`
- Modify: `src/process_opt/consumer/handler.py`（无需改动，泛型 handler 自动适配）

- [ ] **Step 1: 更新 DataRepository**

将 upsert_process 和 upsert_injection 加入 product_model 字段：

```python
async def upsert_process(self, message: ProcessMessage) -> None:
    async with self._pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO process_summary (barcode, device_id, processed_at, params, product_model)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (barcode) DO UPDATE SET
              device_id = EXCLUDED.device_id,
              processed_at = EXCLUDED.processed_at,
              params = EXCLUDED.params,
              product_model = EXCLUDED.product_model,
              updated_at = now()
            """,
            message.barcode,
            message.device_id,
            message.processed_at,
            message.params,
            message.product_model,
        )

async def upsert_inspection(self, message: InspectionMessage) -> None:
    async with self._pool.acquire() as connection:
        # 将 InspectionItem 列表转换为可 JSON 序列化的列表
        results_json = [item.model_dump() for item in message.results]
        await connection.execute(
            """
            INSERT INTO inspection_results (barcode, station_id, inspected_at, results, product_model)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (barcode) DO UPDATE SET
              station_id = EXCLUDED.station_id,
              inspected_at = EXCLUDED.inspected_at,
              results = EXCLUDED.results,
              product_model = EXCLUDED.product_model,
              updated_at = now()
            """,
            message.barcode,
            message.station_id,
            message.inspected_at,
            results_json,
            message.product_model,
        )
```

- [ ] **Step 2: 更新 Repository 协议（api/app.py）**

```python
class AnalysisRepository(Protocol):
    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None: ...
    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        product_model: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]: ...
    async def list_devices(self) -> list[str]: ...
    async def get_stats(self) -> dict[str, Any]: ...
```

- [ ] **Step 3: 更新 RepositoryProxy（api/main.py）**

```python
async def query_records(
    self,
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    product_model: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    if self.repository is None:
        raise RuntimeError("Repository is not initialized")
    return await self.repository.query_records(barcode, device_id, start_time, end_time, product_model, page, page_size)
```

- [ ] **Step 4: 更新 DataRepository.query_records 支持 product_model 过滤**

```python
async def query_records(
    self,
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    product_model: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    conditions: list[str] = []
    params: list[Any] = []

    if barcode is not None:
        conditions.append(f"barcode = ${len(params) + 1}")
        params.append(barcode)
    if device_id is not None:
        conditions.append(f"device_id = ${len(params) + 1}")
        params.append(device_id)
    if start_time is not None:
        conditions.append(f"processed_at >= ${len(params) + 1}")
        params.append(start_time)
    if end_time is not None:
        conditions.append(f"processed_at <= ${len(params) + 1}")
        params.append(end_time)
    if product_model is not None:
        conditions.append("(process_product_model = ${} OR inspection_product_model = ${})".format(len(params) + 1, len(params) + 2))
        params.append(product_model)
        params.append(product_model)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    offset = (page - 1) * page_size

    async with self._pool.acquire() as connection:
        rows = await connection.fetch(
            f"""
            SELECT barcode, device_id, processed_at, params,
                   station_id, inspected_at, results,
                   process_product_model, inspection_product_model,
                   COUNT(*) OVER() AS total_count
            FROM analysis_view
            WHERE {where_clause}
            ORDER BY processed_at DESC
            OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}
            """,
            *params,
            offset,
            page_size,
        )
    ...
    items = [
        {
            "barcode": r["barcode"],
            "device_id": r["device_id"],
            "processed_at": r["processed_at"],
            "params": r["params"],
            "station_id": r["station_id"],
            "inspected_at": r["inspected_at"],
            "results": r["results"],
            "process_product_model": r["process_product_model"],
            "inspection_product_model": r["inspection_product_model"],
        }
        for r in rows
    ]
```

- [ ] **Step 5: 更新 get_analysis_record 返回 product_model 字段**

```python
async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None:
    async with self._pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT barcode, device_id, processed_at, params,
                   station_id, inspected_at, results,
                   process_product_model, inspection_product_model
            FROM analysis_view
            WHERE barcode = $1
            """,
            barcode,
        )
    if row is None:
        return None
    return dict(row)
```

- [ ] **Step 6: 更新测试 `tests/common/test_repositories.py`**

```python
async def test_upsert_process_with_product_model(pool) -> None:
    repo = DataRepository(pool)
    msg = ProcessMessage(
        message_id="pm1", barcode="PM-TEST-001", device_id="D1",
        processed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        product_model="A",
        params={"temp": 220},
    )
    await repo.upsert_process(msg)
    row = await repo.get_analysis_record("PM-TEST-001")
    assert row is not None
    assert row.get("process_product_model") == "A"

async def test_upsert_inspection_with_items(pool) -> None:
    repo = DataRepository(pool)
    msg = InspectionMessage(
        message_id="im1", barcode="IM-TEST-001", station_id="S1",
        inspected_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        product_model="A",
        results=[InspectionItem(name="voltage", value=5.0, result="pass", usl=10.0, lsl=0.0)],
    )
    await repo.upsert_inspection(msg)
    row = await repo.get_analysis_record("IM-TEST-001")
    assert row is not None
    assert row.get("inspection_product_model") == "A"
    assert isinstance(row["results"], list)
    assert row["results"][0]["name"] == "voltage"
```

注意：测试用 `pool` fixture 需要从 `tests/common/conftest.py` 获取（如有），或在本测试模块中使用 `@pytest_asyncio.fixture` 创建临时 pool。

- [ ] **Step 7: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/common/test_repositories.py -v --asyncio-mode=auto 2>&1 | tail -20
```

- [ ] **Step 8: 更新 API 路由 `src/process_opt/api/app.py`**

```python
@app.get("/api/v1/analysis/records")
async def query_records_route(
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    product_model: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Any:
    return await repository.query_records(
        barcode, device_id, start_time, end_time, product_model, page, page_size
    )
```

- [ ] **Step 9: Commit**

```bash
git add src/process_opt/common/repositories.py src/process_opt/api/app.py src/process_opt/api/main.py tests/common/test_repositories.py
git commit -m "feat: update repository and API for product_model + new inspection results format"
```

---

### Task 4: DatasetBuilder 适配新 results 数组格式

**Files:**
- Modify: `src/process_opt/analysis/dataset.py`

这是最核心的改动。DatasetBuilder 目前用 `row["results"].keys()` 获取字段列表，用 `t in row["results"]` 查找字段，新 array 格式需要改。

- [ ] **Step 1: 重写结果字段发现逻辑**

```python
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

    if not rows:
        return AnalysisError(
            code="INSUFFICIENT_SAMPLES",
            message="No samples found in database",
            suggestion="Ensure data has been ingested before analysis",
        )

    all_param_keys: set[str] = set()
    all_result_keys: set[str] = set()
    for row in rows:
        if row["params"] is not None:
            all_param_keys.update(row["params"].keys())
        if row["results"] is not None:
            # results 可能是 dict (旧格式) 或 list (新格式)
            if isinstance(row["results"], list):
                for item in row["results"]:
                    if isinstance(item, dict) and "name" in item:
                        all_result_keys.add(item["name"])
                        # 也暴露 _result 后缀字段用于 P-chart
                        all_result_keys.add(f"{item['name']}_result")
            elif isinstance(row["results"], dict):
                all_result_keys.update(row["results"].keys())
```

- [ ] **Step 2: 重写字段查找逻辑**

```python
for row in rows:
    feat = {}
    if row["params"] is not None:
        for f in use_feature_fields:
            if f in row["params"]:
                feat[f] = row["params"][f]
    features.append(feat)

    tgt = {}
    if row["results"] is not None:
        # 处理新数组格式
        if isinstance(row["results"], list):
            for item in row["results"]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if name in use_target_fields:
                    tgt[name] = item.get("value")
                result_key = f"{name}_result"
                if result_key in use_target_fields:
                    tgt[result_key] = item.get("result")
        # 处理旧 dict 格式（向后兼容）
        elif isinstance(row["results"], dict):
            for t in use_target_fields:
                t_raw = t.replace("_result", "")
                if t_raw in row["results"]:
                    if t.endswith("_result"):
                        tgt[t] = row["results"][t_raw] if isinstance(row["results"][t_raw], str) else "pass"
                    else:
                        tgt[t] = row["results"][t_raw]
    targets.append(tgt)
    ...
```

注意：对于完整的重写，实际上还需要更新 metadata。在 metadata 中也包含 product_model 信息：

```python
metadata.append({
    "barcode": row["barcode"],
    "device_id": row["device_id"],
    "station_id": row["station_id"],
    "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
    "inspected_at": row["inspected_at"].isoformat() if row["inspected_at"] else None,
    "process_product_model": row.get("process_product_model") or "",
    "inspection_product_model": row.get("inspection_product_model") or "",
})
```

- [ ] **Step 3: 运行 dataset 测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/analysis/test_dataset.py -v --asyncio-mode=auto 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/analysis/dataset.py
git commit -m "feat: adapt DatasetBuilder for new results array format"
```

---

### Task 5: SPC P-chart 和后端分析适配

**Files:**
- Modify: `src/process_opt/analysis/spc.py`

- [ ] **Step 1: 适配 `build_spc_result` 的 feature 提取 + P-chart 部分**

因新格式将检测指标值放在 targets 而非 features 中，`feature_values` 需要同时检查 features 和 targets：

```python
def build_spc_result(
    overview_dataset: AnalysisDataset,
    field_dataset: AnalysisDataset,
    field: str | None,
    usl: float | None,
    lsl: float | None,
    target: float | None,
) -> SpcResult:
    spec = None
    if usl is not None and lsl is not None and field is not None:
        spec = {field: {"usl": usl, "lsl": lsl, "target": target}}
    overview = compute_overview(overview_dataset, spec=spec)

    if field is None:
        return SpcResult(overview=overview)

    feature_values: list[float] = []
    result_values: list[str] = []
    labels: list[str] = []
    for i in range(field_dataset.sample_count):
        feat = field_dataset.features[i]
        tgt = field_dataset.targets[i]
        val = feat.get(field)
        # 检测指标值可能在 targets 中（新格式）
        if not isinstance(val, (int, float)):
            val = tgt.get(field)
        if isinstance(val, (int, float)):
            feature_values.append(float(val))
            labels.append(field_dataset.metadata[i].get("barcode", str(i)) if field_dataset.metadata else str(i))
        for k, v in tgt.items():
            if isinstance(v, str):
                result_values.append(v)
    ...
```

同时更新 `compute_overview` 收集 targets 中的数值字段（跳过 `_result` 结尾的字符串字段）：

```python
def compute_overview(dataset: AnalysisDataset, spec: dict[str, dict[str, float]] | None = None) -> list[ParamOverview]:
    field_values: dict[str, list[float]] = {}
    for feat in dataset.features:
        for key, val in feat.items():
            if isinstance(val, (int, float)):
                field_values.setdefault(key, []).append(float(val))
    for tgt in dataset.targets:
        for key, val in tgt.items():
            if isinstance(val, (int, float)):
                field_values.setdefault(key, []).append(float(val))
    ...
```

- [ ] **Step 2: 运行 SPC 测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/analysis/test_spc.py -v 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/spc.py
git commit -m "fix: update SPC compute_overview to handle numeric fields in targets"
```

---

### Task 6: Mock 检测结果模板重构

**Files:**
- Modify: `src/process_opt/mock/templates.py`

- [ ] **Step 1: 将每个 device type 的 results 改为数组格式**

每个指标包含：name, value, unit, result, usl, lsl。

```python
DEVICE_TEMPLATES: dict[str, dict[str, Any]] = {
    "reflow-oven": {
        "params": {
            "temperature": {"min": 100, "max": 300, "mu": 220, "sigma": 20, "precision": 1},
            "conveyor_speed": {"min": 10, "max": 100, "mu": 50, "sigma": 10, "precision": 1},
            "oxygen_ppm": {"min": 0, "max": 1000, "mu": 200, "sigma": 50, "precision": 0},
        },
        "results": [
            {"name": "solder_joint_quality", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "voiding_pct", "value": 0.0, "unit": "%", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "injection-molder": {
        "params": {
            "melt_temp": {"min": 150, "max": 350, "mu": 260, "sigma": 15, "precision": 1},
            "injection_pressure": {"min": 50, "max": 200, "mu": 120, "sigma": 20, "precision": 1},
            "cooling_time": {"min": 5, "max": 60, "mu": 25, "sigma": 8, "precision": 1},
        },
        "results": [
            {"name": "dimensional_accuracy", "value": 0.0, "unit": "mm", "result": "pass", "usl": 0.5, "lsl": -0.5},
            {"name": "flash_present", "value": 0.0, "unit": "", "result": "pass", "usl": 1.0, "lsl": 0.0},
        ],
    },
    "pick-and-place": {
        "params": {...},  # 不变
        "results": [
            {"name": "placement_quality", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "misalignment_count", "value": 0.0, "unit": "count", "result": "pass", "usl": 20.0, "lsl": 0.0},
        ],
    },
    "wave-solder": {
        ...
        "results": [
            {"name": "solder_bridge_rate", "value": 0.0, "unit": "%", "result": "pass", "usl": 3.0, "lsl": 0.0},
            {"name": "through_hole_fill", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
        ],
    },
    "cnc-drill": {
        ...
        "results": [
            {"name": "hole_accuracy", "value": 0.0, "unit": "mm", "result": "pass", "usl": 0.1, "lsl": -0.1},
            {"name": "surface_roughness_ra", "value": 0.0, "unit": "um", "result": "pass", "usl": 6.0, "lsl": 0.5},
        ],
    },
    "3d-printer": {
        ...
        "results": [
            {"name": "print_quality", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "warping_mm", "value": 0.0, "unit": "mm", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "testing-station": {
        ...
        "results": [
            {"name": "functional_test", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "leakage_current_na", "value": 0.0, "unit": "nA", "result": "pass", "usl": 100.0, "lsl": 0.0},
        ],
    },
    "laser-cutter": {
        ...
        "results": [
            {"name": "cut_quality", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "kerf_width_um", "value": 0.0, "unit": "um", "result": "pass", "usl": 300.0, "lsl": 50.0},
        ],
    },
    "coating-machine": {
        ...
        "results": [
            {"name": "coating_uniformity", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "bubble_count", "value": 0.0, "unit": "count", "result": "pass", "usl": 10.0, "lsl": 0.0},
        ],
    },
    "xray-inspection": {
        ...
        "results": [
            {"name": "defect_detected", "value": 0.0, "unit": "", "result": "pass", "usl": 1.0, "lsl": 0.0},
            {"name": "false_positive_rate", "value": 0.0, "unit": "%", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "oven-curing": {
        ...
        "results": [
            {"name": "cure_complete", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "weight_loss_pct", "value": 0.0, "unit": "%", "result": "pass", "usl": 3.0, "lsl": 0.0},
        ],
    },
    "wire-bonder": {
        ...
        "results": [
            {"name": "bond_strength", "value": 0.0, "unit": "g", "result": "pass", "usl": 5.0, "lsl": 3.0},
            {"name": "lift_off_count", "value": 0.0, "unit": "count", "result": "pass", "usl": 5.0, "lsl": 0.0},
        ],
    },
    "ultrasonic-cleaner": {
        ...
        "results": [
            {"name": "cleanliness_pass", "value": 1.0, "unit": "", "result": "pass", "usl": 1.5, "lsl": 0.5},
            {"name": "particle_residue", "value": 0.0, "unit": "count", "result": "pass", "usl": 50.0, "lsl": 0.0},
        ],
    },
}
```

- [ ] **Step 2: 更新测试 `tests/mock/test_templates.py`**

```python
def test_all_templates_have_array_results():
    for dtype, tmpl in DEVICE_TEMPLATES.items():
        assert isinstance(tmpl["results"], list), f"{dtype}: results should be a list"
        for item in tmpl["results"]:
            assert "name" in item, f"{dtype}: missing name"
            assert "value" in item, f"{dtype}: missing value"
            assert "result" in item, f"{dtype}: missing result"
            assert "usl" in item, f"{dtype}: missing usl"
            assert "lsl" in item, f"{dtype}: missing lsl"

def test_template_result_values_within_limits():
    for dtype, tmpl in DEVICE_TEMPLATES.items():
        for item in tmpl["results"]:
            if item["lsl"] is not None and item["usl"] is not None:
                assert item["lsl"] <= item["value"] <= item["usl"], \
                    f"{dtype}.{item['name']}: value {item['value']} must be within [{item['lsl']}, {item['usl']}]"
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/mock/test_templates.py -v 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/mock/templates.py tests/mock/test_templates.py
git commit -m "feat: rebuild mock templates results as array format"
```

---

### Task 7: Mock Generator 适配

**Files:**
- Modify: `src/process_opt/mock/generator.py`

- [ ] **Step 1: 重写 `generate_results`**

新函数在数组中的指标值在 lsl~usl 范围内随机生成，约 5% 超出规格触发 fail。

```python
def generate_results(device_type: str, params: dict[str, float | int]) -> list[dict[str, Any]]:
    template = DEVICE_TEMPLATES[device_type]
    results: list[dict[str, Any]] = []
    for item_def in template["results"]:
        name = item_def["name"]
        usl = item_def["usl"]
        lsl = item_def["lsl"]
        # 约 5% 概率超出规格
        if random.random() < 0.05:
            val = random.uniform(usl, usl * 1.2) if random.random() < 0.5 else random.uniform(lsl * 0.8, lsl)
        else:
            val = random.uniform(lsl, usl)
        val = round(val, 2)
        result = "fail" if val > usl or val < lsl else "pass"
        results.append({
            "name": name,
            "value": val,
            "unit": item_def.get("unit", ""),
            "result": result,
            "usl": usl,
            "lsl": lsl,
        })
    return results
```

- [ ] **Step 2: 更新 `generate_pair`**

```python
PRODUCT_MODELS = ["A", "B", "C"]

def generate_pair(device_type: str, barcode: str, device_index: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    message_id = str(uuid4())
    params = generate_params(device_type)
    results = generate_results(device_type, params)
    now = datetime.now(UTC)
    product_model = random.choice(PRODUCT_MODELS)

    process_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "device_id": f"{device_type}-{device_index:03d}",
        "processed_at": now.isoformat(),
        "product_model": product_model,
        "params": params,
    }

    inspection_payload = {
        "message_id": message_id,
        "barcode": barcode,
        "station_id": f"{device_type}-qa",
        "inspected_at": now.isoformat(),
        "product_model": product_model,
        "results": results,
    }

    return process_payload, inspection_payload
```

- [ ] **Step 3: 更新测试 `tests/mock/test_generator.py`**

```python
def test_generate_results_returns_list():
    results = generate_results("reflow-oven", {"temperature": 220})
    assert isinstance(results, list)
    assert len(results) > 0
    item = results[0]
    assert "name" in item
    assert "value" in item
    assert "result" in item
    assert "usl" in item
    assert "lsl" in item

def test_generate_pair_has_product_model():
    proc, insp = generate_pair("testing-station", "BC-001")
    assert "product_model" in proc
    assert "product_model" in insp
    assert proc["product_model"] in ("A", "B", "C")

def test_generate_pair_results_is_list():
    _, insp = generate_pair("testing-station", "BC-001")
    assert isinstance(insp["results"], list)
    assert len(insp["results"]) > 0
    assert "name" in insp["results"][0]
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/mock/test_generator.py -v 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/mock/generator.py tests/mock/test_generator.py
git commit -m "feat: update mock generator for new results array format + product_model"
```

---

### Task 8: Mock CLI `seed-db` 适配

**Files:**
- Modify: `src/process_opt/mock/cli.py`

- [ ] **Step 1: 更新 `_insert_records`**

生成 inspect_rows 时使用新格式（`generate_pair` 已返回新格式，只需确认序列化方式正确）：

```python
async def _insert_records(pool: asyncpg.Pool, device_ids: list[str], count: int) -> int:
    import json
    BATCH = 1000
    total = 0
    base_time = datetime.now(UTC) - timedelta(days=30)
    while total < count:
        batch_end = min(total + BATCH, count)
        batch_size = batch_end - total
        process_rows: list[tuple] = []
        inspect_rows: list[tuple] = []
        for i in range(batch_size):
            dev_id = random.choice(device_ids)
            barcode = f"DB-{datetime.now(UTC).strftime('%y%m%d')}-{total + i + 1:06d}"
            ts = base_time + timedelta(minutes=total + i)
            proc_payload, insp_payload = generate_pair(
                dev_id.rsplit("-", 1)[0], barcode, int(dev_id.rsplit("-", 1)[-1]),
            )
            process_rows.append((
                barcode, dev_id, ts,
                json.dumps(proc_payload["params"]),
                proc_payload["product_model"],
            ))
            inspect_rows.append((
                barcode, "station-" + dev_id.rsplit("-", 1)[0], ts,
                json.dumps(insp_payload["results"]),
                insp_payload["product_model"],
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO process_summary (barcode, device_id, processed_at, params, product_model)
                   VALUES ($1,$2,$3,$4::jsonb,$5) ON CONFLICT (barcode) DO NOTHING""",
                process_rows,
            )
            await conn.executemany(
                """INSERT INTO inspection_results (barcode, station_id, inspected_at, results, product_model)
                   VALUES ($1,$2,$3,$4::jsonb,$5) ON CONFLICT (barcode) DO NOTHING""",
                inspect_rows,
            )
        total += batch_size
        click.echo(f"  {total}/{count}")
    return total
```

- [ ] **Step 2: 运行 CLI 测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/mock/test_cli.py -v --asyncio-mode=auto 2>&1 | tail -15
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/mock/cli.py
git commit -m "feat: update seed-db CLI for product_model + new results format"
```

---

### Task 9: 前端 DataView 适配

**Files:**
- Modify: `web/src/views/DataView.vue`

DataView 目前将 inspection results 展示为普通对象 key-value，新数组格式需要适配展示。

- [ ] **Step 1: 找到 DataView 中展示 results 的部分**

搜索 DataView.vue 中引用 `results` 的模板代码，将 `results` 的渲染方式从 `Object.entries()` 改为遍历数组。

- [ ] **Step 2: 更新渲染逻辑**

```typescript
// 原：Object.entries(row.results).map(...)
// 新：
function formatResults(results: any) {
  if (!results) return [];
  if (Array.isArray(results)) {
    return results.map((item: any) => ({
      name: item.name,
      value: item.value,
      unit: item.unit || '',
      result: item.result,
      usl: item.usl,
      lsl: item.lsl,
    }));
  }
  // 旧格式兼容
  return Object.entries(results).map(([key, val]) => ({
    name: key,
    value: val,
    result: typeof val === 'string' ? val : 'pass',
  }));
}
```

在模板中遍历并展示每个指标的名称、值、单位、规格限和 pass/fail 标签。

- [ ] **Step 3: 验证构建**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1
```

预期：无类型错误

- [ ] **Step 4: Commit**

```bash
git add web/src/views/DataView.vue
git commit -m "feat: adapt DataView for new inspection results array format"
```

---

### Task 10: 全量测试验证

**Files:** 无新增文件

- [ ] **Step 1: 运行所有后端测试**

```bash
cd /Users/zhongding/dev/thingsboard && python -m pytest tests/ -v --asyncio-mode=auto 2>&1 | tail -40
```

预期：所有测试 PASS（至少不新增失败）

- [ ] **Step 2: 运行前端类型检查 + 构建**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit && npx vite build 2>&1 | tail -20
```

预期：类型检查通过，构建成功

- [ ] **Step 3: 验证 seed-db CLI 可用**

```bash
cd /Users/zhongding/dev/thingsboard && python -m process_opt.mock.cli seed-db --help 2>&1
```

预期：显示帮助信息

- [ ] **Step 4: 如有 PostgreSQL 运行，验证数据管道**

```bash
cd /Users/zhongding/dev/thingsboard && python -c "
from src.process_opt.mock.generator import generate_pair
proc, insp = generate_pair('testing-station', 'TEST-001')
print('Process product_model:', proc['product_model'])
print('Inspection product_model:', insp['product_model'])
print('Results:', insp['results'])
print('All results have name/value/result:', all('name' in r and 'value' in r and 'result' in r for r in insp['results']))
"
```

预期：product_model 非空，results 为数组且有 name/value/result。

- [ ] **Step 5: Commit 最终验证**

```bash
git add -A && git status
```
审查修改列表，确认无遗漏文件。

```bash
git commit -m "chore: final verification and test updates for inspection reporting optimization"
```

---

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `db/migrations/004_product_model.sql` | 创建 | product_model + analysis_view 重建 |
| `src/process_opt/common/schemas.py` | 修改 | InspectionItem 模型 + product_model 字段 |
| `src/process_opt/common/repositories.py` | 修改 | upsert 适配 + query_records 加 product_model 过滤 |
| `src/process_opt/consumer/handler.py` | 无改动 | 泛型 handler 自动适配 |
| `src/process_opt/gateway/app.py` | 无改动 | schema 自动生效 |
| `src/process_opt/api/app.py` | 修改 | Protocol + 路由加 product_model 参数 |
| `src/process_opt/api/main.py` | 修改 | RepositoryProxy 透传 product_model |
| `src/process_opt/analysis/dataset.py` | 修改 | 解析新 results 数组格式 |
| `src/process_opt/analysis/spc.py` | 修改 | overview 收集 targets 中数值字段 |
| `src/process_opt/mock/templates.py` | 修改 | results 改为数组格式 |
| `src/process_opt/mock/generator.py` | 修改 | generate_results 返回数组 + product_model |
| `src/process_opt/mock/cli.py` | 修改 | seed-db 适配新格式 |
| `web/src/views/DataView.vue` | 修改 | 适配新 results 数组展示 |
