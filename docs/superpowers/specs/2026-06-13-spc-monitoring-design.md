# SPC 六合一图监控 — 设计文档

## 概述

在现有工艺参数分析平台中新增独立「SPC 监控」板块，提供统计过程控制(Statistical Process Control)六合一图，支持实时监控模式。

## 架构

### 后端

**新增文件**: `src/process_opt/analysis/spc.py`

SPC 计算模块，包含以下函数：

| 函数 | 输出 | 统计方法 |
|---|---|---|
| `compute_imr(values)` | I 单值(均值/控制限/告警点), MR 移动极差(均值/上限) | `numpy`: mean, std, diff |
| `compute_capability(values, usl, lsl, target)` | Cp, Cpk, Pp, Ppk | 标准六西格玛公式 |
| `compute_p_chart(results)` | 按时间窗口的不合格品率, 控制上限 | 二项分布 p-chart |
| `compute_histogram(values, bin_count=20)` | 分箱数据, 正态拟合曲线 | `numpy`: histogram, `scipy.stats.norm` |
| `compute_summary(values)` | N, mean, std, min, max, p_value | `scipy.stats.normaltest` |
| `compute_overview(device_id)` | 该设备所有参数的概述(Cpk/上下限/状态等) | 遍历参数字段, 调用 capability |

**控制限计算**: I 图 CL=mean, UCL=mean+3σ, LCL=mean-3σ; MR 图 CL=MR̄, UCL=D4×MR̄ (D4=3.267 for n=2).

**状态判定规则**: Cpk ≥ 1.33 正常, 1.0 ≤ Cpk < 1.33 边缘, Cpk < 1.0 异常.

### 新增 Schema

```python
class SpcRequest(BaseModel):
    device_id: str
    field: str | None = None          # 空时返回 overview
    usl: float | None = None          # 空则自动 mean+3σ
    lsl: float | None = None
    target: float | None = None
    since: datetime | None = None     # 监控模式增量查询

class SpcResult(BaseModel):
    overview: list[ParamOverview]     # 设备所有参数概览
    i_chart: IChart | None            # 当前选中参数
    mr_chart: MrChart | None
    histogram: Histogram | None
    capability: Capability | None
    p_chart: PChart | None
    summary: SummaryStats | None
```

### API 路由

```
POST /api/v1/analysis/spc
```

- 如果 `field` 为空: 只返回 `overview` (所有参数概览)
- 如果 `field` 有值: 返回 `overview` + 该参数完整6合图
- `since` 参数启用增量模式: 只返回 since 之后的新数据点 + 重新计算的控制限
- 内部通过 `DatasetBuilder` 从 `analysis_view` 获取数据

需要更新 `AnalysisServiceProxy` 和 `service.py` 挂载新方法。

### 前端

**新增文件**:

```
web/src/views/SpcView.vue              # SPC 主页面
web/src/api/spc.ts                      # API调用
```

**6合图布局结构** (SpcView.vue 内联渲染):

```
┌────────────────────────────────────────────┐
│  设备选择  │  时间范围  │  [查询]  [●启动监控] │
├────────────────────────────────────────────┤
│  参数概览表格 (el-table, 点击选中行切换)       │
│  ┌──────┬──────┬──────┬────┬────┬──────┐   │
│  │ 参数  │ USL  │ LSL  │ N  │Cpk │ 状态  │   │
│  ├──────┼──────┼──────┼────┼────┼──────┤   │
│  │ temp │ 285  │ 149  │ 295│1.15│ ●正常 │   │
│  │ conv │ 74.5 │ 25.5 │ 295│0.82│ ●边缘 │   │
│  └──────┴──────┴──────┴────┴────┴──────┘   │
│  状态: Cpk≥1.33正常 · 1.0≤Cpk<1.33边缘 · <1.0异常 │
├────────────────┬───────────────────────────┤
│  ① I 单值图     │  ② MR 移动极差图           │
│  (ECharts)      │  (ECharts)                │
├────────────────┼───────────────────────────┤
│  ③ 直方图+曲线   │  ④ P 不合格品率图          │
│  (ECharts)      │  (ECharts)                │
├────────────────┼───────────────────────────┤
│  ⑤ 过程能力卡片   │  ⑥ 数据摘要 + 规格限编辑   │
│  Cp/Cpk/Pp/Ppk  │  N/Mean/Std + USL/LSL 输入 │
└────────────────┴───────────────────────────┘
```

**交互逻辑**:

1. 选择设备后点「查询」→ 加载参数概览表 + 默认选中第一行 → 渲染该参数6合图
2. 点击概览表行 → 高亮切换 → 下方6合图更新为该参数
3. 启动监控 → 按设定间隔(5s/10s/30s)轮询 → 概览表和图表增量更新 → 新超限数据闪烁提示
4. 规格限编辑 → 直接在摘要区修改 USL/LSL → 直方图和能力指数实时重算

**已安装依赖**: `echarts@5.5.0` + `vue-echarts@6.6.9`

### 路由与菜单

```typescript
// router/index.ts
{ path: 'spc', component: () => import('@/views/SpcView.vue') },

// AppLayout.vue 侧边栏
<el-menu-item index="/spc">
  <el-icon><TrendCharts /></el-icon>
  <span>SPC监控</span>
</el-menu-item>
```

### 监控模式

| 状态 | 行为 |
|------|------|
| 停止 | 手动查询, 静态图表 |
| 监控中 | setInterval 轮询, 增量数据追加, 倒计时显示, 异常闪烁 |
| 新数据异常 | I 图/MR 图/P 图上超限点闪烁标记, 概览表状态列更新 |
| 停止监控 | clearInterval, 保留当前数据为静态快照 |

### 测试

- 后端: `tests/analysis/test_spc.py` — i-mr计算, capability计算, p-chart计算
- 前端: 无独立测试, 依赖 vue-tsc 类型检查
- 集成: 通过 `POST /api/v1/analysis/spc` 端到端验证

## 实现顺序

1. 后端: schemas + spc.py 计算模块
2. 后端: service.py + main.py 挂载
3. 后端: app.py 路由 + 测试
4. 前端: api/spc.ts + SpcView.vue 页面框架
5. 前端: 6个ECharts子组件
6. 前端: 监控模式逻辑
7. 前端: 路由 + 侧边栏菜单
8. Docker 构建 & 端到端验证
