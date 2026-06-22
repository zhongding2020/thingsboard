---
name: reflow_soldering
display_name: 回流焊
type: process
description: 回流焊（Reflow Soldering）工艺，通过预热、保温、回流和冷却四个温区实现SMT焊接。关键参数包括各温区温度、链速和气氛控制。
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
| preheat_temp | 预热温度 | °C | 140–180 | 150–170 | critical |
| soak_temp | 保温温度 | °C | 170–200 | 180–195 | critical |
| reflow_peak_temp | 回流峰值温度 | °C | 220–250 | 235–245 | critical |
| conveyor_speed | 链速 | cm/min | 40–120 | 60–90 | important |
| nitrogen_flow | 氮气流量 | L/min | 0–30 | 10–20 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| solder_joint_strength | 焊点强度 | N | 15 | — |
| void_rate | 空洞率 | % | — | 25 |
| wetting_angle | 润湿角 | ° | — | 30 |

## 规则约束

- [hard] reflow_peak_temp > 250 → 峰值温度过高会损坏元器件
- [hard] preheat_temp < 130 → 预热不足会导致热冲击
- [soft] conveyor_speed > 100 → 链速过快可能导致冷焊

## 分析提示

- 焊点强度主要受回流峰值温度和保温时间影响
- 空洞率与预热温度曲线和助焊剂活化相关
- 润湿角与峰值温度和氮气流量相关
