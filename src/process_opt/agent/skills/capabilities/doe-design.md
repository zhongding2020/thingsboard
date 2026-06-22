---
name: doe-design
display_name: DOE 实验设计
type: capability
description: 实验设计（全因子、Box-Behnken、中心复合、田口方法）+ ANOVA 方差分析
triggers:
  - doe
  - 实验设计
  - 田口
  - box-behnken
  - 全因子
  - 因子
  - anova
  - 方差分析
tools:
  - design_experiment
  - analyze_experiment
  - build_dataset
---

## 功能

为指定工艺设计 DOE 实验方案，分析实验结果（ANOVA），识别显著因子和最优水平组合。

## 使用场景

- 用户要优化工艺参数但不知道哪些因子关键
- 用户需要系统性的实验方案
- 用户要分析因子间的交互效应

## 分析步骤

1. 确认目标工艺类型和关注的因子（通常从工艺参数表中选择 2-5 个 critical 参数）
2. 根据因子数和需求选择设计类型：2-3 因子 → 全因子，3-5 因子 → Box-Behnken，多因子筛选 → 田口
3. 调用 `design_experiment` 生成实验方案
4. 如果有实验结果数据，调用 `analyze_experiment` 做 ANOVA
5. 用 Markdown 表格展示因子水平表和 ANOVA 结果

## 输出格式

因子水平表 + ANOVA 效应分析 + 显著因子排序
