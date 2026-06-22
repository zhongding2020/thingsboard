---
name: correlation-analysis
display_name: 相关性分析
type: capability
description: Pearson/Spearman 相关系数、热力图、帕累托分析
triggers:
  - 相关性
  - 相关系数
  - 热力图
  - 帕累托
  - pearson
  - spearman
tools:
  - analyze_correlation
  - analyze_pareto
  - build_dataset
  - preview_dataset
---

## 功能

分析工艺参数与质量指标之间的相关性，输出相关系数矩阵和帕累托排序。

## 使用场景

- 用户要了解哪些参数对质量影响最大
- 用户要查看参数间的共线性
- 用户要做因子筛选

## 分析步骤

1. 先确认数据集（如已上传则用已有 dataset_id，否则用 `build_dataset` 构建）
2. 用 `analyze_correlation` 执行相关性分析（默认 Pearson）
3. 如果参数数量较多（>5），用 `analyze_pareto` 做帕累托排序
4. 用 Markdown 表格输出相关系数矩阵

## 输出格式

| 参数 | 相关系数 | 方向 | 显著性 |
|------|----------|------|--------|
