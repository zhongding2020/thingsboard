---
name: line-monitoring
display_name: 产线监控
type: capability
description: 产线级 SPC 总览，多设备状态汇总
triggers:
  - 产线
  - 生产线
  - 设备状态
  - 线体
tools:
  - list_production_lines
  - get_production_line
  - list_registered_devices
  - monitor_production_line
---

## 功能

对产线进行全景监控，汇总产线下所有设备的 SPC 状态。

## 使用场景

- 用户要查看产线整体状况
- 用户要对比产线内设备的性能差异
- 用户要识别产线瓶颈

## 分析步骤

1. 用 `list_production_lines` 确定目标产线
2. 用 `get_production_line` 获取产线详情
3. 用 `monitor_production_line` 执行产线级 SPC
4. 用 Markdown 表格汇总各设备状态

## 输出格式

| 设备 | 关键参数 | Cp | Cpk | 状态 | 建议 |
|------|----------|-----|-----|------|------|
