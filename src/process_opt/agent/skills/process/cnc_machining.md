---
name: cnc_machining
display_name: CNC加工
type: process
description: CNC（计算机数控）加工工艺，通过程序控制刀具和工件的相对运动实现精密加工。关键参数包括转速、进给、切深和刀具参数。
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
| spindle_speed | 主轴转速 | rpm | 2000–12000 | 5000–8000 | critical |
| feed_rate | 进给速度 | mm/min | 100–500 | 200–350 | critical |
| cut_depth | 切削深度 | mm | 0.1–3.0 | 0.5–1.5 | important |
| tool_diameter | 刀具直径 | mm | 1–20 | 4–12 | important |
| coolant_flow | 冷却液流量 | L/min | 2–10 | 4–7 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| dimension_tolerance | 尺寸公差 | μm | — | 20 |
| surface_roughness | 表面粗糙度 | Ra | — | 1.6 |
| roundness | 圆度 | μm | — | 10 |

## 规则约束

- [hard] spindle_speed > 12000 → 转速过高会损坏刀具
- [hard] cut_depth > 3.0 → 切削深度过大会导致加工振动
- [soft] feed_rate > 400 → 进给速度过快会降低表面质量

## 分析提示

- 表面粗糙度主要受主轴转速和进给速度影响
- 尺寸公差与刀具直径和切削深度相关
- 圆度受主轴转速和进给比影响
