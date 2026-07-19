# Windows 安装包构建指南

本指南介绍如何为「工艺参数在线分析与调优系统」生成 Windows x64 安装程序（`.exe`）。

## 一、构建环境要求

**必须在 Windows x64 主机上构建**（因为需要嵌入式 Python for Windows + PostgreSQL Windows Binaries）。

| 项 | 要求 | 备注 |
|---|---|---|
| 操作系统 | Windows 10 / 11 / Server 2019+ x64 | |
| Python | 3.11.x x64 (系统安装) | 用于运行 build-package.py |
| Node.js | 18+ / 20+ | 用于 npm run build 前端 |
| Inno Setup | 6.2+ | 生成 setup.exe |
| 磁盘空间 | 至少 3 GB | 中间产物 + 输出 |

## 二、目录结构

```
windows-build/
├── build-scripts/
│   ├── compile-pyc.py         # Python 源码编译成 .pyc
│   └── build-package.py       # 主打包脚本
├── installer-scripts/
│   ├── installer.iss          # Inno Setup 脚本
│   ├── init-db.bat            # 首次安装：初始化 PostgreSQL
│   ├── install-services.bat   # 注册 5 个 Windows 服务
│   ├── uninstall-services.bat # 卸载服务
│   ├── start-all.bat          # 启动服务
│   ├── stop-all.bat           # 停止服务
│   ├── seed-data.bat          # 灌入 Mock 数据
│   ├── open-web.bat           # 打开 http://localhost:8000
│   ├── pg-password.txt        # PostgreSQL 初始密码
│   └── README.txt             # 用户可见的说明文件
├── downloads/                 # 依赖二进制（首次准备时下载）
│   └── README.md              # 下载清单
├── build/                     # 构建产物 (.gitignore)
│   ├── ProcessOpt/            # 完整安装树
│   └── output/                # 生成的 setup.exe
└── build-windows.md           # 本文件
```

## 三、构建步骤

### 步骤 1：准备依赖（首次）

按 [downloads/README.md](downloads/README.md) 下载 5 个文件放入 `downloads/` 目录：

- `python-3.11.x-embed-amd64.zip`
- `postgresql-15.x-x-windows-x64-binaries.zip`
- `nats-server-v2.10.x-windows-amd64.zip`
- `nssm-2.24.zip`
- `get-pip.py`

安装 Inno Setup 6.2+ 到默认位置：
- 下载：https://jrsoftware.org/isdl.php

### 步骤 2：构建前端

```powershell
cd web
npm install
npm run build
```

产物在 `web\dist\`。

### 步骤 3：运行打包脚本

```powershell
cd windows-build\build-scripts
python build-package.py
```

打包脚本会依次完成：

1. 清理 `build\`
2. 解压嵌入式 Python 到 `build\ProcessOpt\app\python\`
3. 用 `get-pip.py` 引导 pip
4. 安装项目依赖到 `build\ProcessOpt\app\lib\site-packages\`（含 scipy/sklearn 等）
5. 编译 `src/process_opt/` 全部 `.py` 为 `.pyc`
6. 复制到 `build\ProcessOpt\app\process_opt\`
7. 复制 `web/dist/`、`db/migrations/`、`.env` 模板
8. 解压 PostgreSQL 到 `build\ProcessOpt\postgresql\`
9. 解压 NATS 到 `build\ProcessOpt\nats\`
10. 解压 NSSM 到 `build\ProcessOpt\nssm\`
11. 复制 `installer-scripts\*.bat` 到 `build\ProcessOpt\scripts\`

耗时：约 5-10 分钟（视网络速度而定，pip 下载依赖占大头）。

### 步骤 4：生成 setup.exe

用 Inno Setup Compiler 打开 `installer-scripts\installer.iss` → 菜单 **Build → Compile**。

生成物：`build\output\ProcessOpt-Setup-0.1.0-x64.exe`（约 230 MB）

## 四、一键构建脚本（可选）

创建 `windows-build\build-all.bat`：

```bat
@echo off
cd /d %~dp0
echo === Step 1: Build frontend ===
cd ..\web
call npm install
call npm run build
if errorlevel 1 exit /b 1

echo === Step 2: Package application ===
cd ..\windows-build\build-scripts
python build-package.py
if errorlevel 1 exit /b 1

echo === Step 3: Build installer ===
cd ..\installer-scripts
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if errorlevel 1 exit /b 1

echo === Done: build\output\ ===
dir ..\build\output
```

运行：`build-all.bat`

## 五、安装包验证

在**干净的 Windows 虚拟机**上测试：

1. 双击 `ProcessOpt-Setup-0.1.0-x64.exe`
2. 按向导安装到 `C:\Program Files\ProcessOpt\`
3. 安装完成勾选「启动后打开系统」
4. 浏览器自动打开 `http://localhost:8000`
5. 编辑 `C:\Program Files\ProcessOpt\app\.env` 填 API Key
6. 通过服务管理器重启 `ProcessOptApi`（或 `stop-all.bat` + `start-all.bat`）
7. 开始菜单 →「导入测试数据」灌入 5000 条 Mock 数据
8. 页面应看到设备列表和分析数据

## 六、常见问题

### Q1: pip 安装依赖时下载慢或失败

`build-package.py` 已默认使用清华镜像源。如需切换：编辑 `build-package.py` 中 `--index-url` 参数。

### Q2: PostgreSQL 服务启动失败

查看日志：`C:\Program Files\ProcessOpt\logs\postgres.log`

常见原因：
- 端口 5432 被占用（先卸载已有 PostgreSQL 或修改配置）
- 数据目录权限不足（`init-db.bat` 会设置 `Users: modify`）

### Q3: API 返回 500，agent 报错

检查 `.env` 中的 `AGENT_API_KEY` 是否正确填写。修改后须重启 `ProcessOptApi` 服务。

### Q4: 如何自定义端口

1. 编辑 `app\.env` 中的 `PROCESS_OPT_API_PORT` / `PROCESS_OPT_GATEWAY_PORT`
2. 修改 `installer.iss` 中 `IsPortInUse` 检查的端口
3. 修改 `install-services.bat` 中 NATS `-p` 参数
4. 修改 `init-db.bat` 中 `postgresql.conf` 的 `port`

### Q5: 卸载时数据保留

卸载器会弹窗询问「是否保留业务数据库」：
- 选**是**：保留 `postgresql\data\`（下次安装继续用）
- 选**否**：完全删除

### Q6: 生成的 exe 被杀毒软件误报

- 用代码签名证书签署 setup.exe
- 或将 Inno Setup 目录加入杀毒软件白名单

## 七、发布清单

发布前完成：

- [ ] 更新 `pyproject.toml` 版本号
- [ ] 更新 `installer.iss` 中 `AppVersion`
- [ ] 更新 `build-package.py` 中 `VERSION` 文件内容
- [ ] 在干净虚拟机上完整测试安装/卸载/升级
- [ ] 用代码签名证书签署 setup.exe（生产环境）
- [ ] 计算 SHA256：`certutil -hashfile ProcessOpt-Setup-0.1.0-x64.exe SHA256`
- [ ] 发布到内网文件服务器 / OSS

## 八、目录结构预览（安装后）

```
C:\Program Files\ProcessOpt\
├── app\                              # 应用主体 ~230 MB
│   ├── python\                       # 嵌入式 Python
│   ├── lib\site-packages\            # 第三方依赖
│   ├── process_opt\                  # ★ .pyc 编译产物（无 .py 源码）
│   ├── web\dist\                     # 前端静态资源
│   ├── db\migrations\                # SQL 迁移
│   └── .env                          # 配置
├── postgresql\                       # PostgreSQL 15 ~280 MB
│   └── data\                         # 数据库文件（首次 initdb 生成）
├── nats\                             # NATS 消息队列
├── nssm\                             # 服务管理器
├── scripts\                          # 管理批处理脚本
├── logs\                             # 运行日志
├── README.txt                        # 用户说明
└── unins000.exe                      # Inno Setup 卸载器
```

安装后 5 个 Windows 服务自动启动：`ProcessOptPostgres` / `ProcessOptNats` / `ProcessOptGateway` / `ProcessOptConsumer` / `ProcessOptApi`。
