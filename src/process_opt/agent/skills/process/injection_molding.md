---
name: injection_molding
display_name: 注塑成型
type: process
description: 注塑成型工艺，包含塑化、注射、保压、冷却四个阶段。关键控制参数包括温度、压力、速度和时间。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| melt_temp | 熔体温度 | °C | 180–280 | 220–250 | critical |
| mold_temp | 模具温度 | °C | 40–120 | 60–80 | critical |
| injection_pressure | 注射压力 | MPa | 50–180 | 90–130 | critical |
| holding_pressure | 保压压力 | MPa | 30–120 | 50–80 | important |
| cooling_time | 冷却时间 | s | 5–40 | 15–25 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| weight | 产品重量 | g | 45 | 50 |
| dimension_x | X方向尺寸 | mm | 99.8 | 100.2 |
| warpage | 翘曲量 | mm | — | 0.3 |

## 规则约束

- [hard] melt_temp > 280 → 熔体温度过高会导致材料降解
- [hard] cooling_time < 5 → 冷却时间过短会导致产品变形
- [soft] injection_pressure > 150 → 过高的注射压力可能导致模具磨损

## 分析提示

- 熔体温度、模具温度是影响尺寸精度的主要因素
- 翘曲通常与冷却时间和模具温度相关
