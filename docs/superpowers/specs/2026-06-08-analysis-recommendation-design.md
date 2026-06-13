# 分析与参数推荐模块技术设计

## 背景

本设计基于已确认的后端、数据库与消息队列设计。系统已通过 `gateway`、NATS JetStream、`consumer` 和 PostgreSQL 建立数据采集与入库链路，分析模块在此基础上读取 `analysis_view`，为工艺分析、模型拟合和参数推荐提供后端能力。

当前设计范围仅覆盖分析与推荐模块，不包含前端页面、审批流程、参数下发、Windows 安装包和运维控制台。

## 设计目标

- 从 `analysis_view` 构建可复用的分析数据集。
- 支持相关性分析、特征重要性、回归建模和参数推荐。
- 分析算法作为 `api` 内部调用的分层 Python 包，不单独部署。
- 所有分析请求按需计算，首版不持久化模型。
- 推荐结果只能生成建议参数集，不能自动激活。
- 对样本不足、字段错误和模型失败提供结构化错误。

## 总体架构

新增 `analysis` 包，由 `api` 服务调用，不作为独立进程部署。

模块划分：

- `analysis.dataset`：从 `analysis_view` 构建统一分析数据集。
- `analysis.profiling`：字段识别、缺失率、异常值和样本摘要。
- `analysis.correlation`：计算相关性矩阵和显著字段。
- `analysis.importance`：计算特征重要性。
- `analysis.regression`：执行线性回归和 PLS 建模。
- `analysis.recommendation`：基于模型、参数范围和约束生成推荐参数。
- `analysis.errors`：定义分析模块结构化异常。

`api` 层职责：

- 接收 HTTP 请求。
- 校验请求参数。
- 检查时间范围、样本上限和字段权限。
- 调用 `analysis` 包。
- 将结果或错误转换为统一 API 响应。

`analysis` 层职责：

- 数据集构建。
- 数据清洗策略执行。
- 算法计算。
- 推荐候选搜索。
- 输出可解释结果。

## 数据集构建

所有分析入口先构建 `AnalysisDataset`。

### 输入

- `start_time`：开始时间。
- `end_time`：结束时间。
- `device_id`：可选设备过滤。
- `batch_id`：可选批次过滤，若后续数据模型支持。
- `barcodes`：可选条码列表。
- `feature_fields`：工艺参数字段列表。
- `target_fields`：检测指标字段列表。
- `missing_strategy`：缺失值处理策略。
- `max_samples`：最大样本数。

### 来源

- 主数据源为 `analysis_view`。
- 工艺参数来自 `params` JSONB 展开字段。
- 检测结果来自 `results` JSONB 展开字段。
- 元数据来自 `barcode`、`device_id`、`processed_at`、`station_id`、`inspected_at`。

### 输出

`AnalysisDataset` 包含：

- `features`：二维数值特征表。
- `targets`：二维或一维数值目标表。
- `metadata`：条码、设备、时间等追踪信息。
- `field_summary`：字段类型、缺失率、最小值、最大值、均值。
- `sample_count`：有效样本数。

### 校验规则

- 样本数小于算法要求时返回 `INSUFFICIENT_SAMPLES`。
- 字段不存在时返回 `FIELD_NOT_FOUND`。
- 字段无法转换为数值时返回 `NON_NUMERIC_FIELD`。
- 过滤条件导致空结果时返回 `EMPTY_DATASET`。
- 超过最大样本数时按时间倒序或配置策略截断，并在结果中标记 `truncated=true`。

### 缺失值策略

首版支持：

- `drop_row`：删除包含缺失值的样本。
- `mean`：用均值填充数值字段。
- `median`：用中位数填充数值字段。

默认策略为 `drop_row`，避免引入不可见偏差。

## 分析能力

### 数据概览

`analysis.profiling` 输出：

- 样本数。
- 字段列表。
- 字段类型。
- 缺失率。
- 数值范围。
- 均值和标准差。
- 异常值摘要。

异常值首版使用 IQR 方法识别，仅用于提示，不自动剔除。

### 相关性分析

支持方法：

- Pearson：适合线性关系。
- Spearman：适合单调关系和非正态数据。

输入：

- 一个或多个工艺参数字段。
- 一个或多个检测指标字段。
- 相关性方法。

输出：

- 相关性矩阵。
- 每个特征与目标的相关系数。
- 按绝对相关系数排序的显著字段。
- 样本数和缺失处理说明。

### 特征重要性

首版支持两类方法：

- 线性模型系数：用于可解释的线性关系。
- RandomForest 特征重要性：用于非线性关系的初步判断。

输出：

- 特征重要性排序。
- 方法名称。
- 样本数。
- 目标字段。
- 训练评分摘要。

特征重要性用于辅助判断，不作为自动决策依据。

### 回归建模

首版支持：

- 线性回归。
- PLS 回归。

输入：

- 特征字段。
- 单个目标字段。
- 模型类型。
- 缺失值策略。

输出：

- 模型类型。
- 特征列表。
- 目标字段。
- R²。
- RMSE。
- MAE。
- 残差摘要。
- 预测值与实际值样本。
- 模型适用性提示。

首版模型不持久化，请求结束后释放。

## 参数推荐

参数推荐由 `analysis.recommendation` 实现。

### 输入

推荐请求必须显式提供：

- `objective.target_field`：优化目标字段。
- `objective.direction`：`maximize` 或 `minimize`。
- `tunable_parameters`：可调参数列表。
- `bounds`：每个参数的上下限。
- `step` 或 `candidates`：每个参数的搜索步长或候选值。
- `fixed_parameters`：固定参数。
- `constraints`：业务约束。
- `model_type`：用于预测的模型类型。
- `dataset_filter`：时间、设备、条码等数据过滤条件。

### 约束类型

首版支持：

- 参数范围约束，如温度、压力、速度上下限。
- 离散候选值约束，如档位、模式。
- 目标阈值约束，如缺陷率必须低于指定值。
- 固定参数约束。

### 搜索策略

首版采用可解释的候选搜索：

1. 根据每个参数的上下限、步长或候选值生成候选组合。
2. 过滤不满足约束的组合。
3. 使用回归模型预测目标值。
4. 按优化方向排序。
5. 返回最佳组合和备选组合。

为避免组合爆炸，API 层限制候选组合数量。超过上限时返回 `SEARCH_SPACE_TOO_LARGE`，要求用户增大步长或减少参数数量。

### 输出

推荐结果包含：

- `recommended_parameters`：推荐参数组合。
- `predicted_target`：预测目标值。
- `alternatives`：备选参数组合。
- `important_features`：影响较大的参数。
- `risk_notes`：风险提示。
- `model_metrics`：模型评分摘要。
- `dataset_summary`：使用的数据范围和样本数。
- `can_submit_as_proposed`：是否可提交为建议参数集。

推荐结果必须标记为建议值，不允许自动激活。

## API 设计

分析 API 由 `api` 服务提供。

### 数据概览

`POST /api/v1/analysis/profile`

用途：获取字段、样本、缺失率和异常值摘要。

### 相关性分析

`POST /api/v1/analysis/correlation`

用途：计算工艺参数与检测指标之间的相关性。

### 特征重要性

`POST /api/v1/analysis/importance`

用途：识别对目标检测指标影响较大的工艺参数。

### 回归建模

`POST /api/v1/analysis/regression`

用途：拟合目标检测指标与工艺参数之间的关系。

### 参数推荐

`POST /api/v1/analysis/recommendation`

用途：基于模型和约束生成推荐参数组合。

### 提交建议参数集

`POST /api/v1/analysis/recommendation/submit`

用途：将推荐结果提交为 `proposed` 参数集，供后续审批模块处理。

该接口只创建建议参数集，不批准、不激活、不下发。

## 错误处理

分析模块返回结构化错误码。

错误码：

- `EMPTY_DATASET`：过滤后无数据。
- `INSUFFICIENT_SAMPLES`：有效样本数不足。
- `FIELD_NOT_FOUND`：字段不存在。
- `NON_NUMERIC_FIELD`：字段无法作为数值参与分析。
- `TOO_MANY_SAMPLES`：请求样本数超过上限且不允许截断。
- `SEARCH_SPACE_TOO_LARGE`：推荐候选组合数量过大。
- `MODEL_FIT_FAILED`：模型拟合失败。
- `INVALID_CONSTRAINT`：约束表达非法。

API 响应包含：

- `code`：错误码。
- `message`：面向用户的错误说明。
- `details`：字段名、样本数或约束信息。
- `suggestion`：建议用户如何修正请求。

## 性能与限制

首版默认限制：

- 单次分析最大样本数为 10,000。
- 单次推荐最大候选组合数为 50,000。
- 单次请求建议超时时间为 30 秒。
- 大查询必须指定时间范围。

这些限制可通过配置调整。

## 安全与决策边界

- 分析结果仅供工艺人员参考。
- 推荐参数不能自动激活。
- 推荐参数必须进入参数审批流程。
- API 不返回数据库连接、内部 SQL 或敏感配置。
- 错误响应只暴露必要业务信息。

## 测试策略

### 数据集测试

- JSONB 字段能正确展开为数值列。
- 缺失值策略 `drop_row`、`mean`、`median` 生效。
- 字段不存在返回 `FIELD_NOT_FOUND`。
- 非数值字段返回 `NON_NUMERIC_FIELD`。
- 样本不足返回 `INSUFFICIENT_SAMPLES`。

### 相关性测试

- 固定样本下 Pearson 结果稳定。
- 固定样本下 Spearman 结果稳定。
- 输出按绝对相关系数排序。

### 回归测试

- 线性样本能得到合理 R² 和 RMSE。
- PLS 在多特征样本下能返回模型指标。
- 模型无法拟合时返回 `MODEL_FIT_FAILED`。

### 推荐测试

- 推荐结果满足参数上下限。
- 推荐结果满足固定参数约束。
- 候选空间过大返回 `SEARCH_SPACE_TOO_LARGE`。
- 输出包含预测值、备选组合和风险提示。

### API 集成测试

- 每个分析接口能从数据库样本返回结果。
- 错误请求返回结构化错误。
- 推荐提交接口创建 `proposed` 参数集，不创建 `active` 参数集。

## 非目标

本阶段不实现：

- 深度学习模型。
- 自动模型训练任务。
- 模型持久化和版本管理。
- 自动审批或自动下发。
- 前端图表展示。
- 分析任务队列和异步任务管理。

## 后续扩展

- 增加模型持久化和版本管理。
- 增加异步分析任务。
- 增加 DOE 设计生成和方差分析。
- 增加参数推荐结果人工微调记录。
- 增加模型对比和交叉验证。
