# 参数调优 Excel 导入 — 设计文档

## 概述

参数调优页面新增两种数据源模式：数据库查询（现有）和 Excel 导入。页面顶部 Tab 切换。

## 后端

### 新增依赖

`openpyxl` — Excel 文件解析

### 新增文件: `src/process_opt/analysis/excel.py`

解析 Excel 返回 `AnalysisDataset`，包含：
- `parse_excel(file_bytes) -> AnalysisDataset` — 解析 Excel 流
- 断言第一行为 header，数值列为 features，pass/fail 文本列为 targets

### 新增 API

`POST /api/v1/analysis/upload` — 接收 multipart Excel 文件，返回 `{ dataset_id, fields: { features: [...], targets: [...] }, sample_count }`

数据集存储在进程内存（dict），过期清理。

### 修改分析 API

profile/correlation/regression/recommendation 接口增加可选参数 `dataset_id: str | None = None`。有值时直接使用上传数据集，不走 DB。

## 前端

### AnalysisView.vue 顶部

Tab 切换：`库里数据` | `导入文件`。默认库里数据。

### 库数据模式

保持现有 AnalysisFilter + 4 个分析 Tab。

### 导入模式

- 文件上传区（el-upload drag）
- 模板下载链接（GET `/api/v1/analysis/template`）
- 上传后自动跳转到分析结果 Tab
- 上传数据预览表格（字段名 + 前 5 行预览）

## 模板格式

| temperature | conveyor_speed | oxygen_ppm | solder_joint_quality | voiding_pct |
|-------------|---------------|------------|---------------------|-------------|
| 220.5 | 48.2 | 187 | pass | pass |
| 215.0 | 52.0 | 195 | pass | fail |

## 实现顺序

1. 后端: 安装 openpyxl + excel.py
2. 后端: upload 路由 + dataset 内存管理
3. 后端: 分析接口增加 dataset_id
4. 后端: template 下载
5. 前端: AnalysisView Tab 切换 + 上传组件
6. 前端: API 调用适配
7. 测试 + 构建
