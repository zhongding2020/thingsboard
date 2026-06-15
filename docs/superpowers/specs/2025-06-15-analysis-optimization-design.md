# 关联分析模块优化设计

## 概述

在现有参数调优（Analysis）模块中新增帕累托分析和 Cpk 模拟退火优化功能。保留原有 5 步流程（导入→预览→配置→加载→报告），在报告导航中新增 2 个面板，增强 1 个面板。

---

## 1. 新增后端数据模型

文件: `src/process_opt/analysis/schemas.py`

```python
class ParetoItem(BaseModel):
    field: str
    coefficient: float           # |r| 值
    contribution_pct: float      # 单项贡献率 (%)
    cumulative_pct: float        # 累计贡献率 (%)
    strength: str                # "strong"|"medium"|"weak"|"negligible"

class ParetoRequest(BaseModel):
    dataset_id: str
    field_y: str                 # 目标 Y 字段

class OptimizationConfig(BaseModel):
    dataset_id: str
    target_field: str
    usl: float
    lsl: float
    target_value: float
    target_cpk: float = 1.33
    key_factors: list[str]       # 关键因子（从帕累托选择）
    step_size: float             # 搜索步长
    max_iterations: int = 5000

class OptimizationResult(BaseModel):
    initial_cpk: float
    optimized_cpk: float
    convergence: list[dict[str, float]]  # [{iteration, cpk_value}]
    recommended_params: dict[str, float]
    parameter_adjustments: dict[str, dict[str, float]]  # {因子: {from, to, delta}}
    target_field: str
```

---

## 2. 帕累托图计算

文件: `src/process_opt/analysis/pareto.py` (新)

- 从 dataset 提取所有 X 特征字段
- 对每个 X 字段计算与 `field_y` 的皮尔逊相关系数（复用 `correlation.py` 的 `_extract_arrays` + `scipy.stats.pearsonr`）
- 按 |r| 降序排列
- 计算 total = Σ|r_i|
- 每项: contribution_pct = |r_i| / total * 100, cumulative_pct = 前缀和
- strength: |r| > 0.7 → strong, > 0.5 → medium, > 0.3 → weak, 否则 → negligible

暴露函数: `compute_pareto(dataset: AnalysisDataset, field_y: str) -> list[ParetoItem]`

---

## 3. 模拟退火 Cpk 优化

文件: `src/process_opt/analysis/optimization.py` (新)

### 依赖

- 复用 `regression.py` 的 `_extract_arrays` 提取 X/y 数组
- 使用 `LinearRegression` 拟合模型（与现有 recommendation 一致）

### 目标函数

```
cpk = min((usl - y_pred) / (3 * rmse), (y_pred - lsl) / (3 * rmse))
loss = (target_cpk - cpk)^2          if cpk < target_cpk
       |y_pred - target_value|       if cpk >= target_cpk
```

### 退火流程

1. 初始解 = 各关键因子的当前均值
2. 初始温度 T₀ = 100, 退火率 α = 0.95
3. 每轮迭代:
   - 新解 = 当前解 + uniform(-step_size, +step_size) * (T / T₀)
   - 边界裁剪到 [min_val, max_val]（从 dataset 推断）
   - ΔE = loss(新解) - loss(当前解)
   - if ΔE < 0 → 接受; else → 以 exp(-ΔE/T) 概率接受
   - 记录本轮 Cpk 到 convergence 数组
4. 返回最优解 (loss 最小的解)

暴露函数:
`run_optimization(dataset: AnalysisDataset, config: OptimizationConfig) -> OptimizationResult`

---

## 4. API 端点

文件: `src/process_opt/api/app.py`

在 `if analysis_service is not None:` 块中新增:

### POST /api/v1/analysis/pareto
- 请求体: `ParetoRequest`
- 返回: `list[ParetoItem]`
- 逻辑: 取 dataset → `compute_pareto()`

### POST /api/v1/analysis/optimize
- 请求体: `OptimizationConfig`
- 返回: `OptimizationResult`
- 逻辑: 取 dataset → 拟合回归 → `run_optimization()`

遵循现有风格，直接操作 `excel.get_dataset()`，不经过 service 层。

---

## 5. 前端 API 扩展

文件: `web/src/api/analysis.ts`

新增 2 个函数:

```typescript
export function computePareto(data: ParetoRequest) {
  return client.post('/analysis/pareto', data).then(r => r.data)
}

export function optimizeCpk(data: OptimizationConfig) {
  return client.post('/analysis/optimize', data).then(r => r.data)
}
```

对应 TypeScript 类型定义也在此文件中新增。

---

## 6. 前端组件

### ParetoChart.vue (新)

- props: `datasetId: string`, `targetField: string`, `loading: boolean`
- 自动挂载后调用 `computePareto`
- ECharts 绘制:
  - 柱状图: 从高到低排列，蓝色渐变
  - 折线: 红色虚线，累计贡献率%，右 Y 轴 0-100
  - markLine: 在 80% 处画水平参考线
  - xAxis: 因子名，label 倾斜 45°
  - tooltip: 字段名 / |r| / 单项贡献率 / 累计贡献率 / 强度

### CpkOptimizer.vue (新)

- props: `datasetId`, `featureFields: string[]`, `targetField: string`, `usl: number`, `lsl: number`, `targetValue: number`
- 内部 state:
  - `config`: targetCpk, keyFactors[], stepSize, maxIterations
  - `result`: OptimizationResult | null
  - `loading`: boolean
- 渲染:
  - 配置表单: 目标 Cpk input、因子多选(从帕累托结果预选前3)、步长 slider
  - 操作按钮: 开始优化
  - 结果区 (仅在 result 非空时显示):
    - 对比例: 两个 card (优化前红色、优化后绿色)
    - 收敛轨迹: ECharts 折线图 (Cpk vs 迭代次数 + 目标线)
    - 参数调整表: el-table 显示 参数名 / 原值→优化值 / 调整量
  - 提交按钮: 调用 `submitRecommendation`

### CorrelationChart.vue (增强)

- visualMap 颜色改为四段: `[#3b82f6, #eab308, #f97316, #ef4444]`
- 新增 intensity 图例面板
- tooltip 增加 |r| 强度等级显示

---

## 7. AnalysisView.vue 集成

### 配置步骤增强 (Step 3)

在 `FieldCheckboxGrid` 下方新增规格限配置区域:

- 目标字段下拉 (从 selectedTargets 中选 1 个)
- USL / LSL / 目标值 三个 input

新增响应式变量:
`cfgTargetField`, `cfgUsl`, `cflLsl`, `cfgTargetValue`

### 报告导航扩展

```typescript
const navItems = [
  { id: 'report-overview',      ... },  // 原有
  { id: 'report-profile',       ... },  // 原有
  { id: 'report-correlation',   ... },  // 增强
  { id: 'report-pareto',        icon: Histogram, label: '帕累托图', color: '#F59E0B' },  // 新增
  { id: 'report-cpk',           icon: Aim, label: 'Cpk 优化', color: '#EF4444' },      // 新增
  { id: 'report-regression',    ... },  // 原有
  { id: 'report-recommendation', ... },  // 原有
]
```

### 报告内容

在 `report-correlation` 和 `report-regression` 之间插入 2 个新 section:

```vue
<section id="report-pareto">
  <h3>帕累托图</h3>
  <ParetoChart :datasetId="datasetId!" :targetField="cfgTargetField" />
</section>
<section id="report-cpk">
  <h3>Cpk 优化</h3>
  <CpkOptimizer
    :datasetId="datasetId!"
    :featureFields="selectedFeatures"
    :targetField="cfgTargetField"
    :usl="cfgUsl"
    :lsl="cfgLsl"
    :targetValue="cfgTargetValue"
  />
</section>
```

### goReport 流程

在 `loadingProgress` 后追加帕累托计算步骤。帕累托计算结果传给 `ParetoChart` 和 `CpkOptimizer` 使用。

---

## 8. 文件变更清单

| 文件 | 变更 |
|------|------|
| `src/process_opt/analysis/schemas.py` | +4 模型 |
| `src/process_opt/analysis/pareto.py` | 新建 |
| `src/process_opt/analysis/optimization.py` | 新建 |
| `src/process_opt/api/app.py` | +2 端点 |
| `web/src/api/analysis.ts` | +2 函数 + 类型 |
| `web/src/components/ParetoChart.vue` | 新建 |
| `web/src/components/CpkOptimizer.vue` | 新建 |
| `web/src/components/CorrelationChart.vue` | 增强配色+图例 |
| `web/src/views/AnalysisView.vue` | 配置增强+导航扩展+新 sections |

---

## 9. 不变的部分

- 原有 5 步流程结构不变
- 原有报告面板（概览/字段分析/回归/推荐）不变
- 后端 `recommendation.py`/`correlation.py`/`regression.py` 不动
- 前端原有组件不受影响，纯新增+增强
