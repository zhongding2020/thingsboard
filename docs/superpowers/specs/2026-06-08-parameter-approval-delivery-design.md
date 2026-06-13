# 参数审批与下发模块技术设计

## 背景

本设计基于已确认的后端、数据库与消息队列设计，以及分析与参数推荐模块设计。分析模块可以生成建议参数集，但不能自动激活或下发。参数审批与下发模块负责将建议参数集纳入人工审批流程，并向设备提供当前生效参数。

当前设计范围覆盖参数集状态机、审批、激活、设备主动拉取、确认回报和审计记录，不包含前端页面、Windows 安装包和设备端实现。

## 设计目标

- 建立明确的参数集生命周期状态机。
- 保证推荐参数不能绕过审批直接激活。
- 同一 `device_type` 同一时间只能存在一个 `active` 参数集。
- 设备通过主动拉取获取最新生效参数，后端不主动推送。
- 所有状态变更可审计、可追踪。
- 支持设备回报参数拉取、应用成功或失败状态。

## 总体架构

参数审批与下发能力由 `api` 服务提供。

模块划分：

- `parameters.repository`：参数集、参数项、事件和确认记录的数据访问。
- `parameters.state_machine`：参数集状态流转规则。
- `parameters.service`：创建、审批、激活、归档、查询 latest 参数集。
- `parameters.confirmation`：设备确认回报处理。
- `parameters.errors`：结构化业务错误。

依赖：

- PostgreSQL：保存参数集、参数项、事件和设备确认记录。
- `analysis.recommendation`：可提交 `proposed` 参数集。
- `api` 鉴权模块：区分提交、审批、激活权限。

## 状态机设计

参数集状态：

- `draft`：草稿，允许编辑。
- `proposed`：已提交，等待审批。
- `approved`：审批通过，等待激活。
- `active`：当前生效，可被设备拉取。
- `rejected`：审批驳回。
- `archived`：历史归档，不再生效。

允许状态流转：

- `draft -> proposed`
- `proposed -> approved`
- `proposed -> rejected`
- `approved -> active`
- `active -> archived`
- `approved -> archived`

禁止状态流转：

- `proposed -> active`
- `rejected -> active`
- `archived -> active`
- `active -> draft`
- `active -> proposed`

推荐模块只能创建 `proposed` 参数集，不能创建 `approved` 或 `active` 参数集。

## 数据库设计

### parameter_sets

参数集元信息表。

字段：

- `id`：主键。
- `name`：参数集名称。
- `device_type`：设备类型。
- `version`：设备类型内递增版本号。
- `status`：参数集状态。
- `source`：来源，取值如 `manual`、`recommendation`。
- `created_by`：创建人。
- `approved_by`：审批人。
- `activated_by`：激活人。
- `note`：备注。
- `created_at`：创建时间。
- `updated_at`：更新时间。
- `approved_at`：审批时间。
- `activated_at`：激活时间。
- `archived_at`：归档时间。

约束：

- 同一 `device_type` 下 `version` 唯一。
- 同一 `device_type` 只能有一个 `active` 参数集。

### parameter_items

参数集明细表。

字段：

- `id`：主键。
- `set_id`：关联 `parameter_sets.id`。
- `param_key`：参数名。
- `param_value`：参数值。
- `unit`：单位。
- `data_type`：参数类型，如 `number`、`string`、`boolean`。
- `min_value`：可选最小值。
- `max_value`：可选最大值。
- `description`：说明。

约束：

- `set_id` 外键引用 `parameter_sets`。
- 同一 `set_id` 下 `param_key` 唯一。

修改规则：

- `draft` 状态允许修改参数项。
- `proposed` 状态之后不允许直接修改参数项。
- 如需修改 `approved` 或 `active` 参数集，必须复制为新版本。

### parameter_set_events

参数集状态变更审计表。

字段：

- `id`：主键。
- `set_id`：关联 `parameter_sets.id`。
- `event_type`：事件类型，如 `create`、`submit`、`approve`、`reject`、`activate`、`archive`。
- `from_status`：旧状态。
- `to_status`：新状态。
- `operator`：操作人。
- `note`：操作备注。
- `created_at`：事件时间。

用途：

- 追踪参数集生命周期。
- 支持审计和问题追溯。
- 支持前端展示审批历史。

### parameter_confirmations

设备参数确认表。

字段：

- `id`：主键。
- `device_id`：设备编号。
- `device_type`：设备类型。
- `parameter_set_id`：关联 `parameter_sets.id`。
- `parameter_version`：参数版本。
- `status`：确认状态，取值包括 `fetched`、`applied`、`failed`。
- `message`：设备回报信息。
- `confirmed_at`：确认时间。

用途：

- 记录设备是否已拉取参数。
- 记录设备是否已成功应用参数。
- 记录应用失败原因。

## API 设计

### 创建参数集

`POST /api/v1/parameters/sets`

用途：创建 `draft` 参数集。

### 提交参数集

`POST /api/v1/parameters/sets/{id}/submit`

用途：将 `draft` 参数集提交为 `proposed`。

### 审批通过

`POST /api/v1/parameters/sets/{id}/approve`

用途：将 `proposed` 参数集审批为 `approved`。

### 审批驳回

`POST /api/v1/parameters/sets/{id}/reject`

用途：将 `proposed` 参数集驳回为 `rejected`。

### 激活参数集

`POST /api/v1/parameters/sets/{id}/activate`

用途：将 `approved` 参数集激活为 `active`。

行为：

- 在数据库事务中执行。
- 锁定相同 `device_type` 的相关参数集。
- 将旧 `active` 参数集更新为 `archived`。
- 将目标参数集更新为 `active`。
- 写入归档和激活事件。

### 查询最新生效参数

`GET /api/v1/parameters/latest?device_type=xxx&device_id=yyy`

用途：设备主动拉取当前生效参数。

返回：

- `parameter_set_id`。
- `device_type`。
- `version`。
- `name`。
- `activated_at`。
- `items`：参数项列表。
- `checksum`：参数摘要。

如果没有 active 参数集，返回 `NO_ACTIVE_PARAMETER_SET`。

### 设备确认回报

`POST /api/v1/parameters/confirmations`

用途：设备回报参数拉取或应用结果。

请求字段：

- `device_id`。
- `device_type`。
- `parameter_set_id`。
- `parameter_version`。
- `status`：`fetched`、`applied` 或 `failed`。
- `message`：可选说明。

## 设备下发模式

采用设备主动拉取，不采用后端推送。

原因：

- 设备网络环境复杂，主动拉取更易适配。
- 后端不需要维护设备长连接。
- 设备可按自身节拍决定何时应用参数。
- 内网单机部署下足够可靠。

设备推荐流程：

1. 设备定时或在换型前请求 `latest`。
2. 后端返回当前 `active` 参数集。
3. 设备校验 `checksum`。
4. 设备应用参数。
5. 设备调用确认接口回报 `fetched`、`applied` 或 `failed`。

## 版本与并发控制

版本规则：

- 同一 `device_type` 下 `version` 递增。
- 新建参数集时分配下一个版本号。
- 复制历史参数集时生成新版本。

并发控制：

- 激活操作必须在数据库事务中完成。
- 激活时锁定同一 `device_type` 下的参数集记录。
- 使用唯一约束保证同一 `device_type` 只能有一个 `active`。
- 若并发激活冲突，返回 `ACTIVE_CONFLICT`。

不可变规则：

- `approved`、`active`、`archived` 参数集不可直接修改参数项。
- 需要调整时复制为新 `draft` 或新 `proposed`。

## 错误处理

错误码：

- `PARAMETER_SET_NOT_FOUND`：参数集不存在。
- `INVALID_TRANSITION`：非法状态流转。
- `ACTIVE_CONFLICT`：同一设备类型激活冲突。
- `NO_ACTIVE_PARAMETER_SET`：没有可拉取的生效参数集。
- `IMMUTABLE_PARAMETER_SET`：参数集状态不允许修改。
- `INVALID_CONFIRMATION_STATUS`：设备确认状态非法。
- `VERSION_CONFLICT`：版本号冲突。

错误响应包含：

- `code`：错误码。
- `message`：用户可读说明。
- `details`：参数集 ID、当前状态、目标状态等上下文。
- `suggestion`：建议处理方式。

## 权限边界

首版保留简单权限模型：

- 工艺人员：创建、编辑 `draft`，提交 `proposed`。
- QA/主管：审批通过或驳回。
- 管理员：激活参数集、归档参数集。
- 设备：只能读取 latest 参数并提交确认。

设备接口可使用 API Key，与后台用户会话分离。

## 测试策略

### 状态机测试

- `draft -> proposed` 成功。
- `proposed -> approved` 成功。
- `proposed -> rejected` 成功。
- `approved -> active` 成功。
- `proposed -> active` 返回 `INVALID_TRANSITION`。
- `rejected -> active` 返回 `INVALID_TRANSITION`。

### 审计测试

- 创建参数集写入 `create` 事件。
- 提交写入 `submit` 事件。
- 审批写入 `approve` 或 `reject` 事件。
- 激活写入 `activate` 事件。
- 旧 active 自动归档时写入 `archive` 事件。

### 激活并发测试

- 同一 `device_type` 并发激活两个参数集，最终只能有一个 `active`。
- 冲突请求返回 `ACTIVE_CONFLICT` 或保持事务一致性。

### latest 拉取测试

- 有 active 参数时返回参数集和参数项。
- 无 active 参数时返回 `NO_ACTIVE_PARAMETER_SET`。
- 返回值包含 `checksum`。

### 确认回报测试

- `fetched` 状态可记录。
- `applied` 状态可记录。
- `failed` 状态可记录错误信息。
- 未知参数集返回 `PARAMETER_SET_NOT_FOUND`。
- 非法状态返回 `INVALID_CONFIRMATION_STATUS`。

## 非目标

本阶段不实现：

- 后端主动推送参数到设备。
- 设备端参数应用逻辑。
- 复杂 RBAC 权限系统。
- 电子签名。
- 多级审批流。
- 参数灰度发布。
- 参数回滚自动执行。

## 后续扩展

- 支持多级审批。
- 支持参数灰度发布。
- 支持设备分组参数。
- 支持参数回滚。
- 支持电子签名和审批意见模板。
- 支持参数应用结果与质量结果闭环分析。
