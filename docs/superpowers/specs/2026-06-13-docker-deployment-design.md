# Docker 部署方案设计

## 背景

基于已完成的四个后端服务（Gateway、Consumer、BackendAPI）和前端 SPA，将现有开发 docker-compose（仅 postgres + nats）升级为完整 Docker 生产部署，包含所有业务服务。

## 设计目标

- 所有服务容器化：postgres、nats、gateway、consumer、backend-api。
- 单 docker-compose.yml 启动完整系统。
- 正确的启动顺序和健康检查。
- 数据和 NATS 持久化到系统卷。
- 前端静态资源由 backend-api 容器托管。

## 镜像策略

采用**单 Dockerfile + 多启动入口**方式：

- 基于 `python:3.11-slim`。
- 复制 `src/` 和 `pyproject.toml`，安装依赖。
- 复制 `web/dist/`（需构建好前端）。
- 提供三个入口脚本：`scripts/run-gateway.sh`、`scripts/run-consumer.sh`、`scripts/run-api.sh`。
- docker-compose 中每个 service 通过 `command` 指定不同的入口。

不拆多个 Dockerfile 的原因：当前规模下单镜像更简单，且三个服务共享同一依赖集。

## 服务编排

### postgres

- 镜像：`postgres:15`。
- 端口：`5432`。
- 环境变量：POSTGRES_DB、USER、PASSWORD。
- 数据持久化：`tb-postgres-data` 卷。
- 健康检查：`pg_isready`。

### nats

- 镜像：`nats:2.10`。
- 启动参数：`-js -sd /data -m 8222`（启用 JetStream、监控端口）。
- 端口：`4222`（NATS 客户端）、`8222`（监控）。
- 数据持久化：`nats-data` 卷。
- 健康检查：curl NATS monitoring healthz 端点。

### gateway

- 镜像：从 Dockerfile 构建。
- 端口：`8001`。
- 命令：`scripts/run-gateway.sh`（等待 nats 就绪后启动 uvicorn）。
- 依赖：nats（condition: service_healthy）。
- 环境变量：从 .env 或 docker-compose 环境配置。

### consumer

- 镜像：从 Dockerfile 构建。
- 命令：`scripts/run-consumer.sh`（等待 nats 和 postgres 就绪后运行消费者循环）。
- 依赖：postgres（healthy）+ nats（healthy）。
- 环境变量：数据库连接和 NATS 地址。

### backend-api

- 镜像：从 Dockerfile 构建。
- 端口：`8000`。
- 命令：`scripts/run-api.sh`（等待 postgres 就绪后启动 uvicorn）。
- 依赖：postgres（healthy）。
- 前端构建产物 `web/dist/` 在构建时复制到镜像中，由 BackendAPI 托管。

## 启动顺序

1. postgres → 健康 → nats + backend-api 同时启动
2. nats → 健康 → gateway + consumer 同时启动
3. backend-api → 可直接服务 API + 前端

Consumer 额外依赖 nats，但 nats 健康检查在 postgres 之前或之后均可启动。

## 配置管理

使用 docker-compose 环境变量覆盖默认配置：

```yaml
environment:
  PROCESS_OPT_GATEWAY_API_KEY: "change-me"
  PROCESS_OPT_NATS_URL: "nats://nats:4222"
  PROCESS_OPT_POSTGRES_DSN: "postgresql://postgres:postgres@postgres:5432/process_opt"
  PROCESS_OPT_GATEWAY_PORT: "8001"
  PROCESS_OPT_API_PORT: "8000"
```

容器间通过服务名（`postgres`、`nats`）通信。

## 入口脚本

创建 `scripts/` 目录，三个 bash 脚本：

- `run-gateway.sh`：循环检测 nats 端口 4222 和监控端口 8222，就绪后执行 `.venv/bin/python -m process_opt.gateway.main`（实际上是 process-opt-gateway 命令）。
- `run-consumer.sh`：循环检测 postgres 端口 5432 和 nats 端口 4222，就绪后执行 process-opt-consumer。
- `run-api.sh`：循环检测 postgres 端口 5432，就绪后执行 process-opt-api。

## 前端集成

- `web/dist/` 在 Dockerfile 构建时复制。
- BackendAPI 启动时自动挂载静态目录并托管前端。
- 用户访问 `http://localhost:8000` 即可使用全部功能。

## 数据持久化

- `pgdata` 卷：PostgreSQL 数据目录。
- `nats-data` 卷：NATS JetStream 持久化路径。

## 网络

单 `backend` 网络，所有服务加入同一网络，通过服务名通信。

## 非目标

本阶段不实现：

- Kubernetes 部署。
- Docker Swarm 部署。
- 自动 HTTPS 证书。
- 灰度发布或蓝绿部署。
- 日志聚合到 ELK/grafana。
- 监控告警。
- 镜像推送至远程仓库。

## 后续扩展

- 增加 docker-compose.override.yml 用于开发环境。
- 增加 Makefile 简化构建和启动。
- 增加健康检查 API 端点。
- 增加 Docker healthcheck 指令。
- 增加环境变量文档。
