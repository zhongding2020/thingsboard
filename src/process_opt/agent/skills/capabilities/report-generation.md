---
name: report-generation
display_name: 报告生成
type: capability
description: 生成工艺分析报告（Markdown 格式），汇总分析结果
triggers:
  - 报告
  - 总结
  - 汇总
  - 生成报告
tools:
  - generate_report
---

## 功能

基于对话历史中的分析数据，生成结构化 Markdown 工艺分析报告。

## 使用场景

- 用户完成了多步分析后要求汇总
- 用户要求导出分析报告

## 分析步骤

1. 回顾对话历史中的分析结果
2. 调用 `generate_report` 组装报告
3. 报告应包含：工艺概况、数据分析、模型结果、推荐参数、风险提示

## 输出格式

完整的 Markdown 文档，包含标题层级、表格、结论和建议
