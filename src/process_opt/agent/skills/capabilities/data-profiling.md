---
name: data-profiling
display_name: 数据画像
type: capability
description: 统计数据分布（均值、标准差、极值、异常值检测）
triggers:
  - 画像
  - 概况
  - 统计
  - 分布
  - 异常值
  - 趋势
tools:
  - profile_data
  - query_records
  - get_stats
---

## 功能

对指定设备和时间范围的工艺数据进行统计分析，检测异常值。

## 使用场景

- 用户要了解设备运行概况
- 用户要查看数据分布
- 用户要识别异常数据点

## 分析步骤

1. 用 `query_records` 或 `get_stats` 获取数据
2. 用 `profile_data` 执行统计画像
3. 用 Markdown 表格输出统计量

## 输出格式

| 参数 | 均值 | 标准差 | 最小值 | 最大值 | 异常值数 |
|------|------|--------|--------|--------|----------|
