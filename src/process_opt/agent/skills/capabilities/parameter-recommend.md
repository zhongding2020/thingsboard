---
name: parameter-recommend
display_name: 参数推荐
type: capability
description: 网格搜索/LHS 搜索最优参数组合，附带规则校验和预测质量值
triggers:
  - 推荐
  - 优化
  - 最优
  - 改进
  - 提高
  - 降低
  - 改善
tools:
  - recommend_params
  - optimize_parameters
  - run_regression
  - build_dataset
---

## 功能

基于历史数据和回归模型，搜索满足工艺规则约束的最优参数组合。

## 使用场景

- 用户要提升某个质量指标
- 用户要降低不良率
- 用户要在多个约束下寻找最优参数

## 分析步骤

1. 确认优化目标（指标名称 + 方向：maximize/minimize/target）
2. 如果有约束条件（如"不能超过某温度"），先确认
3. 用 `build_dataset` 构建训练数据集
4. 用 `run_regression` 建立预测模型
5. 用 `recommend_params` 或 `optimize_parameters` 搜索最优参数
6. 校验推荐参数是否符合工艺规则
7. 用 Markdown 表格输出推荐参数 + 预测值 + 置信度 + 与当前参数的对比

## 输出格式

| 参数 | 当前值 | 推荐值 | 单位 | 预测指标 | 提升幅度 |
|------|--------|--------|------|----------|----------|
