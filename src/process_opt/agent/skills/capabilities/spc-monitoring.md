---
name: spc-monitoring
display_name: SPC 监控
type: capability
description: 统计过程控制（I-MR 控制图、Cp/Cpk 过程能力分析）
triggers:
  - spc
  - 控制图
  - 过程能力
  - cpk
  - cp
  - 监控
tools:
  - run_spc
  - query_records
  - get_stats
---

## 功能

对指定设备或产线执行 SPC 监控，生成 I-MR 控制图和过程能力指数（Cp/Cpk）。

## 使用场景

- 用户询问设备过程是否稳定
- 用户要求查看控制图
- 用户询问 Cp/Cpk 值

## 分析步骤

1. 先用 `query_records` 获取该设备最近的数据
2. 用 `run_spc` 对关键参数执行 SPC 分析
3. 判断：Cp < 1.0 → 能力不足；1.0 ≤ Cp < 1.33 → 能力一般；Cp ≥ 1.33 → 能力充分
4. 用 Markdown 表格输出 SPC 结论，含控制图数据

## 输出格式

| 参数 | 均值 | UCL | LCL | Cp | Cpk | 判定 |
|------|------|-----|-----|-----|-----|------|
