---
name: adhesive_curing
display_name: 点胶固化
type: process
description: 点胶固化工艺，包含点胶（dispensing）和固化（curing）两个步骤。点胶步骤控制胶量、压力；固化步骤控制温度和时间。
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
| cure_temp | 固化温度 | °C | 80–180 | 120–150 | critical |
| cure_time | 固化时间 | min | 10–120 | 30–60 | critical |
| glue_amount | 胶量 | mg | 5–50 | 15–30 | critical |
| dispense_pressure | 点胶压力 | kPa | 50–300 | 100–200 | important |
| ambient_humidity | 环境湿度 | %RH | 20–80 | 30–60 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| shear_strength | 剪切强度 | kgf/cm² | 80 | — |
| bubble_rate | 气泡率 | % | — | 5.0 |
| glue_overflow | 胶水溢出量 | mm | — | 1.0 |

## 规则约束

- [hard] cure_temp > 180 → 固化温度不得超过180°C，否则会导致胶水老化
- [hard] cure_time < 10 → 固化时间不得少于10分钟
- [soft] cure_temp > 150 and cure_time < 20 → 高温短时间可能导致固化不均匀
- [soft] glue_amount > 40 → 胶量偏大可能导致溢出，建议控制在15-30mg
- [dependency] cure_temp increase → 温度每升高10°C，固化时间可减少约5分钟

## 分析提示

- 优先分析固化温度、固化时间、胶量与剪切强度的相关性
- 如果气泡率高，检查固化温度和时间组合
- 如果胶水溢出量大，检查胶量和点胶压力
