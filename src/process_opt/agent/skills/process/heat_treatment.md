---
name: heat_treatment
display_name: 热处理
type: process
description: 金属热处理工艺，通过加热、保温和冷却改变金属内部组织结构。关键参数包括加热温度、保温时间、冷却速率和气氛。
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
| austenitizing_temp | 奥氏体化温度 | °C | 800–1050 | 850–950 | critical |
| holding_time | 保温时间 | min | 15–120 | 30–60 | critical |
| quench_rate | 淬火冷却速率 | °C/s | 20–200 | 50–120 | critical |
| tempering_temp | 回火温度 | °C | 150–650 | 200–500 | important |
| carbon_potential | 碳势 | %C | 0.2–1.2 | 0.4–0.8 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| hardness | 硬度 | HRC | 40 | 60 |
| case_depth | 硬化层深度 | mm | 0.5 | 2.0 |
| distortion | 变形量 | mm | — | 0.1 |

## 规则约束

- [hard] austenitizing_temp > 1050 → 温度过高会导致晶粒粗化
- [hard] quench_rate < 20 → 冷却速率不足会影响马氏体转变
- [soft] tempering_temp > 600 → 回火温度过高会过度软化

## 分析提示

- 硬度主要受奥氏体化温度和淬火速率影响
- 硬化层深度与碳势和保温时间相关
- 变形量与淬火速率和工件尺寸相关
