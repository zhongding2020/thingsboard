---
name: welding
display_name: 焊接
type: process
description: 金属焊接工艺，通过加热或加压使工件连接。关键参数包括电流、电压、焊接速度和保护气体流量。
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
| welding_current | 焊接电流 | A | 80–300 | 150–250 | critical |
| arc_voltage | 电弧电压 | V | 16–35 | 22–30 | critical |
| welding_speed | 焊接速度 | cm/min | 15–80 | 30–50 | important |
| gas_flow | 保护气流量 | L/min | 8–25 | 12–20 | important |
| wire_feed_rate | 送丝速度 | m/min | 2–12 | 5–9 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| tensile_strength | 抗拉强度 | MPa | 400 | — |
| weld_penetration | 熔深 | mm | 2.0 | 5.0 |
| porosity_level | 气孔等级 | grade | — | 2 |

## 规则约束

- [hard] welding_current > 300 → 电流过大会烧穿工件
- [hard] welding_speed < 15 → 速度过低会导致过热和变形
- [soft] gas_flow < 10 → 保护气不足会产生气孔

## 分析提示

- 抗拉强度与焊接电流和焊接速度高度相关
- 熔深受焊接电流和电弧电压影响大
- 气孔等级与保护气流量和焊接速度相关
