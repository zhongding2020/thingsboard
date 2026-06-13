# SPC 六合一图监控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone SPC monitoring page with a parameter overview table and 6-in-1 control charts (I-MR, histogram, capability, p-chart) with live monitoring mode.

**Architecture:** New `spc.py` analysis module follows existing pattern (profiling.py / correlation.py). Backend returns overview + per-field SPC data via single POST endpoint. Frontend uses ECharts for 6-chart grid layout with monitoring polling.

**Tech Stack:** Python 3.11 + FastAPI + scipy/numpy, Vue 3 + Element Plus + ECharts 5 + vue-echarts 6

---

### Task 1: SPC Schemas

**Files:**
- Modify: `src/process_opt/analysis/schemas.py`

- [ ] **Step 1: Add SpcRequest, IChart, MrChart, Histogram, Capability, PChart, SummaryStats, ParamOverview, SpcResult schemas**

```python
# Append to src/process_opt/analysis/schemas.py before the class definitions end (after RecommendationResult)

from datetime import datetime


class SpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    field: str | None = None
    usl: float | None = None
    lsl: float | None = None
    target: float | None = None
    since: datetime | None = None


class IChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[float]
    labels: list[str]
    mean: float
    ucl: float
    lcl: float
    alerts: list[int]


class MrChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[float]
    labels: list[str]
    mr_bar: float
    ucl: float


class Histogram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bins: list[float]
    counts: list[int]
    curve_x: list[float]
    curve_y: list[float]


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cp: float
    cpk: float
    pp: float
    ppk: float
    usl: float
    lsl: float
    target: float | None = None


class PChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    periods: list[str]
    rates: list[float]
    total_count: int
    defect_count: int
    ucl: float
    p_bar: float


class SummaryStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    mean: float
    std: float
    min_val: float
    max_val: float
    normality_p: float | None = None


class ParamOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    n: int
    mean: float
    std: float
    usl: float
    lsl: float
    cpk: float
    outlier_count: int
    status: str  # "normal" | "marginal" | "abnormal"


class SpcResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overview: list[ParamOverview]
    i_chart: IChart | None = None
    mr_chart: MrChart | None = None
    histogram: Histogram | None = None
    capability: Capability | None = None
    p_chart: PChart | None = None
    summary: SummaryStats | None = None
```

### Task 2: SPC Computation Module

**Files:**
- Create: `src/process_opt/analysis/spc.py`
- Test: `tests/analysis/test_spc.py`

- [ ] **Step 1: Create spc.py with all computation functions**

```python
from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats

from process_opt.analysis.schemas import (
    AnalysisDataset,
    Capability,
    Histogram,
    IChart,
    MrChart,
    PChart,
    ParamOverview,
    SpcResult,
    SummaryStats,
)


def compute_imr(values: list[float], labels: list[str]) -> tuple[IChart, MrChart]:
    arr = np.array(values, dtype=np.float64)
    n = len(arr)
    mean = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    ucl = mean + 3 * sigma
    lcl = mean - 3 * sigma

    mr_vals = [abs(arr[i] - arr[i - 1]) for i in range(1, n)]
    mr_bar = float(np.mean(mr_vals)) if mr_vals else 0.0
    ucl_mr = 3.267 * mr_bar

    alerts = [i for i, v in enumerate(arr) if v > ucl or v < lcl]

    return (
        IChart(values=values, labels=labels, mean=mean, ucl=ucl, lcl=lcl, alerts=alerts),
        MrChart(values=mr_vals, labels=labels[1:], mr_bar=mr_bar, ucl=ucl_mr),
    )


def compute_histogram(values: list[float], usl: float, lsl: float, bin_count: int = 20) -> Histogram:
    arr = np.array(values, dtype=np.float64)
    counts, edges = np.histogram(arr, bins=bin_count)
    bins = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]

    mu = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    x_range = np.linspace(lsl - sigma, usl + sigma, 200)
    curve = sp_stats.norm.pdf(x_range, mu, sigma) * len(arr) * (edges[1] - edges[0])

    return Histogram(
        bins=bins,
        counts=counts.tolist(),
        curve_x=x_range.tolist(),
        curve_y=curve.tolist(),
    )


def compute_capability(values: list[float], usl: float, lsl: float, target: float | None = None) -> Capability:
    arr = np.array(values, dtype=np.float64)
    mean = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    sigma_p = float(np.std(arr, ddof=0))

    cp = (usl - lsl) / (6 * sigma) if sigma > 0 else 0.0
    cpk = min((usl - mean) / (3 * sigma), (mean - lsl) / (3 * sigma)) if sigma > 0 else 0.0
    pp = (usl - lsl) / (6 * sigma_p) if sigma_p > 0 else 0.0
    ppk = min((usl - mean) / (3 * sigma_p), (mean - lsl) / (3 * sigma_p)) if sigma_p > 0 else 0.0

    return Capability(cp=cp, cpk=cpk, pp=pp, ppk=ppk, usl=usl, lsl=lsl, target=target)


def compute_p_chart(results: list[str], time_groups: list[str]) -> PChart:
    from collections import Counter
    periods = sorted(set(time_groups))
    defect_rates: list[float] = []
    total_defects = 0
    total_count = 0
    for p in periods:
        indices = [i for i, tp in enumerate(time_groups) if tp == p]
        group_results = [results[i] for i in indices]
        n = len(group_results)
        defects = sum(1 for r in group_results if r == "fail" or r == "fail")
        total_defects += defects
        total_count += n
        defect_rates.append(defects / n if n > 0 else 0.0)

    p_bar = total_defects / total_count if total_count > 0 else 0.0
    ucl_p = p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / (total_count / len(periods))) if total_count > 0 and len(periods) > 0 else 0.0

    return PChart(
        periods=periods,
        rates=[round(r, 4) for r in defect_rates],
        total_count=total_count,
        defect_count=total_defects,
        ucl=round(ucl_p, 4),
        p_bar=round(p_bar, 4),
    )


def compute_summary(values: list[float]) -> SummaryStats:
    arr = np.array(values, dtype=np.float64)
    _, p_val = sp_stats.normaltest(arr) if len(arr) >= 8 else (None, None)
    return SummaryStats(
        n=len(arr),
        mean=float(np.mean(arr)),
        std=float(np.std(arr, ddof=1)),
        min_val=float(np.min(arr)),
        max_val=float(np.max(arr)),
        normality_p=float(p_val) if p_val is not None else None,
    )


def _determine_status(cpk: float) -> str:
    if cpk >= 1.33:
        return "normal"
    if cpk >= 1.0:
        return "marginal"
    return "abnormal"


def compute_overview(dataset: AnalysisDataset) -> list[ParamOverview]:
    overviews: list[ParamOverview] = []
    for feat in dataset.features:
        for key, val in feat.items():
            if not isinstance(val, (int, float)):
                continue
            existing = next((o for o in overviews if o.field == key), None)
            if existing is None:
                overviews.append(ParamOverview(
                    field=key,
                    n=0,
                    mean=0.0,
                    std=0.0,
                    usl=0.0,
                    lsl=0.0,
                    cpk=0.0,
                    outlier_count=0,
                    status="normal",
                ))

    field_values: dict[str, list[float]] = {}
    for feat in dataset.features:
        for key, val in feat.items():
            if isinstance(val, (int, float)):
                field_values.setdefault(key, []).append(float(val))

    results_values: dict[str, list[str]] = {}
    for tgt in dataset.targets:
        for key, val in tgt.items():
            if isinstance(val, str):
                results_values.setdefault(key, []).append(val)

    overviews = []
    for field, vals in field_values.items():
        arr = np.array(vals, dtype=np.float64)
        mean = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=1))
        usl = mean + 3 * sigma
        lsl = mean - 3 * sigma

        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = int(np.sum((arr < lower_bound) | (arr > upper_bound)))

        cpk = min((usl - mean) / (3 * sigma), (mean - lsl) / (3 * sigma)) if sigma > 0 else 0.0

        overviews.append(ParamOverview(
            field=field,
            n=len(vals),
            mean=round(mean, 2),
            std=round(sigma, 2),
            usl=round(usl, 2),
            lsl=round(lsl, 2),
            cpk=round(cpk, 2),
            outlier_count=outliers,
            status=_determine_status(cpk),
        ))

    overviews.sort(key=lambda o: o.field)
    return overviews


def build_spc_result(
    dataset: AnalysisDataset,
    field: str | None,
    usl: float | None,
    lsl: float | None,
    target: float | None,
) -> SpcResult:
    overview = compute_overview(dataset)

    if field is None:
        return SpcResult(overview=overview)

    feature_values: list[float] = []
    result_values: list[str] = []
    labels: list[str] = []
    for i in range(dataset.sample_count):
        feat = dataset.features[i]
        val = feat.get(field)
        if isinstance(val, (int, float)):
            feature_values.append(float(val))
            labels.append(dataset.metadata[i].get("barcode", str(i)) if dataset.metadata else str(i))
        for tgt in [dataset.targets[i]]:
            for k, v in tgt.items():
                if isinstance(v, str):
                    result_values.append(v)

    if not feature_values:
        return SpcResult(overview=overview)

    arr = np.array(feature_values, dtype=np.float64)
    auto_usl = float(np.mean(arr) + 3 * np.std(arr, ddof=1))
    auto_lsl = float(np.mean(arr) - 3 * np.std(arr, ddof=1))
    auto_target = float(np.mean(arr))

    final_usl = usl if usl is not None else auto_usl
    final_lsl = lsl if lsl is not None else auto_lsl
    final_target = target if target is not None else auto_target

    i_chart, mr_chart = compute_imr(feature_values, labels)
    histogram = compute_histogram(feature_values, final_usl, final_lsl)
    capability = compute_capability(feature_values, final_usl, final_lsl, final_target)
    p_chart = compute_p_chart(result_values, [m.get("processed_at", "")[:10] for m in dataset.metadata]) if result_values else PChart(periods=[], rates=[], total_count=0, defect_count=0, ucl=0.0, p_bar=0.0)
    summary = compute_summary(feature_values)

    return SpcResult(
        overview=overview,
        i_chart=i_chart,
        mr_chart=mr_chart,
        histogram=histogram,
        capability=capability,
        p_chart=p_chart,
        summary=summary,
    )
```

- [ ] **Step 2: Create test file**

```python
# tests/analysis/test_spc.py
from __future__ import annotations

import numpy as np

from process_opt.analysis.schemas import AnalysisDataset
from process_opt.analysis.spc import (
    build_spc_result,
    compute_capability,
    compute_histogram,
    compute_imr,
    compute_overview,
    compute_p_chart,
    compute_summary,
)


class TestComputeImr:
    def test_returns_i_and_mr_charts(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 50)]
        labels = [f"B{i}" for i in range(50)]
        i_chart, mr_chart = compute_imr(vals, labels)
        assert len(i_chart.values) == 50
        assert len(i_chart.labels) == 50
        assert i_chart.ucl > i_chart.mean
        assert i_chart.lcl < i_chart.mean
        assert len(mr_chart.values) == 49
        assert mr_chart.ucl > 0

    def test_identifies_out_of_control_points(self) -> None:
        vals = [100.0] * 20 + [300.0, 100.0]
        labels = [f"B{i}" for i in range(22)]
        i_chart, mr_chart = compute_imr(vals, labels)
        assert 20 in i_chart.alerts

    def test_empty_values(self) -> None:
        i_chart, mr_chart = compute_imr([], [])
        assert i_chart.values == []
        assert mr_chart.values == []


class TestComputeCapability:
    def test_returns_indices(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 100)]
        cap = compute_capability(vals, 115, 85)
        assert cap.cp > 0
        assert cap.cpk > 0
        assert cap.pp > 0
        assert cap.ppk > 0
        assert cap.usl == 115
        assert cap.lsl == 85

    def test_perfect_process_has_high_cpk(self) -> None:
        vals = [100.0] * 50
        cap = compute_capability(vals, 110, 90)
        assert cap.cpk > 1.5


class TestComputeHistogram:
    def test_returns_bins_and_curve(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 200)]
        hist = compute_histogram(vals, 115, 85)
        assert len(hist.bins) == 20
        assert len(hist.counts) == 20
        assert len(hist.curve_x) == 200
        assert len(hist.curve_y) == 200


class TestComputePChart:
    def test_returns_defect_rates(self) -> None:
        results = ["pass", "pass", "fail", "pass", "fail", "pass", "pass", "pass", "fail", "pass"]
        groups = ["2026-06-01", "2026-06-01", "2026-06-01", "2026-06-01", "2026-06-01",
                   "2026-06-02", "2026-06-02", "2026-06-02", "2026-06-02", "2026-06-02"]
        p = compute_p_chart(results, groups)
        assert len(p.periods) == 2
        assert p.defect_count == 3
        assert p.total_count == 10
        assert p.p_bar == 0.3

    def test_no_results(self) -> None:
        p = compute_p_chart([], [])
        assert p.periods == []


class TestComputeSummary:
    def test_returns_stats(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 100)]
        s = compute_summary(vals)
        assert s.n == 100
        assert 90 < s.mean < 110
        assert s.std > 0
        assert s.min_val < s.max_val

    def test_normality_p_is_none_for_small_samples(self) -> None:
        s = compute_summary([1.0, 2.0, 3.0])
        assert s.normality_p is None


class TestBuildSpcResult:
    def test_overview_only_when_no_field(self) -> None:
        ds = AnalysisDataset(
            features=[{"temperature": 180.0}, {"temperature": 190.0}],
            targets=[{"quality": "pass"}, {"quality": "pass"}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={},
            sample_count=2,
        )
        result = build_spc_result(ds, field=None, usl=None, lsl=None, target=None)
        assert len(result.overview) > 0
        assert result.i_chart is None

    def test_full_result_with_field(self) -> None:
        ds = AnalysisDataset(
            features=[{"temperature": 180.0}, {"temperature": 190.0}, {"temperature": 200.0}],
            targets=[{"quality": "pass"}, {"quality": "pass"}, {"quality": "fail"}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}, {"barcode": "B3"}],
            field_summary={},
            sample_count=3,
        )
        result = build_spc_result(ds, field="temperature", usl=210.0, lsl=170.0, target=190.0)
        assert result.i_chart is not None
        assert len(result.i_chart.values) == 3
        assert result.capability is not None
        assert result.capability.usl == 210.0
        assert result.capability.lsl == 170.0
        assert result.p_chart is not None
        assert result.summary is not None
        assert result.summary.n == 3
```

- [ ] **Step 3: Run tests to verify**

Run: `.venv/bin/python -m pytest tests/analysis/test_spc.py -v`
Expected: All tests pass

### Task 3: Wire SPC into Service Layer

**Files:**
- Modify: `src/process_opt/analysis/service.py`
- Modify: `src/process_opt/api/main.py`
- Modify: `src/process_opt/api/app.py`

- [ ] **Step 1: Add spc-related methods to AnalysisService**

```python
# In src/process_opt/analysis/service.py, add after profile_from_request:

    async def spc(self, request: SpcRequest) -> SpcResult:
        from process_opt.analysis.spc import build_spc_result
        dataset_req = AnalysisDatasetRequest(
            feature_fields=[request.field] if request.field else [],
            target_fields=["dummy"],
        )
        dataset = await self.build_dataset(dataset_req)

        field = request.field
        if field and field not in {f for feat in dataset.features for f in feat}:
            existing = sorted({f for feat in dataset.features for f in feat})
            raise AnalysisError(
                code="FIELD_NOT_FOUND",
                message=f"Field '{field}' not found in data",
                suggestion=f"Available fields: {existing}",
            )

        return build_spc_result(
            dataset=dataset,
            field=field,
            usl=request.usl,
            lsl=request.lsl,
            target=request.target,
        )
```

- [ ] **Step 2: Add import for SpcRequest/SpcResult in service.py**

```python
# Update the import line in service.py:
from process_opt.analysis.schemas import (
    AnalysisDataset,
    AnalysisDatasetRequest,
    CorrelationRequest,
    CorrelationResult,
    ImportanceRequest,
    ImportanceResult,
    ProfilingResult,
    RecommendationRequest,
    RecommendationResult,
    RegressionRequest,
    RegressionResult,
    SpcRequest,
    SpcResult,
)
```

- [ ] **Step 3: Add spc method to AnalysisServiceProxy in main.py**

```python
# In src/process_opt/api/main.py, add to AnalysisServiceProxy class:

    async def spc(self, request: SpcRequest) -> SpcResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.spc(request)
```

- [ ] **Step 4: Add import for SpcRequest/SpcResult in main.py**

```python
# Update the import line:
from process_opt.analysis.schemas import (
    ...,  # keep existing
    SpcRequest,
    SpcResult,
)
```

- [ ] **Step 5: Add SPC route in app.py**

```python
# In src/process_opt/api/app.py, inside `if analysis_service is not None:` block, add:

        @app.post("/api/v1/analysis/spc")
        async def spc_route(body: SpcRequest) -> SpcResult:
            return await analysis_service.spc(body)
```

- [ ] **Step 6: Add import for SpcRequest/SpcResult in app.py**

```python
# Update the import line:
from process_opt.analysis.schemas import (
    ...,
    SpcRequest,
    SpcResult,
)
```

### Task 4: SPC API Tests

**Files:**
- Modify: `tests/api/test_analysis_api.py`

- [ ] **Step 1: Add FakeAnalysisService.spc method**

```python
# Add to FakeAnalysisService class:
    async def spc(self, request: SpcRequest) -> SpcResult:
        from process_opt.analysis.schemas import SpcResult
        return SpcResult(
            overview=[
                ParamOverview(
                    field="temperature", n=10, mean=200.0, std=5.0,
                    usl=215.0, lsl=185.0, cpk=1.0, outlier_count=0, status="marginal",
                )
            ],
            i_chart=IChart(values=[200.0], labels=["B1"], mean=200.0, ucl=215.0, lcl=185.0, alerts=[]),
            mr_chart=MrChart(values=[], labels=[], mr_bar=0.0, ucl=0.0),
            histogram=Histogram(bins=[], counts=[], curve_x=[], curve_y=[]),
            capability=Capability(cp=1.0, cpk=1.0, pp=1.0, ppk=1.0, usl=215.0, lsl=185.0),
            p_chart=PChart(periods=[], rates=[], total_count=0, defect_count=0, ucl=0.0, p_bar=0.0),
            summary=SummaryStats(n=1, mean=200.0, std=0.0, min_val=200.0, max_val=200.0, normality_p=None),
        )
```

- [ ] **Step 2: Add imports to test file**

```python
# Add to the import block:
from process_opt.analysis.schemas import (
    ...,
    IChart,
    MrChart,
    Histogram,
    Capability,
    PChart,
    ParamOverview,
    SummaryStats,
    SpcRequest,
    SpcResult,
)
```

- [ ] **Step 3: Add test_spc_returns_spc_result test**

```python
# Add after test_recommendation_success test:
@pytest.mark.asyncio
async def test_spc_returns_spc_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/spc",
            json={"device_id": "D1", "field": "temperature"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["overview"]) == 1
    assert data["overview"][0]["field"] == "temperature"
    assert data["overview"][0]["cpk"] == 1.0
    assert data["i_chart"] is not None
    assert data["i_chart"]["mean"] == 200.0

@pytest.mark.asyncio
async def test_spc_overview_only() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/spc",
            json={"device_id": "D1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["overview"]) == 1
    assert data["i_chart"] is None
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

### Task 5: Frontend API Module

**Files:**
- Create: `web/src/api/spc.ts`

- [ ] **Step 1: Create spc API client**

```typescript
// web/src/api/spc.ts
import client from './client'

export interface SpcRequest {
  device_id: string
  field?: string
  usl?: number
  lsl?: number
  target?: number
  since?: string
}

export interface SpcResult {
  overview: ParamOverview[]
  i_chart: IChart | null
  mr_chart: MrChart | null
  histogram: Histogram | null
  capability: Capability | null
  p_chart: PChart | null
  summary: SummaryStats | null
}

export interface ParamOverview {
  field: string
  n: number
  mean: number
  std: number
  usl: number
  lsl: number
  cpk: number
  outlier_count: number
  status: 'normal' | 'marginal' | 'abnormal'
}

export interface IChart {
  values: number[]
  labels: string[]
  mean: number
  ucl: number
  lcl: number
  alerts: number[]
}

export interface MrChart {
  values: number[]
  labels: string[]
  mr_bar: number
  ucl: number
}

export interface Histogram {
  bins: number[]
  counts: number[]
  curve_x: number[]
  curve_y: number[]
}

export interface Capability {
  cp: number
  cpk: number
  pp: number
  ppk: number
  usl: number
  lsl: number
  target: number | null
}

export interface PChart {
  periods: string[]
  rates: number[]
  total_count: number
  defect_count: number
  ucl: number
  p_bar: number
}

export interface SummaryStats {
  n: number
  mean: number
  std: number
  min_val: number
  max_val: number
  normality_p: number | null
}

export function fetchSpc(data: SpcRequest): Promise<SpcResult> {
  return client.post('/analysis/spc', data).then((res) => res.data)
}
```

### Task 6: Frontend SPC View

**Files:**
- Create: `web/src/views/SpcView.vue`

- [ ] **Step 1: Create SpcView.vue**

```vue
<template>
  <div class="spc-view">
    <div class="spc-header">
      <h2 class="page-title">SPC 监控</h2>
      <p class="page-desc">统计过程控制六合一图</p>
    </div>

    <el-card class="spc-filter-card">
      <div class="spc-filter-bar">
        <el-form :inline="true" :model="filter">
          <el-form-item label="设备">
            <el-select v-model="filter.deviceId" placeholder="选择设备" clearable style="width: 160px">
              <el-option v-for="d in devices" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="timeRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleQuery">查询</el-button>
          </el-form-item>
        </el-form>
        <div class="spc-monitor-controls">
          <div class="monitor-interval">
            <span>间隔</span>
            <el-select v-model="monitorInterval" size="small" style="width: 80px">
              <el-option label="5s" :value="5" />
              <el-option label="10s" :value="10" />
              <el-option label="30s" :value="30" />
            </el-select>
          </div>
          <el-button
            :type="monitoring ? 'danger' : 'success'"
            @click="toggleMonitoring"
          >
            {{ monitoring ? '● 停止监控' : '● 启动监控' }}
          </el-button>
        </div>
      </div>
      <div v-if="monitoring" class="monitor-bar">
        <span class="monitor-dot" /> 监控中 · 下次刷新 {{ countdown }}s · 数据点 {{ spcResult?.summary?.n ?? 0 }}
      </div>
    </el-card>

    <el-card v-if="spcResult?.overview?.length" class="overview-card">
      <template #header>
        <span class="section-title">参数概览</span>
        <span class="section-subtitle">点击行切换 SPC 图</span>
      </template>
      <el-table
        :data="spcResult.overview"
        stripe
        size="small"
        highlight-current-row
        @row-click="handleParamClick"
      >
        <el-table-column prop="field" label="参数" min-width="140" class-name="cell-mono" />
        <el-table-column prop="usl" label="上限(USL)" width="110" class-name="cell-mono" />
        <el-table-column prop="lsl" label="下限(LSL)" width="110" class-name="cell-mono" />
        <el-table-column prop="n" label="数据量" width="80" class-name="cell-mono" />
        <el-table-column prop="cpk" label="Cpk" width="80" class-name="cell-mono" />
        <el-table-column prop="outlier_count" label="离群数" width="80" class-name="cell-mono" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div v-if="spcResult?.i_chart" class="spc-charts-grid">
      <el-card class="chart-card" v-for="chart in charts" :key="chart.title">
        <template #header>
          <span class="chart-title">{{ chart.title }}</span>
        </template>
        <div class="chart-body" :style="{ height: chart.height + 'px' }">
          <v-chart v-if="chart.visible" :option="chart.option" autoresize />
          <el-empty v-else description="暂无数据" :image-size="40" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
} from 'echarts/components'
import { fetchSpc, type SpcResult, type ParamOverview } from '@/api/spc'
import { listDevices } from '@/api/records'

use([
  CanvasRenderer, LineChart, BarChart,
  GridComponent, TooltipComponent, MarkLineComponent, MarkPointComponent, TitleComponent,
])

const devices = ref<string[]>([])
const timeRange = ref<[Date, Date] | null>([new Date(Date.now() - 604800000), new Date()])
const spcResult = ref<SpcResult | null>(null)
const selectedField = ref('')
const loading = ref(false)

const monitoring = ref(false)
const monitorInterval = ref(10)
const countdown = ref(0)
let monitorTimer: ReturnType<typeof setInterval> | undefined
let countdownTimer: ReturnType<typeof setInterval> | undefined

const filter = reactive({
  deviceId: '',
})

const charts = computed(() => {
  const r = spcResult.value
  if (!r) return []
  return [
    {
      title: `I 单值图 — ${selectedField.value}`,
      height: 280,
      visible: !!r.i_chart,
      option: buildIChartOption(r.i_chart),
    },
    {
      title: 'MR 移动极差图',
      height: 280,
      visible: !!r.mr_chart,
      option: buildMrChartOption(r.mr_chart),
    },
    {
      title: '直方图 + 正态曲线',
      height: 280,
      visible: !!r.histogram,
      option: buildHistogramOption(r.histogram, r.capability),
    },
    {
      title: 'P 不合格品率图',
      height: 280,
      visible: !!(r.p_chart && r.p_chart.periods.length > 0),
      option: buildPChartOption(r.p_chart),
    },
    {
      title: '过程能力指数',
      height: 200,
      visible: !!r.capability,
      option: buildCapabilityOption(r.capability),
    },
    {
      title: '数据摘要',
      height: 200,
      visible: !!r.summary,
      option: buildSummaryOption(r.summary, r.capability),
    },
  ]
})

function statusTagType(status: string): string {
  switch (status) {
    case 'normal': return 'success'
    case 'marginal': return 'warning'
    case 'abnormal': return 'danger'
    default: return 'info'
  }
}

function statusText(status: string): string {
  switch (status) {
    case 'normal': return '正常'
    case 'marginal': return '边缘'
    case 'abnormal': return '异常'
    default: return status
  }
}

function handleParamClick(row: ParamOverview) {
  selectedField.value = row.field
  loadSpc()
}

async function loadSpc() {
  if (!filter.deviceId || !selectedField.value) return
  loading.value = true
  try {
    spcResult.value = await fetchSpc({
      device_id: filter.deviceId,
      field: selectedField.value,
    })
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  if (!filter.deviceId) return
  loading.value = true
  try {
    spcResult.value = await fetchSpc({ device_id: filter.deviceId })
    if (spcResult.value.overview.length && !selectedField.value) {
      selectedField.value = spcResult.value.overview[0].field
      await loadSpc()
    }
  } finally {
    loading.value = false
  }
}

async function handleQuery() {
  selectedField.value = ''
  await loadOverview()
}

function toggleMonitoring() {
  monitoring.value = !monitoring.value
  if (monitoring.value) {
    countdown.value = monitorInterval.value
    monitorTimer = setInterval(async () => {
      if (filter.deviceId && selectedField.value) {
        try {
          spcResult.value = await fetchSpc({
            device_id: filter.deviceId,
            field: selectedField.value,
          })
        } catch {
          // silently retry on next tick
        }
      }
      countdown.value = monitorInterval.value
    }, monitorInterval.value * 1000)
    countdownTimer = setInterval(() => {
      if (countdown.value > 0) countdown.value--
    }, 1000)
  } else {
    clearInterval(monitorTimer)
    clearInterval(countdownTimer)
    monitorTimer = undefined
    countdownTimer = undefined
  }
}

onMounted(async () => {
  try {
    devices.value = await listDevices()
  } catch {
    // silently fail
  }
})

onUnmounted(() => {
  clearInterval(monitorTimer)
  clearInterval(countdownTimer)
})

function buildIChartOption(chart: SpcResult['i_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: chart.labels, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        data: chart.values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 1.5 },
        itemStyle: {
          color: (params: any) => chart.alerts.includes(params.dataIndex) ? '#DC2626' : '#3B82F6',
        },
        markLine: {
          silent: true,
          data: [
            { yAxis: chart.mean, label: { formatter: `CL: ${chart.mean.toFixed(1)}` }, lineStyle: { type: 'solid', color: '#059669' } },
            { yAxis: chart.ucl, label: { formatter: `UCL: ${chart.ucl.toFixed(1)}` }, lineStyle: { type: 'dashed', color: '#DC2626' } },
            { yAxis: chart.lcl, label: { formatter: `LCL: ${chart.lcl.toFixed(1)}` }, lineStyle: { type: 'dashed', color: '#DC2626' } },
          ],
        },
      },
    ],
  }
}

function buildMrChartOption(chart: SpcResult['mr_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: chart.labels, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        data: chart.values,
        step: 'end',
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 1.5, color: '#F59E0B' },
        areaStyle: { color: 'rgba(245, 158, 11, 0.1)' },
        markLine: {
          silent: true,
          data: [
            { yAxis: chart.mr_bar, label: { formatter: `MR̄: ${chart.mr_bar.toFixed(1)}` }, lineStyle: { type: 'solid', color: '#059669' } },
            { yAxis: chart.ucl, label: { formatter: `UCL: ${chart.ucl.toFixed(1)}` }, lineStyle: { type: 'dashed', color: '#DC2626' } },
          ],
        },
      },
    ],
  }
}

function buildHistogramOption(hist: SpcResult['histogram'], cap: SpcResult['capability']) {
  if (!hist || !cap) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: hist.counts.map((c, i) => [hist.bins[i], c]),
        barWidth: '90%',
        itemStyle: { color: '#3B82F6', opacity: 0.6 },
      },
      {
        type: 'line',
        data: hist.curve_x.map((x, i) => [x, hist.curve_y[i]]),
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#DC2626', width: 2 },
      },
    ],
  }
}

function buildPChartOption(chart: SpcResult['p_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: chart.periods, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'line',
        data: chart.rates.map((r) => +(r * 100).toFixed(2)),
        symbol: 'diamond',
        symbolSize: 8,
        lineStyle: { width: 1.5, color: '#8B5CF6' },
        markLine: {
          silent: true,
          data: [
            { yAxis: chart.p_bar * 100, label: { formatter: `p̄: ${(chart.p_bar * 100).toFixed(1)}%` }, lineStyle: { type: 'solid', color: '#059669' } },
            { yAxis: chart.ucl * 100, label: { formatter: `UCL: ${(chart.ucl * 100).toFixed(1)}%` }, lineStyle: { type: 'dashed', color: '#DC2626' } },
          ],
        },
      },
    ],
  }
}

function buildCapabilityOption(cap: SpcResult['capability']) {
  if (!cap) return {}
  return {
    tooltip: { trigger: 'item' },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { show: false },
    yAxis: { show: false },
    series: [
      {
        type: 'bar',
        data: [
          { value: cap.cp, itemStyle: { color: cap.cp >= 1.33 ? '#059669' : cap.cp >= 1.0 ? '#D97706' : '#DC2626' } },
          { value: cap.cpk, itemStyle: { color: cap.cpk >= 1.33 ? '#059669' : cap.cpk >= 1.0 ? '#D97706' : '#DC2626' } },
          { value: cap.pp, itemStyle: { color: cap.pp >= 1.33 ? '#059669' : cap.pp >= 1.0 ? '#D97706' : '#DC2626' } },
          { value: cap.ppk, itemStyle: { color: cap.ppk >= 1.33 ? '#059669' : cap.ppk >= 1.0 ? '#D97706' : '#DC2626' } },
        ],
        barWidth: 20,
        label: {
          show: true,
          position: 'top',
          formatter: (p: any) => p.name + ': ' + p.value.toFixed(2),
          fontSize: 11,
        },
      },
    ],
    dataset: {
      dimensions: ['name', 'value'],
      source: [
        { name: 'Cp', value: cap.cp },
        { name: 'Cpk', value: cap.cpk },
        { name: 'Pp', value: cap.pp },
        { name: 'Ppk', value: cap.ppk },
      ],
    },
  }
}

function buildSummaryOption(summary: SpcResult['summary'], cap: SpcResult['capability']) {
  if (!summary) return {}
  return {
    tooltip: { trigger: 'item' },
    series: [],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: [
            `N: ${summary.n}`,
            `Mean: ${summary.mean.toFixed(2)}`,
            `Std: ${summary.std.toFixed(2)}`,
            `Min: ${summary.min_val}`,
            `Max: ${summary.max_val}`,
            `USL: ${cap?.usl.toFixed(2) ?? '-'}`,
            `LSL: ${cap?.lsl.toFixed(2) ?? '-'}`,
          ].join('\n'),
          fontSize: 13,
          lineHeight: 22,
          fontFamily: 'Fira Code, monospace',
          textAlign: 'center',
          fill: '#CBD5E1',
        },
      },
    ],
  }
}
</script>

<style scoped>
.spc-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.spc-header {
  flex-shrink: 0;
}
.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 2px;
}
.page-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.spc-filter-card {
  flex-shrink: 0;
}
.spc-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.spc-monitor-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.monitor-interval {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.monitor-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 4px;
  font-size: 12px;
  color: #DC2626;
  margin-top: 8px;
}
.monitor-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #DC2626;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.overview-card {
  flex-shrink: 0;
}
.overview-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
}
.section-title {
  font-size: 13px;
  font-weight: 500;
}
.section-subtitle {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.spc-charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  padding-bottom: 12px;
}
.chart-card {
  display: flex;
  flex-direction: column;
}
.chart-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  padding: 8px;
}
.chart-body {
  width: 100%;
}
.chart-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}
</style>
```

### Task 7: Add Router and Sidebar

**Files:**
- Modify: `web/src/router/index.ts`
- Modify: `web/src/components/AppLayout.vue`

- [ ] **Step 1: Add SPC route**

```typescript
// In web/src/router/index.ts, add to children:
{ path: 'spc', component: () => import('@/views/SpcView.vue') },
```

- [ ] **Step 2: Add sidebar menu item**

```vue
<!-- In AppLayout.vue, add after </el-menu-item index="/data"> -->
<el-menu-item index="/spc">
  <el-icon><TrendCharts /></el-icon>
  <span>SPC监控</span>
</el-menu-item>
```

- [ ] **Step 3: Add TrendCharts icon import**

```typescript
// In AppLayout.vue, add TrendCharts to the icon imports:
import { Monitor, DocumentCopy, TrendCharts, DataAnalysis, Setting, Tools } from '@element-plus/icons-vue'
```

### Task 8: Build and Verify

- [ ] **Step 1: Frontend type check**

Run: `cd web && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Frontend build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Backend full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 4: Docker build and restart**

Run: `docker compose build backend-api && docker compose up -d backend-api`
Expected: Container starts successfully

- [ ] **Step 5: Verify API endpoint**

Run: `curl -s -X POST http://localhost:8000/api/v1/analysis/spc -H "Content-Type: application/json" -d '{"device_id":"reflow-oven","field":"temperature"}' | python3 -m json.tool`
Expected: Returns SPC result with overview, i_chart, mr_chart, etc.
