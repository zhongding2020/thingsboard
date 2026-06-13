# Mock Device Simulator 技术设计

## 背景

为开发、测试、演示提供可重复的工艺参数和检测数据生成工具。

## 设计目标

- 两种运行模式：一次性 seed 和持续 stream。
- 内置两种设备模板，模拟真实制造场景。
- 数据在合理范围内随机波动，检测结果与参数弱相关。
- 约 5% 异常值用于测试异常检测。
- 通过 CLI 命令调用，直接向 Gateway 发送数据。

## 运行模式

### seed 模式

`process-opt-mock seed --count 100`

生成指定数量的历史数据，直接通过 HTTP POST 发送到 Gateway。每条数据包含工艺参数和检测结果，时间戳随机分布在过去 7 天内。用于填充数据库用于分析演示。

### stream 模式

`process-opt-mock stream --interval 5`

持续以指定间隔（秒）发送数据。每轮发送一组工艺参数 + 一组检测结果。打印每轮统计。按 Ctrl+C 停止。

## 设备模板

### 回流焊炉（`reflow-oven`）

工艺参数：

| 参数 | 单位 | 范围 | 正态分布参数 |
|------|------|------|-------------|
| temperature | C | 180-260 | μ=230, σ=15 |
| conveyor_speed | cm/min | 50-120 | μ=85, σ=15 |
| oxygen_level | ppm | 200-1500 | μ=500, σ=200 |

检测指标（与温度弱相关，温度过高 → 合格率下降）：

| 指标 | 单位 | 范围 | 与参数相关性 |
|------|------|------|-------------|
| solder_quality | % | 85-99 | 负相关于 temperature，正相关于 conveyor_speed |
| bridge_rate | % | 0-5 | 正相关于 temperature，负相关于 oxygen_level |

### 注塑机（`injection-molder`）

工艺参数：

| 参数 | 单位 | 范围 | 正态分布参数 |
|------|------|------|-------------|
| melt_temp | C | 180-260 | μ=220, σ=20 |
| injection_pressure | MPa | 50-180 | μ=120, σ=30 |
| cooling_time | s | 10-40 | μ=25, σ=6 |

检测指标（与参数弱相关）：

| 指标 | 单位 | 范围 | 与参数相关性 |
|------|------|------|-------------|
| tensile_strength | MPa | 40-80 | 正相关于 injection_pressure |
| warpage | mm | 0.1-2.0 | 负相关于 cooling_time |

## 数据生成逻辑

### 工艺参数生成

```python
def generate_params(device_type: str) -> dict:
    template = TEMPLATES[device_type]
    params = {}
    for key, cfg in template["params"].items():
        value = random.gauss(cfg["mu"], cfg["sigma"])
        value = clamp(value, cfg["min"], cfg["max"])
        value = round(value, cfg["precision"])
        if random.random() < 0.05:  # 5% 异常值
            value = random.uniform(cfg["min"], cfg["max"] * 0.3)  # 极端低值
            value = round(value, cfg["precision"])
        params[key] = value
    return params
```

### 检测结果生成

检测结果在参数的基础上加入相关性计算和随机噪声：

- `solder_quality` = 基准值(95) - (temperature - 230) * 0.05 + (conveyor_speed - 85) * 0.02 + 随机噪声
- `bridge_rate` = 基准值(1.5) + (temperature - 230) * 0.01 - (oxygen_level - 500) * 0.001 + 随机噪声
- `tensile_strength` = 基准值(60) + (injection_pressure - 120) * 0.15 + 随机噪声
- `warpage` = 基准值(1.0) - (cooling_time - 25) * 0.02 + 随机噪声

噪声为标准差为 2-5% 范围的高斯分布。

### 条码格式

`{device_type}-{YYYYMMDD}-{序列号}`，如 `reflow-oven-20260613-00001`。

seed 模式下序列号从 00001 递增。stream 模式下使用时间戳毫秒。

## 配置

所有参数可通过 CLI 参数覆盖：

- `--gateway-url`：默认 `http://localhost:8001`
- `--api-key`：默认 `dev-api-key`
- `--device-type`：默认 `reflow-oven`
- `--interval`：stream 模式间隔秒数，默认 5
- `--count`：seed 模式数量，默认 100
- `--start-date`：seed 模式起始时间

## CLI 命令设计

```bash
process-opt-mock seed [--count 100] [--device-type reflow-oven] [--gateway-url http://localhost:8001] [--api-key dev-api-key] [--start-date 2026-06-01]

process-opt-mock stream [--interval 5] [--device-type reflow-oven] [--gateway-url http://localhost:8001] [--api-key dev-api-key]
```

## 输出

seed 模式输出：

```
Sending 100 records for reflow-oven...
  25/100 - last barcode: reflow-oven-20260613-00025 (202 OK)
  50/100 - last barcode: reflow-oven-20260613-00050 (202 OK)
  ...
Done. Sent 100 process + 100 inspection records in 12.3s.
```

stream 模式输出：

```
Streaming reflow-oven to http://localhost:8001 (Ctrl+C to stop)
  [10:32:01] sent pair 1: barcode=reflow-oven-20260613-abc123, temp=231.5C, quality=94.2%
  [10:32:06] sent pair 2: barcode=reflow-oven-20260613-def456, temp=245.1C, quality=91.8%
  ...
```

## 错误处理

- Gateway 不可用 → 打印错误并等待后重试（stream 模式）或终止（seed 模式）。
- 非 202 响应 → 打印响应内容和状态码。
- 异常值不特殊处理，只记录。

## 实现文件

```text
src/process_opt/mock/__init__.py
src/process_opt/mock/templates.py      # 设备模板配置
src/process_opt/mock/generator.py      # 数据生成逻辑
src/process_opt/mock/sender.py         # HTTP 发送和重试
src/process_opt/mock/cli.py            # CLI 入口 (seed/stream)
```

## 非目标

- 不模拟 TCP/MQTT 等非 HTTP 协议。
- 不做设备到 NATS 的直接发布（始终走 Gateway API）。
- 不做参数推荐验证（只生成数据）。
