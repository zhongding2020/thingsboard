---
name: powder_coating
display_name: 粉末涂装
type: process
description: 粉末涂装工艺，通过静电喷涂将粉末涂料附着在工件表面，经烘烤固化形成涂层。关键参数包括电压、气压、烘烤温度和链速。
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
| electrostatic_voltage | 静电电压 | kV | 40–100 | 60–80 | critical |
| atomizing_pressure | 雾化气压 | MPa | 0.1–0.5 | 0.2–0.35 | critical |
| curing_temp | 固化温度 | °C | 160–220 | 180–200 | critical |
| curing_time | 固化时间 | min | 10–30 | 15–20 | important |
| conveyor_speed | 链速 | m/min | 1.0–4.0 | 2.0–3.0 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| coating_thickness | 涂层厚度 | μm | 60 | 100 |
| adhesion | 附着力 | grade | 0 | 1 |
| gloss | 光泽度 | GU | 80 | 95 |

## 规则约束

- [hard] curing_temp > 220 → 固化温度过高会导致涂层变色
- [hard] curing_time < 10 → 固化时间不足会导致涂层固化不完全
- [soft] electrostatic_voltage < 45 → 静电电压过低会导致上粉率下降

## 分析提示

- 涂层厚度主要受静电电压和雾化气压影响
- 附着力与固化温度和固化时间高度相关
- 光泽度受固化温度曲线和粉末粒度影响
