## 概述

设备通过 HTTP POST 向网关上报工艺参数和检测结果。网关验证 API Key 后将消息发布到 NATS JetStream，由消费者写入 PostgreSQL。

| 项目 | 值 |
|------|-----|
| **网关地址** | `http://{host}:8001` |
| **认证方式** | HTTP Header `X-API-Key` |
| **内容类型** | `application/json` |

---

## 上报工艺参数

**POST** `/api/v1/data/process`

```json
{
  "message_id": "uuid-string",
  "barcode": "PRODUCT-001",
  "device_id": "reflow-oven",
  "processed_at": "2026-06-13T10:00:00Z",
  "params": {
    "temperature": 223.5,
    "conveyor_speed": 48.2,
    "oxygen_ppm": 187
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message_id` | string | 是 | 消息唯一 ID |
| `barcode` | string | 是 | 产品条码 |
| `device_id` | string | 是 | 设备标识 |
| `processed_at` | ISO 8601 | 是 | 处理时间 |
| `params` | object | 是 | 工艺参数键值对（数值型） |

### 设备类型与参数

**reflow-oven** (回流焊炉)

| 参数 | 范围 | 单位 |
|------|------|------|
| `temperature` | 100–300 | °C |
| `conveyor_speed` | 10–100 | cm/min |
| `oxygen_ppm` | 0–1000 | ppm |

**injection-molder** (注塑机)

| 参数 | 范围 | 单位 |
|------|------|------|
| `melt_temp` | 150–350 | °C |
| `injection_pressure` | 50–200 | MPa |
| `cooling_time` | 5–60 | s |

---

## 上报检测结果

**POST** `/api/v1/data/inspection`

```json
{
  "message_id": "uuid-string",
  "barcode": "PRODUCT-001",
  "station_id": "reflow-oven-qa",
  "inspected_at": "2026-06-13T10:05:00Z",
  "results": {
    "solder_joint_quality": "pass",
    "voiding_pct": "pass"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message_id` | string | 是 | 消息唯一 ID |
| `barcode` | string | 是 | 产品条码（与工艺参数一致） |
| `station_id` | string | 是 | 质检工位标识 |
| `inspected_at` | ISO 8601 | 是 | 检测时间 |
| `results` | object | 是 | 检测结果键值对（pass/fail） |

---

## 模拟数据工具

命令行工具 `process-opt-mock` 用于生成和上报模拟数据：

```bash
# 批量上报 100 条 reflow-oven 数据
process-opt-mock seed --count 100 --api-key change-me

# 批量上报 500 条注塑机数据
process-opt-mock seed --count 500 --device-type injection-molder --api-key change-me

# 持续流式上报（每 5 秒一条）
process-opt-mock stream --interval 5 --api-key change-me
```

---

## HTTP 状态码说明

| 状态码 | 含义 |
|--------|------|
| 202 | 消息已接收 |
| 401 | API Key 无效 |
| 422 | 请求参数不合法 |
| 500 | 服务器内部错误 |
