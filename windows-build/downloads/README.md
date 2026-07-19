# 依赖下载清单

打包前请将以下 4 个文件下载到本目录 (`windows-build/downloads/`)。

## 1. Python 3.11 Embeddable (Windows x64)

- **文件名**：`python-3.11.9-embed-amd64.zip`（或更新的 3.11.x）
- **下载**：https://www.python.org/downloads/windows/
- 选择 "Windows embeddable package (64-bit)"
- 直链示例：https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
- 大小：约 10 MB

## 2. PostgreSQL 15 Windows Binaries

- **文件名**：`postgresql-15.8-1-windows-x64-binaries.zip`（或更新的 15.x）
- **下载**：https://www.enterprisedb.com/download-postgresql-binaries
- 选择 "Windows x86-64" 的 15.x 版本
- 大小：约 90 MB（zip），解压后 280 MB

## 3. NATS Server

- **文件名**：`nats-server-v2.10.22-windows-amd64.zip`（或更新的 2.10.x）
- **下载**：https://github.com/nats-io/nats-server/releases
- 找到 v2.10.x → Assets → `nats-server-v2.10.x-windows-amd64.zip`
- 大小：约 6 MB

## 4. NSSM (Non-Sucking Service Manager)

- **文件名**：`nssm-2.24.zip`
- **下载**：https://nssm.cc/release/nssm-2.24.zip
- 大小：约 300 KB

## 5. get-pip.py (Python 包管理器引导脚本)

- **文件名**：`get-pip.py`
- **下载**：https://bootstrap.pypa.io/get-pip.py
- 大小：约 2 MB

## 验证清单

下载完成后，`downloads/` 目录应包含：

```
downloads/
├── python-3.11.9-embed-amd64.zip
├── postgresql-15.8-1-windows-x64-binaries.zip
├── nats-server-v2.10.22-windows-amd64.zip
├── nssm-2.24.zip
├── get-pip.py
└── README.md (本文件)
```

版本号可以更新（例如 3.11.10、15.9），但 **major.minor 版本必须保持** (Python 3.11.x，PostgreSQL 15.x，NATS 2.10.x)。build-package.py 会用通配符匹配。
