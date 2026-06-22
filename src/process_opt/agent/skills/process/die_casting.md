---
name: die_casting
display_name: 压铸
type: process
description: 压铸工艺，将熔融金属在高压下注入模具型腔。关键参数包括压射压力、温度、速度和冷却条件。
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
| melt_temp | 合金液温度 | °C | 620–680 | 640–660 | critical |
| die_temp | 模具温度 | °C | 150–250 | 180–220 | critical |
| injection_speed | 压射速度 | m/s | 1.5–6.0 | 3.0–4.5 | critical |
| casting_pressure | 铸造压力 | MPa | 50–120 | 70–90 | important |
| holding_time | 保压时间 | s | 2–10 | 4–7 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| porosity | 孔隙率 | % | — | 2.0 |
| tensile_strength | 抗拉强度 | MPa | 180 | — |
| surface_roughness | 表面粗糙度 | μm | — | 6.3 |

## 规则约束

- [hard] melt_temp > 680 → 合金液温度过高会导致氧化和烧损
- [hard] injection_speed < 1.5 → 压射速度过低会导致充型不足
- [soft] die_temp < 160 → 模具温度偏低可能产生冷隔缺陷

## 分析提示

- 孔隙率与压射速度和铸造压力高度相关
- 抗拉强度受合金液温度和保压时间影响大
- 表面粗糙度主要与模具温度和压射速度相关
