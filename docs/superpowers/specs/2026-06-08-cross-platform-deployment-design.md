# 跨平台部署与运维模块技术设计

## 背景

本设计基于已确认的后端、分析推荐、参数审批下发和前端模块设计。系统需要支持服务器运行环境不固定的场景，目标平台包括 Windows、Linux 和 macOS。

当前设计范围覆盖跨平台生产部署、服务管理、目录结构、配置、升级、备份、恢复和健康检查，不包含具体业务功能实现和设备端实现。

## 设计目标

- 支持 Windows、Linux、macOS 三类服务器部署。
- 三端共享一致的应用目录结构和配置模型。
- 服务可开机自启、统一启动停止、查看状态和日志。
- 支持外部 PostgreSQL 优先，内置或容器化数据库作为可选方案。
- 支持升级前备份、数据库迁移和部署后验证。
- 敏感配置不得写入日志。

## 交付形态

### Windows

交付文件：

- `Setup.exe`

安装方式：

- 使用 Inno Setup 生成单安装包。
- 默认安装到 `C:\Program Files\ProcessOptPlatform`。
- 安装过程注册 Windows Service。
- 安装完成后可选择立即启动服务。

### Linux

交付文件：

- `process-opt-platform-linux-x64.tar.gz`

安装方式：

- 默认解压到 `/opt/process-opt-platform`。
- 安装脚本生成 systemd service 文件。
- 使用 `systemctl` 管理服务。
- 支持非 root 用户运行应用服务，但注册 systemd 需要管理员权限。

### macOS

交付文件：

- `process-opt-platform-darwin-x64.tar.gz`
- 后续可扩展 `.pkg` 安装包。

安装方式：

- 默认安装到 `/usr/local/process-opt-platform`。
- 后续桌面化场景可安装到 `/Applications/ProcessOptPlatform`。
- 安装脚本生成 launchd plist。
- 使用 `launchctl` 管理服务。

## 安装包内容

三端安装包均包含：

- `Gateway` 可执行文件。
- `Consumer` 可执行文件。
- `BackendAPI` 可执行文件。
- 前端静态资源 `frontend/dist/`。
- 对应平台的 `nats-server` 二进制文件。
- 数据库初始化脚本和迁移脚本。
- 配置模板。
- 服务注册脚本。
- `platformctl` 统一管理 CLI。
- 默认日志目录。
- 默认 NATS 数据目录。
- 备份目录。

不强制内置 PostgreSQL 数据文件。

## 数据库与 NATS 策略

### NATS

NATS 随安装包内置对应平台二进制。

原因：

- NATS 单文件、轻量、跨平台。
- 可控性高，便于统一配置 JetStream。
- 避免要求客户预装消息队列。

NATS 数据默认存放：

- Windows：`%ProgramData%\ProcessOptPlatform\data\nats`
- Linux：`/var/lib/process-opt-platform/nats`
- macOS：`/usr/local/var/process-opt-platform/nats`

### PostgreSQL

采用外部 PostgreSQL 优先策略。

优先级：

1. 使用客户已有 PostgreSQL 实例。
2. 使用运维人员单独安装的 PostgreSQL。
3. 可选使用容器化 PostgreSQL。
4. Windows 场景可选提供便携 PostgreSQL 包。

原因：

- 数据库是核心持久化组件，应便于备份、监控和升级。
- Linux/macOS 上系统包管理器或云数据库更稳定。
- 避免将数据库生命周期强绑定到应用安装目录。

安装脚本职责：

- 读取 PostgreSQL DSN。
- 检查连接可用性。
- 创建或验证目标数据库。
- 执行 `init-db.sql`。
- 执行数据库迁移。

## 统一目录结构

应用目录：

```text
process-opt-platform/
  bin/
  frontend/
    dist/
  config/
    config.ini
    config.example.ini
  db/
    init-db.sql
    migrations/
  logs/
  data/
    nats/
  backups/
  scripts/
  service/
  tmp/
```

目录说明：

- `bin/`：应用可执行文件和 NATS 二进制。
- `frontend/dist/`：前端构建产物，由 BackendAPI 托管。
- `config/`：配置文件和模板。
- `db/`：数据库初始化和迁移脚本。
- `logs/`：应用日志。
- `data/nats/`：JetStream 持久化数据。
- `backups/`：备份文件。
- `scripts/`：安装、卸载、升级辅助脚本。
- `service/`：生成的服务定义文件。
- `tmp/`：临时文件。

生产环境可将数据目录映射到系统数据目录。

## 配置设计

主配置文件：

- `config/config.ini`

配置项：

- `api.host`。
- `api.port`。
- `gateway.host`。
- `gateway.port`。
- `nats.url`。
- `nats.jetstream_domain`。
- `postgres.dsn`。
- `security.api_key`。
- `security.session_secret`。
- `logging.level`。
- `logging.path`。
- `analysis.max_samples`。
- `analysis.max_search_candidates`。
- `backup.path`。
- `service.user`。

安全要求：

- API Key、数据库密码、Session Secret 不写入日志。
- `platformctl doctor` 输出会脱敏 DSN 和密钥。
- 配置文件默认只允许服务运行用户读取。

## 服务设计

运行服务：

- `ProcessOptNATS`
- `ProcessOptConsumer`
- `ProcessOptGateway`
- `ProcessOptBackendAPI`

PostgreSQL 由外部实例管理，不默认注册为本系统服务。

启动顺序：

1. PostgreSQL 可连接。
2. NATS 启动。
3. Consumer 启动。
4. Gateway 启动。
5. BackendAPI 启动。

停止顺序：

1. Gateway 停止。
2. BackendAPI 停止。
3. Consumer 停止。
4. NATS 停止。

### Windows Service

Windows 使用服务管理器注册服务。

要求：

- 服务开机自启。
- 失败后自动重启。
- 日志写入应用日志目录。
- 可通过 `platformctl` 或系统服务管理器控制。

### Linux systemd

Linux 生成 systemd unit 文件。

要求：

- `Restart=always`。
- 指定工作目录。
- 指定运行用户。
- 服务依赖网络可用。
- 日志写入文件，同时可由 journal 查看。

### macOS launchd

macOS 生成 launchd plist。

要求：

- `KeepAlive=true`。
- 指定工作目录。
- 标准输出和错误输出写入日志目录。
- 使用 `launchctl` 加载和卸载。

## platformctl 设计

提供统一 CLI：

```text
platformctl start
platformctl stop
platformctl restart
platformctl status
platformctl logs
platformctl doctor
platformctl backup
platformctl restore
platformctl migrate
```

职责：

- 屏蔽 Windows Service、systemd、launchd 差异。
- 输出统一状态格式。
- 执行健康检查。
- 执行备份恢复。
- 执行数据库迁移。

## 健康检查

`platformctl doctor` 检查：

- 配置文件是否存在。
- 端口是否被占用。
- PostgreSQL 是否可连接。
- NATS 是否可连接。
- JetStream 是否启用。
- 数据库迁移版本是否最新。
- 服务是否运行。
- 日志目录是否可写。
- NATS 数据目录是否可写。
- 磁盘空间是否充足。
- API 健康接口是否正常。

检查结果分为：

- `OK`。
- `WARN`。
- `ERROR`。

## 日志设计

日志文件：

- `logs/gateway.log`
- `logs/consumer.log`
- `logs/backend-api.log`
- `logs/nats.log`
- `logs/platformctl.log`

要求：

- 按大小滚动。
- 保留最近若干份。
- 包含时间、级别、服务名、请求 ID 或消息 ID。
- 不记录密钥、数据库密码和完整连接串。

## 备份设计

备份内容：

- PostgreSQL dump。
- `config/` 目录。
- 数据库迁移版本信息。
- 关键日志索引。

备份命令：

```text
platformctl backup
```

备份文件命名：

```text
process-opt-backup-YYYYMMDD-HHMMSS.tar.gz
```

备份位置：

- 默认 `backups/`。
- 可通过 `backup.path` 配置。

## 恢复设计

恢复命令：

```text
platformctl restore <backup-file>
```

恢复流程：

1. 检查备份文件完整性。
2. 提示二次确认。
3. 停止 Gateway、BackendAPI、Consumer。
4. 恢复数据库。
5. 恢复配置文件。
6. 执行迁移校验。
7. 启动服务。
8. 执行 `doctor`。

恢复前必须提示会覆盖当前数据库和配置。

## 升级设计

升级流程：

1. 检查当前版本。
2. 执行 `platformctl doctor`。
3. 自动备份数据库和配置。
4. 停止服务。
5. 替换应用文件。
6. 保留现有 `config/config.ini`。
7. 执行数据库迁移。
8. 启动服务。
9. 执行 `platformctl doctor`。
10. 输出升级结果。

失败处理：

- 如果迁移前失败，保留旧版本。
- 如果迁移后失败，提示使用备份恢复。
- 保留升级日志。

## 数据库迁移

迁移脚本位于：

- `db/migrations/`

要求：

- 每个迁移有唯一版本号。
- 数据库记录已应用版本。
- 迁移按版本顺序执行。
- 迁移失败停止后续执行。
- 迁移日志写入 `logs/platformctl.log`。

## 安全边界

- 安装脚本不打印明文密钥。
- 日志不记录明文数据库密码。
- 配置文件权限最小化。
- 服务使用非管理员用户运行，除非平台限制。
- 管理命令需要本机权限。
- 默认不启用公网访问。

## 测试策略

### 安装测试

- Windows 安装包可完成安装和卸载。
- Linux tar.gz 安装脚本可注册 systemd。
- macOS tar.gz 安装脚本可注册 launchd。
- 三端安装后目录结构一致。

### 服务测试

- `platformctl start` 能启动全部服务。
- `platformctl stop` 能停止全部服务。
- `platformctl restart` 能重启服务。
- `platformctl status` 能显示服务状态。
- 服务异常退出后能自动重启。

### 配置测试

- 缺少配置文件时给出明确错误。
- PostgreSQL DSN 错误时 `doctor` 返回 ERROR。
- NATS 端口冲突时 `doctor` 返回 ERROR。
- 敏感配置在日志和 doctor 输出中脱敏。

### 备份恢复测试

- `platformctl backup` 生成备份文件。
- 备份文件包含数据库 dump 和配置。
- `platformctl restore` 可恢复数据库和配置。
- 恢复前必须二次确认。

### 升级测试

- 升级前自动备份。
- 配置文件升级后保留。
- 数据库迁移按版本执行。
- 升级后 `doctor` 返回 OK。

## 非目标

本阶段不实现：

- Kubernetes 部署。
- 多节点高可用。
- 云原生 Helm Chart。
- 自动公网 HTTPS 证书。
- 数据库主从复制。
- 桌面客户端。

## 后续扩展

- 增加 Docker Compose 生产部署模式。
- 增加 MSI 或 pkg 原生安装包。
- 增加远程升级工具。
- 增加自动定时备份。
- 增加监控指标导出。
