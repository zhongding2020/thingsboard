# 关联分析模块优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 在参数调优模块中新增帕累托图分析和 Cpk 模拟退火优化功能

**架构:** 后端新增 2 个 Python 模块(pareto.py / optimization.py) + 2 个 API 端点，前端新增 2 个 Vue 组件(ParetoChart / CpkOptimizer) + 增强 CorrelationChart + 集成到 AnalysisView

**技术栈:** Python FastAPI / NumPy / scipy / scikit-learn / Vue 3 / ECharts / Element Plus

---

### Task 1: 后端数据模型扩展

**文件:**
- Modify: `src/process_opt/analysis/schemas.py:1-218` — 追加 4 个新 Pydantic 模型

- [ ] **Step 1: 在 schemas.py 末尾追加新模型**

```python
class ParetoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    field_y: str


class ParetoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    coefficient: float
    contribution_pct: float
    cumulative_pct: float
    strength: str  # "strong"|"medium"|"weak"|"negligible"


class OptimizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    target_field: str
    usl: float
    lsl: float
    target_value: float
    target_cpk: float = 1.33
    key_factors: list[str] = Field(min_length=1)
    step_size: float = Field(gt=0)
    max_iterations: int = Field(default=5000, ge=100, le=50000)


class OptimizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_cpk: float
    optimized_cpk: float
    convergence: list[dict[str, float]]          # [{iteration, cpk_value}]
    recommended_params: dict[str, float]
    parameter_adjustments: dict[str, dict[str, float]]  # {因子: {from, to, delta}}
    target_field: str
```

追加在 `TargetConfig` 或末尾（如文件末尾是 `SpcResult`，则追加在其后）。

- [ ] **Step 2: 验证导入**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -c "
from process_opt.analysis.schemas import ParetoRequest, ParetoItem, OptimizationConfig, OptimizationResult
print('OK: models imported successfully')
"
```

Expected: `OK: models imported successfully`

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: add pareto and optimization schemas"
```

---

### Task 2: 帕累托图计算模块

**文件:**
- Create: `src/process_opt/analysis/pareto.py`
- Create: `tests/analysis/test_pareto.py`

- [ ] **Step 1: 写测试**

```python
from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


class TestComputePareto:
    def test_returns_items_sorted_by_coefficient(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1: list[float] = rng.normal(0, 1, n).tolist()
        x2: list[float] = rng.normal(0, 1, n).tolist()
        x3: list[float] = rng.normal(0, 1, n).tolist()
        y: list[float] = [x1[i] * 2 + rng.normal(0, 0.3) for i in range(n)]

        features = [{"x1": x1[i], "x2": x2[i], "x3": x3[i]} for i in range(n)]
        targets = [{"y": y[i]} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.pareto import compute_pareto

        items = compute_pareto(ds, "y")

        assert len(items) == 3
        coeffs = [i.coefficient for i in items]
        assert coeffs == sorted(coeffs, reverse=True)

    def test_cumulative_pct_sums_to_100(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = x1 + x2 + rng.normal(0, 0.2, n)

        features = [{"x1": float(x1[i]), "x2": float(x2[i])} for i in range(n)]
        targets = [{"y": float(y[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.pareto import compute_pareto

        items = compute_pareto(ds, "y")

        assert pytest.approx(items[-1].cumulative_pct, 0.01) == 100.0

    def test_strength_classification(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x_strong = rng.normal(0, 1, n)
        x_medium = rng.normal(0, 1, n)
        x_weak = rng.normal(0, 1, n)
        x_none = rng.normal(0, 1, n)
        y = (x_strong * 3 + rng.normal(0, 0.2, n))

        features = [
            {"s": float(x_strong[i]), "m": float(x_medium[i]),
             "w": float(x_weak[i]), "n": float(x_none[i])}
            for i in range(n)
        ]
        targets = [{"y": float(y[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.pareto import compute_pareto

        items = compute_pareto(ds, "y")

        strengths = {i.field: i.strength for i in items}
        assert strengths["s"] in ("strong",)
        # The others depend on actual |r| values

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )

        from process_opt.analysis.pareto import compute_pareto

        with pytest.raises(AnalysisError) as exc:
            compute_pareto(ds, "y")
        assert exc.value.code == "EMPTY_DATASET"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/analysis/test_pareto.py -v 2>&1 | tail -10
```

Expected: `FAILED` with `ModuleNotFoundError` (pareto 模块不存在)

- [ ] **Step 3: 实现 compute_pareto**

```python
from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, ParetoItem


def _classify_strength(r: float) -> str:
    """Classify correlation strength by absolute value."""
    abs_r = abs(r)
    if abs_r > 0.7:
        return "strong"
    if abs_r > 0.5:
        return "medium"
    if abs_r > 0.3:
        return "weak"
    return "negligible"


def compute_pareto(
    dataset: AnalysisDataset,
    field_y: str,
) -> list[ParetoItem]:
    if dataset.sample_count == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute Pareto on empty dataset",
        )

    # Extract all Y values
    y_vals = []
    for tgt in dataset.targets:
        v = tgt.get(field_y)
        if v is None or not isinstance(v, (int, float)):
            raise AnalysisError(
                code="NON_NUMERIC_FIELD",
                message=f"Target field '{field_y}' contains non-numeric or missing values",
            )
        y_vals.append(float(v))
    y_arr = np.array(y_vals, dtype=np.float64)

    # Get all X feature field names
    feature_names = sorted({k for f in dataset.features for k in f})

    # Compute correlation for each X vs Y
    pairs: list[tuple[str, float]] = []
    for field in feature_names:
        x_vals = []
        for feat in dataset.features:
            v = feat.get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Feature field '{field}' contains non-numeric or missing values",
                )
            x_vals.append(float(v))
        x_arr = np.array(x_vals, dtype=np.float64)
        coeff, _ = scipy_stats.pearsonr(x_arr, y_arr)
        pairs.append((field, abs(float(coeff))))

    # Sort by |r| descending
    pairs.sort(key=lambda p: p[1], reverse=True)
    total = sum(p[1] for p in pairs) or 1.0

    # Build Pareto items with cumulative contribution
    items: list[ParetoItem] = []
    cumulative = 0.0
    for field, abs_r in pairs:
        contribution = (abs_r / total) * 100.0
        cumulative += contribution
        items.append(ParetoItem(
            field=field,
            coefficient=round(abs_r, 4),
            contribution_pct=round(contribution, 2),
            cumulative_pct=round(cumulative, 2),
            strength=_classify_strength(abs_r),
        ))

    return items
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/analysis/test_pareto.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: pareto chart computation module"
```

---

### Task 3: 模拟退火优化模块

**文件:**
- Create: `src/process_opt/analysis/optimization.py`
- Create: `tests/analysis/test_optimization.py`

- [ ] **Step 1: 写测试**

```python
from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, OptimizationConfig


def _make_dataset(
    x1: np.ndarray, x2: np.ndarray, y: np.ndarray,
) -> AnalysisDataset:
    n = len(x1)
    features = [
        {"temp": float(x1[i]), "pressure": float(x2[i])}
        for i in range(n)
    ]
    targets = [{"strength": float(y[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{} for _ in range(n)],
        field_summary={}, sample_count=n,
    )


class TestRunOptimization:
    def test_returns_optimization_result(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        temp = rng.uniform(150, 250, n)
        pressure = rng.uniform(1.0, 5.0, n)
        strength = 100 + 0.3 * (temp - 200) - 5 * (pressure - 3) + rng.normal(0, 2, n)

        ds = _make_dataset(temp, pressure, strength)

        config = OptimizationConfig(
            dataset_id="test",
            target_field="strength",
            usl=115.0,
            lsl=85.0,
            target_value=100.0,
            target_cpk=1.33,
            key_factors=["temp", "pressure"],
            step_size=5.0,
            max_iterations=1000,
        )

        from process_opt.analysis.optimization import run_optimization

        result = run_optimization(ds, config)

        assert result.target_field == "strength"
        assert result.optimized_cpk > 0
        assert len(result.convergence) > 0
        assert "temp" in result.recommended_params
        assert "pressure" in result.recommended_params
        assert result.initial_cpk > 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/analysis/test_optimization.py -v 2>&1 | tail -10
```

Expected: `FAILED` with ModuleNotFoundError

- [ ] **Step 3: 实现 run_optimization**

```python
from __future__ import annotations

import math

import numpy as np
from sklearn.linear_model import LinearRegression

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, OptimizationConfig, OptimizationResult


def _extract_arrays(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    n = dataset.sample_count
    feat_cols: list[list[float]] = [[] for _ in feature_fields]
    tgt_vals: list[float] = []

    for i in range(n):
        for j, field in enumerate(feature_fields):
            v = dataset.features[i].get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Field '{field}' contains non-numeric or missing values",
                )
            feat_cols[j].append(float(v))
        v = dataset.targets[i].get(target_field)
        if v is None or not isinstance(v, (int, float)):
            raise AnalysisError(
                code="NON_NUMERIC_FIELD",
                message=f"Target field '{target_field}' contains non-numeric or missing values",
            )
        tgt_vals.append(float(v))

    X = np.column_stack([np.array(col, dtype=np.float64) for col in feat_cols])
    y = np.array(tgt_vals, dtype=np.float64)
    return X, y


def _compute_cpk(y_pred: float, usl: float, lsl: float, rmse: float) -> float:
    if rmse <= 0 or y_pred <= lsl or y_pred >= usl:
        return 0.0
    sigma = rmse
    cpu = (usl - y_pred) / (3 * sigma)
    cpl = (y_pred - lsl) / (3 * sigma)
    return min(cpu, cpl)


def run_optimization(
    dataset: AnalysisDataset,
    config: OptimizationConfig,
) -> OptimizationResult:
    if dataset.sample_count == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot run optimization on empty dataset",
        )

    # Fit regression model
    X, y = _extract_arrays(dataset, config.key_factors, config.target_field)
    model = LinearRegression()
    model.fit(X, y)
    y_pred_all = model.predict(X)
    rmse = float(np.sqrt(np.mean((y - y_pred_all) ** 2)))

    # Infer bounds from data
    bounds: dict[str, tuple[float, float]] = {}
    for j, field in enumerate(config.key_factors):
        col = X[:, j]
        bounds[field] = (float(col.min()), float(col.max()))

    # Compute initial Cpk (using current mean of each factor)
    initial_params = {field: float(X[:, j].mean()) for j, field in enumerate(config.key_factors)}
    X_init = np.array([[initial_params[f] for f in config.key_factors]], dtype=np.float64)
    y_init_pred = float(model.predict(X_init)[0])
    initial_cpk = _compute_cpk(y_init_pred, config.usl, config.lsl, rmse)

    # Simulated annealing
    current_params = initial_params.copy()
    current_X = np.array([[current_params[f] for f in config.key_factors]], dtype=np.float64)
    current_y_pred = float(model.predict(current_X)[0])
    current_cpk = _compute_cpk(current_y_pred, config.usl, config.lsl, rmse)
    current_loss = _loss(current_cpk, current_y_pred, config)

    best_params = current_params.copy()
    best_loss = current_loss

    T0 = 100.0
    alpha = 0.95
    convergence: list[dict[str, float]] = []

    for iteration in range(config.max_iterations):
        T = T0 * (alpha ** iteration)

        # Propose new solution
        new_params = current_params.copy()
        for field in config.key_factors:
            step = config.step_size * (T / T0)
            lo, hi = bounds[field]
            delta = np.random.uniform(-step, step)
            new_params[field] = max(lo, min(hi, new_params[field] + delta))

        new_X = np.array([[new_params[f] for f in config.key_factors]], dtype=np.float64)
        new_y_pred = float(model.predict(new_X)[0])
        new_cpk = _compute_cpk(new_y_pred, config.usl, config.lsl, rmse)
        new_loss = _loss(new_cpk, new_y_pred, config)

        delta_loss = new_loss - current_loss

        if delta_loss < 0 or (T > 0 and np.random.random() < math.exp(-delta_loss / max(T, 1e-10))):
            current_params = new_params
            current_y_pred = new_y_pred
            current_cpk = new_cpk
            current_loss = new_loss

            if current_loss < best_loss:
                best_params = current_params.copy()
                best_loss = current_loss

        if iteration % 50 == 0 or iteration == config.max_iterations - 1:
            convergence.append({"iteration": iteration, "cpk_value": round(current_cpk, 4)})

    # Compute final Cpk with best params
    best_X = np.array([[best_params[f] for f in config.key_factors]], dtype=np.float64)
    best_y_pred = float(model.predict(best_X)[0])
    optimized_cpk = _compute_cpk(best_y_pred, config.usl, config.lsl, rmse)

    # Build adjustments dict
    adjustments: dict[str, dict[str, float]] = {}
    for field in config.key_factors:
        orig = initial_params[field]
        opt = best_params[field]
        adjustments[field] = {
            "from": round(orig, 2),
            "to": round(opt, 2),
            "delta": round(opt - orig, 2),
        }

    return OptimizationResult(
        initial_cpk=round(initial_cpk, 4),
        optimized_cpk=round(optimized_cpk, 4),
        convergence=convergence,
        recommended_params={k: round(v, 4) for k, v in best_params.items()},
        parameter_adjustments=adjustments,
        target_field=config.target_field,
    )


def _loss(cpk: float, y_pred: float, config: OptimizationConfig) -> float:
    if cpk < config.target_cpk:
        return (config.target_cpk - cpk) ** 2
    else:
        return abs(y_pred - config.target_value)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/analysis/test_optimization.py -v 2>&1 | tail -10
```

Expected: `1 passed`

- [ ] **Step 5: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: simulated annealing Cpk optimization module"
```

---

### Task 4: API 端点

**文件:**
- Modify: `src/process_opt/api/app.py` — 在 `if analysis_service is not None:` 块末尾追加 2 个端点

- [ ] **Step 1: 在 app.py 末尾添加端点**

在 `dataset_query_route` 定义之后、`recommendation_submit_route` 之前追加:

```python
@app.post("/api/v1/analysis/pareto")
async def pareto_route(body: ParetoRequest) -> list[ParetoItem]:
    from process_opt.analysis.excel import get_dataset
    from process_opt.analysis.pareto import compute_pareto
    ds = get_dataset(body.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found or expired")
    return compute_pareto(ds, body.field_y)


@app.post("/api/v1/analysis/optimize")
async def optimize_route(body: OptimizationConfig) -> OptimizationResult:
    from process_opt.analysis.excel import get_dataset
    from process_opt.analysis.optimization import run_optimization
    ds = get_dataset(body.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found or expired")
    return run_optimization(ds, body)
```

并在文件顶部的导入块中添加新模型的引用:

```python
from process_opt.analysis.schemas import (
    ...
    ParetoItem,         # 新增
    ParetoRequest,      # 新增
    OptimizationConfig, # 新增
    OptimizationResult, # 新增
)
```

- [ ] **Step 2: 验证导入**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -c "
from process_opt.api.app import create_app
print('OK: app module imports successfully')
"
```

Expected: `OK: app module imports successfully`

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: add pareto and optimize API endpoints"
```

---

### Task 5: 前端 API 客户端扩展

**文件:**
- Modify: `web/src/api/analysis.ts` — 新增 2 个函数 + 类型定义

- [ ] **Step 1: 在 analysis.ts 末尾追加类型和函数**

```typescript
// 在文件末尾追加

export interface ParetoItem {
  field: string
  coefficient: number
  contribution_pct: number
  cumulative_pct: number
  strength: string
}

export interface OptimizationConfig {
  dataset_id: string
  target_field: string
  usl: number
  lsl: number
  target_value: number
  target_cpk: number
  key_factors: string[]
  step_size: number
  max_iterations?: number
}

export interface OptimizationResult {
  initial_cpk: number
  optimized_cpk: number
  convergence: { iteration: number; cpk_value: number }[]
  recommended_params: Record<string, number>
  parameter_adjustments: Record<string, { from: number; to: number; delta: number }>
  target_field: string
}

export function computePareto(data: { dataset_id: string; field_y: string }): Promise<ParetoItem[]> {
  return client.post('/analysis/pareto', data).then((r) => r.data)
}

export function optimizeCpk(data: OptimizationConfig): Promise<OptimizationResult> {
  return client.post('/analysis/optimize', data).then((r) => r.data)
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: add pareto and optimize API client functions"
```

---

### Task 6: ParetoChart.vue 组件

**文件:**
- Create: `web/src/components/ParetoChart.vue`

- [ ] **Step 1: 创建 ParetoChart.vue**

```vue
<template>
  <div class="pareto-chart">
    <div v-if="!autoMode" class="pareto-form">
      <el-form inline>
        <el-form-item label="目标 Y">
          <el-select v-model="targetField" style="width: 180px">
            <el-option v-for="f in targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper" v-loading="loading">
      <div v-if="items.length" ref="chartRef" class="pareto-chart-el" />
      <div v-if="items.length" class="pareto-insights">
        <div class="insight-card">
          <div class="insight-label">80/20 分析</div>
          <div class="insight-value">{{ topN }} 个因子贡献 <strong>{{ topContrib }}%</strong></div>
        </div>
        <div class="insight-card">
          <div class="insight-label">推荐优化因子</div>
          <div class="insight-tags">
            <el-tag v-for="item in topFactors" :key="item.field" :type="tagType(item.strength)" size="small">
              {{ item.field }} ({{ item.coefficient }})
            </el-tag>
          </div>
        </div>
      </div>
      <el-empty v-if="!items.length && !loading" description="选择目标后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { computePareto, type ParetoItem } from '@/api/analysis'
import * as echarts from 'echarts'

const props = defineProps<{
  datasetId: string
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const targetField = ref('')
const items = ref<ParetoItem[]>([])
const chartRef = ref<HTMLDivElement>()

const topFactors = computed(() => items.value.slice(0, 3))
const topN = computed(() => topFactors.value.length)
const topContrib = computed(() => {
  if (!items.value.length) return 0
  return items.value.slice(0, 3).reduce((s, i) => s + i.contribution_pct, 0).toFixed(1)
})

function tagType(strength: string): 'danger' | 'warning' | 'info' | '' {
  if (strength === 'strong') return 'danger'
  if (strength === 'medium') return 'warning'
  if (strength === 'weak') return 'info'
  return ''
}

watch(() => props.autoMode, (v) => { if (v) autoCompute() }, { immediate: true })
watch(() => [props.datasetId, props.targetFields.length], () => {
  if (props.autoMode) autoCompute()
})

async function autoCompute() {
  if (!props.datasetId || !props.targetFields.length) return
  targetField.value = props.targetFields[0]
  await handleCompute()
}

async function handleCompute() {
  if (!targetField.value) return
  loading.value = true
  try {
    items.value = await computePareto({
      dataset_id: props.datasetId,
      field_y: targetField.value,
    })
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !items.value.length) return
  const chart = echarts.init(chartRef.value)
  const names = items.value.map(i => i.field)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const item = items.value[idx]
        return `<strong>${item.field}</strong><br/>
          |r| = ${item.coefficient}<br/>
          贡献率: ${item.contribution_pct}%<br/>
          累计: ${item.cumulative_pct}%<br/>
          强度: ${item.strength}`
      },
    },
    grid: { left: 60, right: 60, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { rotate: 30, fontSize: 11, interval: 0 },
    },
    yAxis: [
      {
        type: 'value',
        name: '贡献率 %',
        nameTextStyle: { fontSize: 11 },
        max: 100,
        axisLabel: { fontSize: 11 },
      },
      {
        type: 'value',
        name: '累计 %',
        nameTextStyle: { fontSize: 11 },
        max: 100,
        axisLabel: { fontSize: 11 },
      },
    ],
    series: [
      {
        name: '贡献率',
        type: 'bar',
        data: items.value.map(i => i.contribution_pct),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3b82f6' },
            { offset: 1, color: '#1d4ed8' },
          ]),
        },
      },
      {
        name: '累计贡献率',
        type: 'line',
        yAxisIndex: 1,
        data: items.value.map(i => i.cumulative_pct),
        lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
        itemStyle: { color: '#ef4444' },
        markLine: {
          silent: true,
          data: [{ yAxis: 80, label: { formatter: '80% 参考线', fontSize: 10 } }],
          lineStyle: { color: '#f97316', type: 'dashed' },
        },
      },
    ],
  })
  window.addEventListener('resize', () => chart.resize())
}
</script>

<style scoped>
.pareto-form { margin-bottom: 12px; }
.chart-wrapper { min-height: 200px; }
.pareto-chart-el { width: 100%; height: 320px; }
.pareto-insights { display: flex; gap: 12px; margin-top: 12px; }
.insight-card {
  flex: 1; background: var(--el-bg-color);
  border-radius: 6px; padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
}
.insight-label { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.insight-value { font-size: 13px; color: var(--el-text-color-primary); }
.insight-value strong { color: var(--el-color-warning); }
.insight-tags { display: flex; gap: 4px; flex-wrap: wrap; }
</style>
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: add ParetoChart component"
```

---

### Task 7: CpkOptimizer.vue 组件

**文件:**
- Create: `web/src/components/CpkOptimizer.vue`

- [ ] **Step 1: 创建 CpkOptimizer.vue**

```vue
<template>
  <div class="cpk-optimizer">
    <!-- Config Form -->
    <div class="opt-config">
      <el-form label-width="100px" size="small">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="目标 Cpk">
              <el-input-number v-model="targetCpk" :min="0.5" :max="3" :step="0.1" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="USL">
              <el-input-number v-model="uslVal" :min="0" :step="1" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="LSL">
              <el-input-number v-model="lslVal" :min="0" :step="1" style="width: 140px" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="目标值">
              <el-input-number v-model="targetVal" :min="0" :step="0.5" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="搜索步长">
              <el-slider v-model="stepSize" :min="0.1" :max="5" :step="0.1" style="width: 160px" />
              <span class="slider-val">{{ stepSize }}</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关键因子">
          <el-checkbox-group v-model="selectedFactors">
            <el-checkbox v-for="f in featureFields" :key="f" :label="f" :value="f" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleOptimize" :loading="loading" :disabled="!selectedFactors.length">
            <el-icon style="margin-right: 4px;"><Aim /></el-icon> 开始优化
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Results -->
    <div v-if="result" class="opt-results">
      <!-- Before/After comparison -->
      <div class="cpk-comparison">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never">
              <div class="cpk-label">优化前 Cpk</div>
              <div class="cpk-value initial">{{ result.initial_cpk }}</div>
              <div class="cpk-status" :class="cpkStatus(result.initial_cpk)">{{ cpkStatusText(result.initial_cpk) }}</div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never">
              <div class="cpk-label">优化后 Cpk</div>
              <div class="cpk-value optimized">{{ result.optimized_cpk }}</div>
              <div class="cpk-status" :class="cpkStatus(result.optimized_cpk)">{{ cpkStatusText(result.optimized_cpk) }}</div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- Convergence Chart -->
      <div class="convergence-section">
        <h4 class="section-title">收敛轨迹</h4>
        <div ref="convChartRef" class="conv-chart" />
      </div>

      <!-- Parameter Adjustments -->
      <div class="adjustments-section">
        <h4 class="section-title">参数调整建议</h4>
        <el-table :data="adjustmentRows" border size="small" style="width: 100%">
          <el-table-column label="参数" prop="field" width="120" />
          <el-table-column label="当前值" prop="from" width="100" />
          <el-table-column label="优化值" prop="to" width="100" />
          <el-table-column label="调整量" prop="delta" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.delta > 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)' }">
                {{ row.delta > 0 ? '+' : '' }}{{ row.delta }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="方向" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.delta > 0" type="danger" size="small">↑ 上调</el-tag>
              <el-tag v-else-if="row.delta < 0" type="success" size="small">↓ 下调</el-tag>
              <el-tag v-else type="info" size="small">—</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Submit -->
      <div class="submit-section">
        <el-button type="primary" @click="handleSubmit" size="default">
          <el-icon style="margin-right: 4px;"><Upload /></el-icon> 提交到参数管理
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { optimizeCpk, submitRecommendation, type OptimizationResult } from '@/api/analysis'
import * as echarts from 'echarts'
import { Aim, Upload } from '@element-plus/icons-vue'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetField: string
  usl: number
  lsl: number
  targetValue: number
}>()

const loading = ref(false)
const result = ref<OptimizationResult | null>(null)
const convChartRef = ref<HTMLDivElement>()

const targetCpk = ref(1.33)
const uslVal = ref(props.usl)
const lslVal = ref(props.lsl)
const targetVal = ref(props.targetValue)
const stepSize = ref(1.0)
const selectedFactors = ref<string[]>([])

watch(() => props.featureFields, (fields) => {
  if (!selectedFactors.value.length) {
    selectedFactors.value = fields.slice(0, 3)
  }
}, { immediate: true })

watch(() => props.usl, (v) => { uslVal.value = v })
watch(() => props.lsl, (v) => { lslVal.value = v })
watch(() => props.targetValue, (v) => { targetVal.value = v })

const adjustmentRows = computed(() => {
  if (!result.value) return []
  return Object.entries(result.value.parameter_adjustments).map(([field, adj]) => ({
    field, ...adj,
  }))
})

function cpkStatus(cpk: number): string {
  if (cpk >= 1.33) return 'normal'
  if (cpk >= 1.0) return 'marginal'
  return 'abnormal'
}

function cpkStatusText(cpk: number): string {
  if (cpk >= 1.33) return '达标'
  if (cpk >= 1.0) return '边缘'
  return '异常'
}

async function handleOptimize() {
  if (!selectedFactors.value.length) return
  loading.value = true
  result.value = null
  try {
    result.value = await optimizeCpk({
      dataset_id: props.datasetId,
      target_field: props.targetField,
      usl: uslVal.value,
      lsl: lslVal.value,
      target_value: targetVal.value,
      target_cpk: targetCpk.value,
      key_factors: selectedFactors.value,
      step_size: stepSize.value,
    })
    await nextTick()
    renderConvergence()
  } finally {
    loading.value = false
  }
}

function renderConvergence() {
  if (!convChartRef.value || !result.value) return
  const chart = echarts.init(convChartRef.value)
  const data = result.value.convergence

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const d = params[0]
        return `迭代: ${d.dataIndex * 50}<br/>Cpk: ${d.value}`
      },
    },
    grid: { left: 50, right: 30, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.iteration),
      name: '迭代次数',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'Cpk',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'line',
      data: data.map(d => d.cpk_value),
      smooth: true,
      lineStyle: { color: '#6366f1', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99,102,241,0.3)' },
          { offset: 1, color: 'rgba(99,102,241,0.05)' },
        ]),
      },
      markLine: {
        silent: true,
        data: [{ yAxis: targetCpk.value, label: { formatter: `目标 Cpk = ${targetCpk.value}`, fontSize: 10 } }],
        lineStyle: { color: '#10b981', type: 'dashed' },
      },
    }],
  })
  window.addEventListener('resize', () => chart.resize())
}

async function handleSubmit() {
  if (!result.value) return
  await submitRecommendation({
    device_type: 'imported',
    parameters: result.value.recommended_params,
  })
}
</script>

<style scoped>
.opt-config { margin-bottom: 16px; }
.slider-val { margin-left: 8px; font-family: 'Fira Code', monospace; font-size: 12px; color: var(--el-text-color-secondary); }

.opt-results { margin-top: 16px; }

.cpk-comparison { margin-bottom: 20px; }
.cpk-label { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.cpk-value { font-family: 'Fira Code', monospace; font-size: 28px; font-weight: 700; }
.cpk-value.initial { color: var(--el-color-danger); }
.cpk-value.optimized { color: var(--el-color-success); }
.cpk-status { font-size: 12px; margin-top: 4px; }
.cpk-status.normal { color: var(--el-color-success); }
.cpk-status.marginal { color: var(--el-color-warning); }
.cpk-status.abnormal { color: var(--el-color-danger); }

.section-title { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--el-text-color-primary); }
.conv-chart { width: 100%; height: 240px; margin-bottom: 20px; }
.adjustments-section { margin-bottom: 16px; }
.submit-section { margin-top: 12px; }
</style>
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: add CpkOptimizer component"
```

---

### Task 8: CorrelationChart.vue 增强

**文件:**
- Modify: `web/src/components/CorrelationChart.vue` — 增强配色和图例

- [ ] **Step 1: 增强 visualMap 配色和图例**

修改 `buildMatrix` 函数调用 `renderHeatmap` 替换为:

```typescript
function renderHeatmap(xLabels: string[], yLabels: string[], items: { x: string; y: string; value: number }[]) {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  const heatData = items.map(i => [xLabels.indexOf(i.x), yLabels.indexOf(i.y), i.value])
  chart.setOption({
    tooltip: {
      formatter: (p: any) => {
        const d = items[p.dataIndex]
        const absR = Math.abs(d.value)
        let strength = '极弱'
        if (absR > 0.7) strength = '强'
        else if (absR > 0.5) strength = '中'
        else if (absR > 0.3) strength = '弱'
        return `${d.x} × ${d.y}<br/>r = ${d.value.toFixed(4)} (${strength})`
      },
    },
    grid: { left: 120, right: 60, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { rotate: 30, fontSize: 11, interval: 0 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      axisLabel: { fontSize: 11 },
      splitArea: { show: true },
    },
    visualMap: {
      min: -1,
      max: 1,
      inRange: {
        color: ['#3b82f6', '#eab308', '#f97316', '#ef4444'],
      },
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: {
        show: true,
        formatter: (p: any) => heatData[p.dataIndex][2].toFixed(2),
        fontSize: 10,
        color: '#333',
      },
      emphasis: {
        itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' },
      },
    }],
  })
  window.addEventListener('resize', () => chart.resize())
}
```

同时更新 `coeffColor` 函数:

```typescript
function coeffColor(r: number): string {
  const absR = Math.abs(r)
  if (absR > 0.7) return '#ef4444'
  if (absR > 0.5) return '#f97316'
  if (absR > 0.3) return '#eab308'
  return '#3b82f6'
}
```

将 visualMap 颜色数组从 `['#3b82f6', '#ffffff', '#ef4444']` 改为 `['#3b82f6', '#eab308', '#f97316', '#ef4444']`，表示极弱→弱→中→强。

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: enhance correlation heatmap with strength-based colors and legend"
```

---

### Task 9: AnalysisView.vue 集成

**文件:**
- Modify: `web/src/views/AnalysisView.vue` — 配置步骤增强 + 报告导航扩展 + 新 sections

- [ ] **Step 1: 新增响应式变量**

在 `const missingCount = ref(0)` 之后添加:

```typescript
const cfgTargetField = ref('')
const cfgUsl = ref(100)
const cfgLsl = ref(0)
const cfgTargetValue = ref(50)
```

- [ ] **Step 2: 扩展导入**

在 imports 块中追加:

```typescript
import ParetoChart from '@/components/ParetoChart.vue'
import CpkOptimizer from '@/components/CpkOptimizer.vue'
import { Histogram, Aim } from '@element-plus/icons-vue'
```

- [ ] **Step 3: 扩展 navItems**

```typescript
// 在 report-correlation 和 report-regression 之间插入
const navItems = [
  { id: 'report-overview', icon: Document, label: '数据概览', color: '#3B82F6' },
  { id: 'report-profile', icon: DataAnalysis, label: '字段分析', color: '#8B5CF6' },
  { id: 'report-correlation', icon: Link, label: '相关性', color: '#10B981' },
  { id: 'report-pareto', icon: Histogram, label: '帕累托图', color: '#F59E0B' },
  { id: 'report-cpk', icon: Aim, label: 'Cpk 优化', color: '#EF4444' },
  { id: 'report-regression', icon: TrendCharts, label: '回归', color: '#F59E0B' },
  { id: 'report-recommendation', icon: MagicStick, label: '推荐', color: '#EC4899' },
]
```

- [ ] **Step 4: 配置步骤新增规格限表单**

在 `goConfig` 函数中，在 `selectedTargets` 赋值之后添加:

```typescript
function goConfig() {
  state.value = 'config'
  selectedFeatures.value = previewFields.value.features.map((f) => f.name)
  selectedTargets.value = previewFields.value.targets.filter((f) => f.type === 'numeric').map((f) => f.name)
  // 初始化 Cpk 配置
  if (selectedTargets.value.length) {
    cfgTargetField.value = selectedTargets.value[0]
  }
}
```

在模板的 Step 3 (config) 区域, `<FieldCheckboxGrid>` 之后、`<div class="config-actions">` 之前追加:

```vue
<div class="spec-section">
  <h4 class="section-subtitle">Cpk 优化规格限</h4>
  <el-form inline size="small">
    <el-form-item label="目标字段">
      <el-select v-model="cfgTargetField" style="width: 160px">
        <el-option v-for="f in selectedTargets" :key="f" :label="f" :value="f" />
      </el-select>
    </el-form-item>
    <el-form-item label="USL">
      <el-input-number v-model="cfgUsl" :min="0" :step="1" style="width: 120px" />
    </el-form-item>
    <el-form-item label="LSL">
      <el-input-number v-model="cfgLsl" :min="0" :step="1" style="width: 120px" />
    </el-form-item>
    <el-form-item label="目标值">
      <el-input-number v-model="cfgTargetValue" :min="0" :step="0.5" style="width: 120px" />
    </el-form-item>
  </el-form>
</div>
```

- [ ] **Step 5: 报告新增两个 section**

在 `<section id="report-correlation">` 和 `<section id="report-regression">` 之间插入:

```vue
<section id="report-pareto">
  <h3><el-icon :size="16" color="#F59E0B"><Histogram /></el-icon> 帕累托图</h3>
  <ParetoChart
    :dataset-id="datasetId!"
    :target-fields="selectedTargets"
    :auto-mode="true"
  />
</section>
<section id="report-cpk">
  <h3><el-icon :size="16" color="#EF4444"><Aim /></el-icon> Cpk 优化</h3>
  <CpkOptimizer
    :dataset-id="datasetId!"
    :feature-fields="selectedFeatures"
    :target-field="cfgTargetField"
    :usl="cfgUsl"
    :lsl="cfgLsl"
    :target-value="cfgTargetValue"
  />
</section>
```

- [ ] **Step 6: 验证 TypeScript 编译**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1 | tail -10
```

Expected: 无类型错误

- [ ] **Step 7: 提交**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "feat: integrate pareto and cpk optimization into AnalysisView"
```

---

### Task 10: 运行完整测试套件

- [ ] **Step 1: 运行所有后端测试**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/analysis/ -v 2>&1 | tail -20
```

Expected: 所有测试通过

- [ ] **Step 2: 运行 TypeScript 检查**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit 2>&1
```

Expected: 无输出（无错误）

- [ ] **Step 3: 提交最终**

```bash
cd /Users/zhongding/dev/thingsboard && git add -A && git commit -m "chore: final verification commit"
```
