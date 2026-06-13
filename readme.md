# 工艺参数在线分析与调优系统 - 最终方案

## 1. 方案概述
本系统是一套面向制造业车间的**轻量级、闭环式工艺优化平台**，完全基于 Python 自研，不依赖任何第三方重型 IoT 平台。系统通过 HTTP 接收设备上报的工艺参数与产品检测结果，以**产品条码**为关联主键，经轻量级消息队列 NATS 缓冲后存入 PostgreSQL，并提供一体化 Web 前端，涵盖**实时监控、数据分析、参数推荐、审批下发、系统管理**等全部功能。前端采用 JS 技术栈，后端提供统一 REST API，所有组件编译为原生 Windows 可执行文件，通过单一安装包部署，支持开机自启、一键重启等运维特性。

---

## 2. 总体架构

### 2.1 架构拓扑
```
[生产设备/检测设备]
      │ HTTP POST (JSON)
      ▼
[数据接入网关 (FastAPI)]          ──pub──>   [NATS JetStream]   ──sub──>   [数据消费者 (Python)]
      │                                      (持久化消息队列)                    │
      │ 直接发布                                                              ▼
      ▼                                                                  [PostgreSQL]
 返回 202                                                                     │
                                                                              ├─ process_summary
                                                                              ├─ inspection_results
                                                                              ├─ analysis_view
                                                                              ├─ parameter_sets
                                                                              └─ parameter_items
                                                                              │
                                                                              ▼
                                                              [统一后端 API (FastAPI)]
                                                                      │
                                                         ┌──────────┼──────────┐
                                                         │          │          │
                                                    分析/推荐   参数下发/审批   系统管理
                                                         │          │          │
                                                         └──────────┼──────────┘
                                                                    ▼
                                                          [一体化前端 (Vue/React)]
                                                        (管理+分析+审批+配置)
```

- **设备层**：通过标准 HTTP 上报数据，无需额外客户端。
- **接入层**：轻量网关负责校验和发布至 NATS，立即返回，确保产线不中断。
- **消息层**：NATS JetStream 提供消息持久化、消费者组、重试与死信机制，保障数据可靠性。
- **处理层**：消费者读取消息，解析后以 UPSERT 方式写入 PostgreSQL，实现幂等处理。
- **存储层**：PostgreSQL 15 便携版，利用 JSONB 灵活存储参数与结果，内置分析视图自动按条码关联。
- **服务层**：统一 FastAPI 服务整合**数据分析、参数管理、系统管理** API，并托管前端静态资源。
- **展现层**：现代化 JS 前端，集成了管理仪表盘、交互式分析、参数审批下发、系统运维等全部界面。

### 2.2 关键技术选型

| 层面 | 技术 | 说明 |
|------|------|------|
| 消息队列 | NATS Server (JetStream) | 单文件 ~20MB，Go 编译，无外部依赖，极低资源占用 |
| 接入网关 | FastAPI + nats-py | 编译为单个 .exe |
| 数据消费者 | Python + nats-py + psycopg2 | 支持持久化消费、自动重试、批量写入 |
| 数据库 | PostgreSQL 15 便携版 | JSONB、视图、UPSERT |
| 后端 API | FastAPI（统一） | 集成分析算法、参数管理、系统控制 |
| 分析引擎 | scikit-learn, statsmodels, pyDOE2 | 相关性、特征重要性、回归、DOE |
| 前端 | Vue 3 + Element Plus / React + Ant Design | SPA，统一入口 |
| 图表 | Plotly.js / ECharts | 热力图、散点、响应曲面等 |
| 打包部署 | Inno Setup + PyInstaller | 单安装包，不携带源码 |
| 运行环境 | Windows 10/Server 2016+ 64位 | 内嵌 Python 运行时（已编译进 exe） |

---

## 3. 数据流与可靠性设计

1. **设备上报** → 网关 `POST /api/v1/data/process|inspection`，网关校验 JSON 格式后发布至 NATS `process_data` / `inspection_data` 主题，采用 JetStream 同步发布，确保写入后返回 `202`；若 NATS 不可用返回 `503`，设备可重试。
2. **消息缓冲**：NATS 将消息持久化到磁盘，消费者未 Ack 前不会删除，可配置最大投递次数（默认 5 次），超限转入死信主题。
3. **消费者处理**：消费者从 JetStream Pull 消息，解析 JSON，执行参数校验，然后写入 PostgreSQL，成功则 Ack。使用 `ON CONFLICT (barcode) DO UPDATE` 保证重复消费幂等。
4. **分析查询**：前端请求 → API → 直接查询 `analysis_view` 或原始表，所有计算在后端完成，仅返回结果。
5. **参数下发**：设备主动 GET `http://host:8000/api/v1/parameters/latest?device_type=xxx`，获取当前激活参数集。该接口无需认证或基于 API Key，与数据上报链路完全独立。

---

## 4. 数据库核心设计

- **process_summary** (barcode PK, device_id, processed_at, params JSONB)
- **inspection_results** (barcode PK, station_id, inspected_at, results JSONB)
- **analysis_view**：自动关联 barcode 的宽表视图，提取常用字段便于分析
- **parameter_sets** (id, name, device_type, status, created_by, note, created_at)
- **parameter_items** (set_id FK, param_key, param_value, unit)
- **parameter_confirmations** (device_id, parameter_set_id, status, confirmed_at) 可选

---

## 5. 一体化前端功能模块

采用单页面应用 (SPA)，侧边导航菜单包含：

| 模块 | 功能描述 |
|------|----------|
| **系统总览** | 实时显示接入设备数、今日数据量、服务运行状态（绿/红）、系统资源占用 |
| **数据分析** | 按设备/时间/批次筛选数据；相关性热力图；因子重要性柱状图；模型拟合（回归、PLS）及残差图；DOE 设计生成与方差分析；参数推荐（自动计算最优解并支持微调） |
| **工艺管理** | 参数推荐结果提交（状态为 `proposed`）；QA 审批列表（批准/驳回）；参数下发状态追踪；历史参数集查询与对比 |
| **系统设置** | 服务控制（启动/停止/重启各服务）；配置文件编辑（数据库连接、NATS 地址、API Key）；数据库一键备份/恢复；日志查看与搜索 |
| **用户中心** | 简单登录/登出（可选） |

所有操作均通过调用统一后端 API 完成，前端仅负责交互与渲染。

---

## 6. 部署与安装

### 6.1 安装包组成（压缩后约 150–180 MB）
- 编译后 exe：`Gateway.exe`, `Consumer.exe`, `BackendAPI.exe`（集成分析+参数+管理+静态前端）
- 运行时：`nats-server.exe`, PostgreSQL 15 便携版（解压后 ~120 MB）
- 配置文件：`config.ini`, `init-db.sql`
- 前端静态资源：`dist/`（由 BackendAPI 托管）
- 文档：部署手册 PDF

### 6.2 一键安装与自启动
- 双击 `Setup.exe`，选择目录，自动完成文件释放、DB 初始化、Windows 服务注册（NATS、PostgreSQL、Consumer、Gateway、BackendAPI 均注册为服务，启动类型为自动延迟）。
- 安装后系统自动启动所有服务，无需额外操作。
- 创建开始菜单快捷方式：“工艺优化平台”（打开浏览器访问 `http://localhost:8000`）。

### 6.3 一键重启
- 前端“系统设置”页面提供 **“重启全部服务”** 按钮，内部调用管理 API 按顺序停止/启动 Windows 服务。
- 也可通过开始菜单工具 `ServiceManager.exe`（可选）以图形化方式控制。

---

## 7. 系统约束与能力评估

### 7.1 约束条件
- **操作系统**：仅支持 Windows 10 / Server 2016 64 位及以上。
- **部署模式**：单机，不支持集群；NATS 单节点，无高可用。
- **设备规模**：≤50 台，每台上报频率 ≤10 条/秒（典型 1 条/秒）。
- **并发用户**：前端建议并发 ≤10 人，复杂分析可能占用较多后端资源。
- **安全性**：内网部署，无 HTTPS 内置支持，认证基于 API Key + 简单会话；不建议直接暴露公网。
- **数据存储**：依赖本地磁盘，需自行保证备份，数据库无复制。

### 7.2 性能指标
- **上报吞吐量**：网关单实例 > 1000 条/秒，NATS 可支撑 3000+ msg/s，远超 50 设备 × 1 条/秒（50 TPS）需求。
- **端到端延迟**：从 HTTP 上报到数据可查询 < 1 秒（典型 100-500ms）。
- **分析响应**：常规相关性、特征重要性（≤ 1 万条数据）< 2 秒；DOE 生成与拟合 < 1 秒。
- **资源占用**：全部服务运行内存 < 1.5 GB（空闲），CPU 常态 < 20%（i5 8GB 测试）。
- **可用性**：单机 Windows 服务模式下，非计划停机时间预计 < 3.5 小时/月（约 99.5%）。

### 7.3 数据可靠性
- 消息不丢失：NATS JetStream 持久化 + 消费者 Ack 保证。
- 数据可恢复：数据库支持一键备份，结合定期任务可实现灾难恢复。
- 死信队列：处理异常的消息可保留并后续人工介入。

---

## 8. 开发环境运行

### 8.1 启动依赖

```bash
docker compose up -d postgres nats
```

### 8.2 安装依赖

```bash
uv pip install --python .venv/bin/python -e '.[dev]'
```

如果不用 `uv`，也可以使用：

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

### 8.3 启动服务

分别打开三个终端：

```bash
process-opt-gateway
```

```bash
process-opt-consumer
```

```bash
process-opt-api
```

默认端口：

- Gateway: `8001`
- Backend API: `8000`
- NATS: `4222`
- PostgreSQL: `5432`

### 8.4 上报示例

工艺参数上报：

```bash
curl -X POST http://localhost:8001/api/v1/data/process \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key' \
  -d '{"message_id":"p1","barcode":"B1","device_id":"D1","processed_at":"2026-06-08T10:00:00Z","params":{"temperature":180}}'
```

检测结果上报：

```bash
curl -X POST http://localhost:8001/api/v1/data/inspection \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key' \
  -d '{"message_id":"i1","barcode":"B1","station_id":"QA1","inspected_at":"2026-06-08T10:05:00Z","results":{"diameter":10.2}}'
```

查询关联结果：

```bash
curl http://localhost:8000/api/v1/analysis/records/B1
```

---

## 9. 方案优势总结
- **完全自研轻量**：无 ThingsBoard/Kafka/Java 依赖，整体安装包约 160 MB，一键部署。
- **抗产线中断**：HTTP→NATS 异步解耦，后端服务全部宕机也不影响设备上报。
- **全链路闭环**：采集→分析→推荐→审批→下发→验证，形成工艺持续改进 PDCA 循环。
- **友好易用**：Web 界面集所有功能于一体，工艺/QA 无需编码即可完成复杂分析。
- **安全可控**：源码不暴露，数据不外传，权限可扩展。
- **运维便捷**：开机自启，图形化服务管理，支持在线重启与配置变更。

本方案精准匹配中小型制造企业工艺优化的需求，兼顾轻量、可靠、易用与可扩展性，具备快速落地与长期演进的能力。