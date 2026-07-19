工艺参数在线分析与调优系统 v0.1.0
================================================================

★ 系统访问
  安装完成后，服务会自动启动。打开浏览器访问：
    http://localhost:8000

★ 首次使用配置
  1. 编辑 app\.env 填写 AGENT_API_KEY（大模型 API Key）
  2. 通过开始菜单「重启服务」使配置生效

★ 常用操作（开始菜单 → 工艺参数在线分析与调优系统）
  • 打开系统       — 浏览器打开管理界面
  • 启动服务       — 手动启动全部后台服务
  • 停止服务       — 手动停止全部后台服务
  • 导入测试数据   — 一键灌入 5000 条 Mock 数据
  • 查看日志       — 打开 logs 目录
  • 编辑配置       — 打开 .env 配置文件
  • 卸载           — 完整卸载系统

★ Windows 服务
  安装后自动注册并启动 5 个服务：
    ProcessOptPostgres    数据库（端口 5432）
    ProcessOptNats        消息队列（端口 4222）
    ProcessOptGateway     数据网关（端口 8001）
    ProcessOptConsumer    数据消费
    ProcessOptApi         Web 服务（端口 8000）

★ 数据备份
  停止服务后，备份以下两个目录即可：
    postgresql\data\      业务数据
    app\.env              配置文件

★ 端口占用问题
  如 5432/4222/8000/8001 被占用，编辑 .env 修改端口，
  并同步修改「注册表 HKLM\SYSTEM\CurrentControlSet\Services\ProcessOpt*」
  的 ImagePath 或使用 nssm.exe edit 命令。

★ 系统要求
  • Windows 10/11 x64 或 Windows Server 2019+
  • 至少 4 GB 内存
  • 至少 2 GB 磁盘空间

★ 技术支持
  日志文件：安装目录\logs\
