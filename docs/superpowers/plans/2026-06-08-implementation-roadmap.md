# 工艺优化平台 Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已完成的模块设计整理为可执行的分阶段实施顺序。

**Architecture:** 项目应拆成多个独立实施计划，每个计划对应一个可测试子系统。先完成数据底座，再完成分析、参数流转、前端和部署能力。

**Tech Stack:** Python、FastAPI、NATS JetStream、PostgreSQL、Vue 3、Element Plus、ECharts、PyInstaller、Inno Setup、systemd、launchd。

---

## 已完成设计文档

1. `docs/superpowers/specs/2026-06-08-backend-data-message-design.md`
   - 后端服务、数据库、NATS、数据接入、消费者、基础 API。

2. `docs/superpowers/specs/2026-06-08-analysis-recommendation-design.md`
   - 数据集构建、相关性、重要性、回归、参数推荐。

3. `docs/superpowers/specs/2026-06-08-parameter-approval-delivery-design.md`
   - 参数状态机、审批、激活、设备主动拉取、确认回报。

4. `docs/superpowers/specs/2026-06-08-frontend-module-design.md`
   - Vue SPA、侧边栏布局、分析页、工艺管理、系统设置、权限。

5. `docs/superpowers/specs/2026-06-08-cross-platform-deployment-design.md`
   - Windows/Linux/macOS 部署、服务管理、配置、备份、恢复、升级。

## 推荐实施顺序

### Phase 1: 后端数据底座

**对应设计：** `2026-06-08-backend-data-message-design.md`

**目标：** 完成最小可运行链路：HTTP 上报 → NATS → Consumer → PostgreSQL → API 查询。

**建议单独计划文件：** `docs/superpowers/plans/2026-06-08-backend-data-message-plan.md`

**完成标准：**

- Gateway 可接收 process/inspection 上报。
- NATS JetStream 可持久化消息。
- Consumer 可幂等写入 PostgreSQL。
- API 可查询条码、时间范围和 `analysis_view`。
- 集成测试覆盖完整链路。

### Phase 2: 参数集基础与状态机

**对应设计：** `2026-06-08-parameter-approval-delivery-design.md`

**目标：** 在分析模块之前先完成参数集模型、状态机和 latest 拉取接口，便于后续推荐结果提交。

**建议单独计划文件：** `docs/superpowers/plans/2026-06-08-parameter-state-machine-plan.md`

**完成标准：**

- 参数集和参数项可创建、提交、审批、激活。
- 同一 `device_type` 只能有一个 `active`。
- 设备可拉取 latest 参数。
- 设备确认可记录。
- 审计事件完整记录。

### Phase 3: 分析与推荐模块

**对应设计：** `2026-06-08-analysis-recommendation-design.md`

**目标：** 基于 `analysis_view` 实现分析数据集、相关性、回归和推荐，并能提交 `proposed` 参数集。

**建议单独计划文件：** `docs/superpowers/plans/2026-06-08-analysis-recommendation-plan.md`

**完成标准：**

- 能构建 `AnalysisDataset`。
- 支持 profile、correlation、importance、regression、recommendation API。
- 推荐结果符合约束。
- 推荐结果只能提交为 `proposed`。
- 样本不足、字段错误、模型失败均有结构化错误。

### Phase 4: 前端 SPA

**对应设计：** `2026-06-08-frontend-module-design.md`

**目标：** 实现完整闭环 UI：总览 → 数据分析 → 推荐提交 → 审批激活 → 设备确认查看。

**建议单独计划文件：** `docs/superpowers/plans/2026-06-08-frontend-spa-plan.md`

**完成标准：**

- Vue 3 + Element Plus SPA 可构建。
- 登录和权限控制可用。
- 数据分析页可调用后端分析 API。
- 工艺管理页可执行审批和激活。
- 系统设置页可展示服务状态和危险操作确认。
- 前端静态资源可由 BackendAPI 托管。

### Phase 5: 跨平台部署与运维

**对应设计：** `2026-06-08-cross-platform-deployment-design.md`

**目标：** 实现 Windows/Linux/macOS 生产部署包和统一 `platformctl` 运维入口。

**建议单独计划文件：** `docs/superpowers/plans/2026-06-08-cross-platform-deployment-plan.md`

**完成标准：**

- Windows 可生成 `Setup.exe` 并注册服务。
- Linux 可解压 tar.gz 并注册 systemd。
- macOS 可解压 tar.gz 并注册 launchd。
- `platformctl start|stop|restart|status|doctor|backup|restore|migrate` 可用。
- 升级保留配置并执行迁移。

## 依赖关系

```text
Phase 1 后端数据底座
  ├─> Phase 2 参数状态机
  │     └─> Phase 3 分析推荐提交 proposed
  ├─> Phase 3 分析推荐读取 analysis_view
  └─> Phase 4 前端调用 API

Phase 1 + Phase 2 + Phase 3 + Phase 4
  └─> Phase 5 跨平台部署打包
```

## 首个实施计划建议

建议先创建并执行：

`docs/superpowers/plans/2026-06-08-backend-data-message-plan.md`

原因：

- 它是所有模块的基础。
- 能最快验证技术选型是否成立。
- 完成后可用集成测试证明数据链路闭环。

## 后续计划编写规则

每个 Phase 单独写实施计划，计划必须包含：

- 具体文件结构。
- 每个任务的失败测试。
- 最小实现步骤。
- 精确测试命令。
- 每个任务后独立提交。
- 最终 lint、typecheck、test 验证命令。

## 当前不建议一次性实施的内容

- 不建议同时实现前端和后端。
- 不建议先做部署打包。
- 不建议先做复杂分析算法。
- 不建议把五个模块放进一个巨大实施计划。

## 下一步

- [ ] 为 Phase 1 编写详细 TDD 实施计划。
- [ ] Review Phase 1 计划。
- [ ] 按 Phase 1 计划执行后端数据底座。
- [ ] 完成 Phase 1 后再进入 Phase 2。
