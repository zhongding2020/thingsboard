# 后端、数据库与消息队列技术设计

## 背景

本设计基于 `readme.md` 中的纯 Python 自研方案，不依赖 ThingsBoard CE。当前设计范围仅覆盖后端服务、数据库和消息队列，不包含前端、Windows 安装包和运维控制台。

目标是实现面向制造业车间的轻量级工艺数据采集、缓存、入库、查询、分析和参数管理后端基础架构。

## 设计目标

- 设备通过 HTTP 上报工艺参数和检测结果。
- 网关快速校验并写入 NATS JetStream，避免产线阻塞。
- 消费者异步处理消息并幂等写入 PostgreSQL。
- API 服务提供统一查询、分析和参数管理接口。
- 代码采用单仓库模块化结构，便于开发、测试和后续打包。

## 总体架构

采用单仓库模块化结构，包含四个核心模块：

- `gateway`：FastAPI 接入网关，负责设备 HTTP 上报、基础校验、API Key 鉴权和 NATS 发布。
- `consumer`：JetStream 消费者，负责拉取消息、业务校验、转换和 PostgreSQL 写入。
- `api`：统一业务 API，负责数据查询、分析接口和参数管理接口。
- `common`：共享模块，提供配置、日志、数据库连接、NATS 客户端、Schema 和通用异常定义。

三个运行服务分别为：

- `Gateway`：接收设备数据。
- `Consumer`：消费消息并入库。
- `BackendAPI`：提供业务 API。

这种结构在部署上保持服务隔离，在代码上复用公共能力，避免采集、消费和业务 API 强耦合。

## 数据流

### 工艺参数上报

1. 设备调用 `POST /api/v1/data/process`。
2. `gateway` 校验请求 JSON、必填字段和 API Key。
3. 校验通过后发布到 JetStream subject `process_data`。
4. JetStream 确认持久化成功后，网关返回 `202 Accepted`。
5. `consumer` 拉取消息，校验业务字段。
6. 使用 `barcode` 作为主键写入或更新 `process_summary`。
7. 写入成功后 ack 消息。

### 检测结果上报

1. 设备调用 `POST /api/v1/data/inspection`。
2. `gateway` 校验请求并发布到 JetStream subject `inspection_data`。
3. `consumer` 消费后写入或更新 `inspection_results`。
4. `analysis_view` 通过 `barcode` 自动关联工艺参数和检测结果。

## 消息模型

### 工艺参数消息

必需字段：

- `message_id`：消息唯一 ID，由设备提供或网关生成。
- `barcode`：产品条码，核心关联主键。
- `device_id`：设备编号。
- `processed_at`：加工时间。
- `params`：工艺参数 JSON 对象。

### 检测结果消息

必需字段：

- `message_id`：消息唯一 ID，由设备提供或网关生成。
- `barcode`：产品条码，核心关联主键。
- `station_id`：检测工位编号。
- `inspected_at`：检测时间。
- `results`：检测结果 JSON 对象。

## 数据库设计

### process_summary

存储每个产品条码对应的工艺参数摘要。

字段：

- `barcode`：主键。
- `device_id`：加工设备。
- `processed_at`：加工时间。
- `params`：JSONB，存储动态工艺参数。
- `created_at`：创建时间。
- `updated_at`：更新时间。

唯一约束：

- `barcode`。

写入策略：

- 使用 `INSERT ... ON CONFLICT (barcode) DO UPDATE` 实现幂等。

### inspection_results

存储每个产品条码对应的检测结果。

字段：

- `barcode`：主键。
- `station_id`：检测工位。
- `inspected_at`：检测时间。
- `results`：JSONB，存储动态检测指标。
- `created_at`：创建时间。
- `updated_at`：更新时间。

唯一约束：

- `barcode`。

写入策略：

- 使用 `INSERT ... ON CONFLICT (barcode) DO UPDATE` 实现幂等。

### analysis_view

按 `barcode` 关联 `process_summary` 和 `inspection_results`，作为分析查询的基础宽表。

用途：

- 查询同一产品的工艺参数和检测结果。
- 支撑后续相关性分析、回归分析和参数推荐。
- 对常用 JSONB 字段可在视图中展开为普通列。

### parameter_sets

存储参数集元信息。

字段：

- `id`：主键。
- `name`：参数集名称。
- `device_type`：设备类型。
- `status`：状态，取值包括 `draft`、`proposed`、`approved`、`active`、`rejected`、`archived`。
- `created_by`：创建人。
- `note`：备注。
- `created_at`：创建时间。
- `updated_at`：更新时间。

### parameter_items

存储参数集明细。

字段：

- `id`：主键。
- `set_id`：关联 `parameter_sets.id`。
- `param_key`：参数名。
- `param_value`：参数值。
- `unit`：单位。

约束：

- `set_id` 外键引用 `parameter_sets`。
- 同一 `set_id` 下 `param_key` 唯一。

## API 边界

### 接入 API

由 `gateway` 提供：

- `POST /api/v1/data/process`：接收工艺参数。
- `POST /api/v1/data/inspection`：接收检测结果。

成功响应：

- `202 Accepted`。

失败响应：

- `400`：JSON 格式或必填字段错误。
- `401`：API Key 无效。
- `503`：NATS 不可用或发布失败。

### 查询与分析 API

由 `api` 提供：

- 按条码查询工艺参数和检测结果。
- 按设备、时间范围查询数据。
- 查询 `analysis_view`。
- 预留相关性、回归和参数推荐接口。

分析计算在后端执行，前端或调用方只接收结果数据。

### 参数管理 API

由 `api` 提供：

- 创建参数集。
- 查询参数集列表和详情。
- 修改参数集状态。
- 查询指定设备类型的最新激活参数集。

设备拉取最新参数时使用：

- `GET /api/v1/parameters/latest?device_type=xxx`

## 可靠性设计

- 网关只有在 JetStream 确认持久化成功后才返回 `202`。
- NATS 不可用时返回 `503`，由设备端重试。
- 消费者处理成功后才 ack。
- 数据库写入失败时不 ack，由 JetStream 重投。
- 业务校验失败的消息记录错误原因，并进入错误表或死信主题。
- 消息携带 `message_id`、`barcode` 和时间戳，便于链路追踪。
- 入库使用 `barcode` 幂等更新，避免重复消费造成重复数据。

## 错误处理

### 网关错误

- 请求体不是合法 JSON：返回 `400`。
- 缺少 `barcode`、时间戳或业务主体字段：返回 `400`。
- API Key 错误：返回 `401`。
- NATS 连接失败或发布失败：返回 `503`。

### 消费者错误

- JSON 解析失败：记录错误并进入死信。
- 必填字段缺失：记录错误并进入死信。
- 数据库暂时不可用：不 ack，等待重投。
- 数据库约束错误：记录错误并进入死信或错误表。

## 测试策略

### 网关测试

- 合法工艺参数上报返回 `202`。
- 合法检测结果上报返回 `202`。
- 缺少必填字段返回 `400`。
- API Key 无效返回 `401`。
- NATS 发布失败返回 `503`。

### 消费者测试

- 正常 `process_data` 消息写入 `process_summary`。
- 正常 `inspection_data` 消息写入 `inspection_results`。
- 重复 `barcode` 消息执行更新而不是插入重复记录。
- 非法消息进入错误处理流程。
- 数据库失败时消息不 ack。

### 数据库测试

- 迁移脚本可从空库创建全部表和视图。
- JSONB 字段可保存动态参数和检测结果。
- `analysis_view` 能按 `barcode` 正确关联数据。
- 参数集与参数项外键约束有效。

### 集成测试

验证完整链路：

1. 调用 HTTP 上报接口。
2. 网关发布 NATS 消息。
3. 消费者消费消息。
4. PostgreSQL 写入数据。
5. API 查询到对应记录。

## 非目标

本阶段不设计以下内容：

- 前端页面与交互。
- Windows 安装包。
- Windows 服务注册。
- 系统设置和服务控制 UI。
- 高可用集群。
- 公网 HTTPS 暴露。

## 后续扩展

- 增加分析算法模块，支持相关性、回归和参数推荐。
- 增加参数审批状态流转。
- 增加错误消息重放工具。
- 增加定期数据库备份。
- 增加前端管理界面。
