---
name: product-tracing
display_name: 产品追溯
type: capability
description: 按条码追溯完整生产链路（工艺参数 + 质检结果）
triggers:
  - 追溯
  - 条码
  - 链路
  - 产品
tools:
  - trace_product
  - trace_product_full
---

## 功能

通过产品条码追溯完整的生产参数和质检记录。

## 使用场景

- 用户要查看某个产品的生产过程
- 用户要排查质量问题的根因
- 用户要对比良品和不良品的工艺差异

## 分析步骤

1. 确认产品条码（barcode）
2. 用 `trace_product` 或 `trace_product_full` 查询
3. 用 Markdown 表格展示工艺参数 + 质检结果
4. 如有异常，标注偏差项

## 输出格式

| 阶段 | 参数 | 实际值 | 目标值 | 偏差 | 状态 |
|------|------|--------|--------|------|------|
