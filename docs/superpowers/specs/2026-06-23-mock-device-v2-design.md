# 工艺装备模拟器 V2 技术设计

## 背景

现有 `process-opt-mock` (2026-06-13) 是一个 CLI 工具，仅支持单向随机数据推送（seed/stream 模式）。需要升级为支持双向交互、多设备管理、机理驱动的 Web 端装备模拟器。

## 设计目标

- **Web 端多设备管理**：在网页上创建、配置、启停多个模拟设备，查看实时状态
- **双向交互**：设备能接收实验计划、参数配置，能执行任务并反馈结果
- **机理模型驱动**：试验结果基于工艺类型 + 领域机理逻辑生成，非纯随机
- **与现有系统零冲突**：复用 Gateway 和 Backend API，模拟设备行为与真实设备一致

## 整体架构

```
┌───────────────────────────────────────────────────────────────┐
│                    Browser                                     │
│  /mock-devices (新增) ← Element Plus 卡片网格 + SSE 实时推送  │
└─────────────────────┬─────────────────────────────────────────┘
                      │
        /api/v1/mock/* (新增路由组)
                      │
┌─────────────────────┴─────────────────────────────────────────┐
│                  Backend API (:8000)                            │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  MockManager (单例，lifespan 中初始化)                    │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  devices: dict[device_id, MockDevice]              │  │ │
│  │  │  create / delete / start / pause / stop / config   │  │ │
│  │  └──────────────┬─────────────────────────────────────┘  │ │
│  │                 │                                         │ │
│  │  ┌──────────────┴─────────────────────────────────────┐  │ │
│  │  │  MockDevice (每个设备一个实例)                      │  │ │
│  │  │                                                    │  │ │
│  │  │  state: idle | running | paused                    │  │ │
│  │  │  current_params: dict                              │  │ │
│  │  │  experiment_queue: asyncio.Queue                   │  │ │
│  │  │  event_queue: asyncio.Queue → SSE                  │  │ │
│  │  │                                                    │  │ │
│  │  │  [running 时并发 4 个 asyncio.Task]                │  │ │
│  │  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ │  │ │
│  │  │  │Heartbeat│ │ReportData│ │PollTask│ │ExecuteExp│ │  │ │
│  │  │  │30s/GW   │ │N s/GW    │ │30s/API │ │event/API │ │  │ │
│  │  │  └─────────┘ └──────────┘ └────────┘ └─────────┘ │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  │                                                           │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  MechanismEngine                                    │  │ │
│  │  │  ┌────────┐ ┌──────────┐ ┌────────┐ ...             │  │ │
│  │  │  │回流焊  │ │注塑成型  │ │固化炉  │                 │  │ │
│  │  │  └────────┘ └──────────┘ └────────┘                 │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│       httpx → Gateway (:8001) → NATS → Consumer → DB           │
│       httpx → Backend API (:8000) self-call                     │
└─────────────────────────────────────────────────────────────────┘
```

## 设备生命周期

```
[创建] → IDLE → [启动] → RUNNING
              ▲              │
              │              │ [暂停/异常]
              │              ▼
              └── [恢复] ── PAUSED
                              │
                              ▼ [停止]
                            IDLE
                              │
                              ▼ [删除]
                            (销毁)
```

| 状态 | 含义 | 行为 |
|------|------|------|
| **IDLE** | 已创建未运行 | 已注册到 device_registry，只接收配置，不发数据 |
| **RUNNING** | 正常运行 | 心跳 30s + 数据上报 + 轮询任务 + 实验执行 |
| **PAUSED** | 暂停中 | 保持注册状态，停止所有上报，可恢复 |

**操作效果**：

- **创建**：写入 device_registry（如不存在），创建 MockDevice 实例，状态 IDLE
- **删除**：停止所有 Task，从 MockManager 移除，device_registry 记录保留（历史数据可追溯）
- **启动/暂停/停止**：即时生效，状态变更通过 SSE 推送前端

## 四个常驻任务

### HeartbeatTask (30s)

POST 到 Gateway `/api/v1/data/process`：

```json
{
  "message_id": "hb-reflow-oven-005-1719234000",
  "barcode": "_heartbeat_",
  "device_id": "reflow-oven-005",
  "processed_at": "2026-06-23T10:00:00Z",
  "params": {
    "_heartbeat": true,
    "status": "running",
    "current_params": {"temperature": 245, "conveyor_speed": 55},
    "last_result_summary": {"pass": 8, "fail": 2}
  }
}
```

`barcode: "_heartbeat_"` 为特殊标记，consumer 可根据此字段跳过或单独存储心跳记录。

### ReportDataTask (可配间隔，默认 60s)

1. 用 `current_params`（加小噪声，模拟工艺波动）构造 `ProcessMessage`
2. 调用 `MechanismEngine.simulate(device_type, params)` → 构造 `InspectionMessage`
3. `send_pair()` 发送 process + inspection 到 Gateway
4. 可配置使用机理模型还是模板随机生成

### PollTask (30s)

1. `GET /api/v1/experiment/plans?status=draft&process_type={type}` → 发现新计划 → 自动分配，入队 `experiment_queue`
2. `GET /api/v1/parameters/{device_type}/latest` → 发现新版本参数 → 更新 `current_params`，POST 确认回执到 `parameter_confirmations`

### ExecuteExpTask (事件驱动)

循环从 `experiment_queue` 获取实验计划：

1. 遍历 `design_runs`，每条 run 提取 factor 值注入 `current_params`
2. `MechanismEngine.simulate(device_type, params)` → 得检测结果
3. 提取 `response_name` 对应的结果值
4. `POST /api/v1/experiment/plans/{id}/results` 上报单条结果
5. 推送 SSE: `experiment.progress`
6. 全部完成 → 推送 `experiment.complete`

## 机理引擎

### 模块结构

```
src/process_opt/mock/mechanism/
  __init__.py           # 注册表 + get_mechanism(device_type) 工厂
  base.py               # BaseMechanism 抽象类 + ParamSpec, ResultSpec
  reflow_oven.py        # 回流焊模型
  injection_molder.py   # 注塑成型模型
  oven_curing.py        # 固化炉模型
  cnc_drill.py          # CNC钻孔模型
  coating_machine.py    # 涂覆机模型
```

### 基类接口

```python
class MechanismModel(ABC):
    param_spec: ClassVar[dict[str, ParamSpec]]    # 输入参数定义
    result_spec: ClassVar[list[ResultSpec]]        # 输出结果定义

    @abstractmethod
    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        """输入工艺参数 → 输出检测结果（机理公式 + 可控噪声）"""
```

### 五种工艺机理模型

| 工艺 | 核心机理 | 输入参数 | 输出结果 |
|------|---------|---------|---------|
| 回流焊 (reflow-oven) | 热输入积分模型 | temperature, conveyor_speed, oxygen_ppm | solder_joint_quality, voiding_pct |
| 注塑成型 (injection-molder) | 简化 PVT 收缩模型 | melt_temp, injection_pressure, cooling_time | dimensional_accuracy, flash_present |
| 固化炉 (oven-curing) | Arrhenius 固化动力学 | oven_temp, cure_duration_min, humidity_pct, airflow_rate | cure_complete, weight_loss_pct |
| CNC钻孔 (cnc-drill) | 切削参数影响模型 | spindle_speed, feed_rate, drill_depth, coolant_flow | hole_accuracy, surface_roughness_ra |
| 涂覆机 (coating-machine) | 喷涂均匀性模型 | spray_pressure, coating_thickness_um, cure_temp, conveyor_speed | coating_uniformity, bubble_count |

### 示例：回流焊机理模型

```python
class ReflowOvenModel(MechanismModel):
    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        temp = params["temperature"]
        speed = params["conveyor_speed"]
        oxygen = params["oxygen_ppm"]

        # 热输入量 = f(温度, 速度)，理想区间 [target_low, target_high]
        heat_input = temp / speed * 10
        ideal = 240 / 50 * 10  # = 48
        quality = 1.0 - abs(heat_input - ideal) / ideal * 0.8

        # 空洞率：温度和氧含量共同影响
        voiding = 0.5 + (temp - 240) * 0.02 + oxygen * 0.003

        # 可控噪声（模拟测量误差）
        quality += random.gauss(0, 0.02)
        voiding += random.gauss(0, 0.1)

        return [
            InspectionItem(name="solder_joint_quality", value=round(quality, 2),
                           usl=1.5, lsl=0.5,
                           result="pass" if 0.5 <= quality <= 1.5 else "fail"),
            InspectionItem(name="voiding_pct", value=round(voiding, 2),
                           usl=5.0, lsl=0.0,
                           result="pass" if voiding <= 5.0 else "fail"),
        ]
```

### 与现有 DEVICE_TEMPLATES 的关系

- 现有 `DEVICE_TEMPLATES` 保留，用于 `seed` / `stream` CLI 模式的随机数据生成
- 机理模型是另一条路径，用于实验执行（必须）和常规数据上报（可配）
- 两种模式共享 `InspectionItem` 数据类型和 Gateway 发送路径

## API 路由设计

### REST 端点

| Method | Path | 功能 |
|--------|------|------|
| `GET` | `/api/v1/mock/devices` | 列出所有模拟设备及状态 |
| `POST` | `/api/v1/mock/devices` | 创建模拟设备 |
| `GET` | `/api/v1/mock/devices/{id}` | 获取设备详情 |
| `DELETE` | `/api/v1/mock/devices/{id}` | 删除模拟设备 |
| `POST` | `/api/v1/mock/devices/{id}/start` | 启动设备模拟 |
| `POST` | `/api/v1/mock/devices/{id}/pause` | 暂停设备模拟 |
| `POST` | `/api/v1/mock/devices/{id}/stop` | 停止设备模拟 |
| `PUT` | `/api/v1/mock/devices/{id}/params` | 更新设备工艺参数 |
| `POST` | `/api/v1/mock/devices/{id}/experiments` | 分配实验计划到设备 |
| `GET` | `/api/v1/mock/devices/{id}/events` | SSE 实时事件流 |

### 请求/响应样例

**创建设备**：

```json
// POST /api/v1/mock/devices
{
  "device_id": "reflow-oven-005",
  "device_type": "reflow-oven",
  "name": "回流焊 5号",
  "line_id": "L1",
  "report_interval": 60
}
// → 201 {"device_id":"reflow-oven-005","device_type":"reflow-oven","status":"idle","line_id":"L1"}
```

**更新参数**：

```json
// PUT /api/v1/mock/devices/reflow-oven-005/params
{
  "temperature": 245,
  "conveyor_speed": 55,
  "oxygen_ppm": 180
}
// → 200 {"device_id":"reflow-oven-005","current_params":{...},"confirmed":true}
```

**分配实验**：

```json
// POST /api/v1/mock/devices/reflow-oven-005/experiments
{ "plan_id": 3 }
// → 202 {"plan_id":3,"total_runs":9,"status":"queued"}
```

**列出设备**：

```json
// GET /api/v1/mock/devices
{
  "devices": [
    {
      "device_id": "reflow-oven-005",
      "device_type": "reflow-oven",
      "name": "回流焊 5号",
      "status": "running",
      "line_id": "L1",
      "line_name": "PCBA-A线",
      "report_interval": 60,
      "last_heartbeat": "2026-06-23T10:00:02Z",
      "report_count": 128,
      "current_experiment": {"plan_id": 3, "run_order": 5, "total_runs": 9}
    }
  ],
  "summary": {"running": 3, "paused": 1, "idle": 0}
}
```

### SSE 事件类型

```
event: status
data: {"device_id":"reflow-oven-005","status":"running"}

event: heartbeat
data: {"device_id":"reflow-oven-005","status":"running","current_params":{"temperature":245,...}}

event: experiment.progress
data: {"device_id":"reflow-oven-005","plan_id":3,"run_order":5,"total_runs":9,"result":"pass"}

event: experiment.complete
data: {"device_id":"reflow-oven-005","plan_id":3,"pass":7,"fail":2}

event: data.reported
data: {"device_id":"reflow-oven-005","barcode":"...","quality":"pass"}

event: error
data: {"device_id":"reflow-oven-005","message":"Gateway unreachable, retrying..."}
```

## 前端设计

### 路由

Vue Router 新增 `/mock-devices`，导航栏新增「装备模拟」入口。

### 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  工艺装备模拟器                         [+ 添加设备]         │
│                                                             │
│  ┌─── 概览 ─────────────────────────────────────────────┐  │
│  │  🟢 运行中: 3   🟡 暂停: 1   ⚪ 空闲: 0            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────┐ ┌──────────────────┐                 │
│  │ 🟢 reflow-oven   │ │ 🟢 injection     │                 │
│  │    -001          │ │    -001          │                 │
│  │ 产线: PCBA-A线   │ │ 产线: 注塑-A线   │                 │
│  │ 心跳: 2s前       │ │ 心跳: 8s前       │                 │
│  │ 上报: 128条      │ │ 上报: 96条       │                 │
│  │ 实验: 1个进行中  │ │ 实验: 无         │                 │
│  │ ──────────────── │ │ ──────────────── │                 │
│  │ [参数配置][实验] │ │ [参数配置][实验] │                 │
│  │ [⏸暂停] [🛑停止]│ │ [⏸暂停] [🛑停止]│                 │
│  └──────────────────┘ └──────────────────┘                 │
│                                                             │
│  ┌──────────────────┐ ┌──────────────────┐                 │
│  │ 🟡 oven-curing   │ │ 🟢 cnc-drill     │                 │
│  │    -001          │ │    -001          │                 │
│  │ ...              │ │ ...              │                 │
│  └──────────────────┘ └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### 组件树

```
MockDevices.vue
  ├─ DeviceCard.vue            # 设备卡片（状态指示灯、统计、操作按钮）
  ├─ AddDeviceDialog.vue       # 创建设备弹窗
  ├─ DeviceConfigDrawer.vue    # 参数配置侧边抽屉
  └─ ExperimentPanel.vue       # 实验任务面板（侧边抽屉）
```

### 交互说明

- **添加设备**：弹窗选择工艺类型、产线、输入编号后缀、配置上报间隔
- **参数配置**：侧边抽屉展示所有工艺参数（key/当前值/单位/范围），可编辑提交
- **实验面板**：列出待执行实验 → 点击分配 → 显示进度条和每条结果 → 历史记录
- **实时状态**：SSE 推送，卡片指示灯/心跳时间动态更新
- **删除确认**：二次确认弹窗，提示"历史数据保留"

## 新增文件清单

```
后端:
  src/process_opt/mock/manager.py              # MockManager
  src/process_opt/mock/device.py               # MockDevice
  src/process_opt/mock/mechanism/__init__.py   # 机理引擎注册表
  src/process_opt/mock/mechanism/base.py       # 基类 + 数据类型
  src/process_opt/mock/mechanism/reflow_oven.py
  src/process_opt/mock/mechanism/injection_molder.py
  src/process_opt/mock/mechanism/oven_curing.py
  src/process_opt/mock/mechanism/cnc_drill.py
  src/process_opt/mock/mechanism/coating_machine.py
  src/process_opt/api/mock_routes.py           # REST + SSE 路由

前端:
  web/src/views/MockDevices.vue                # 页面
  web/src/components/mock/DeviceCard.vue       # 设备卡片
  web/src/components/mock/AddDeviceDialog.vue  # 添加弹窗
  web/src/components/mock/DeviceConfigDrawer.vue
  web/src/components/mock/ExperimentPanel.vue
```

## 非目标 (V2)

- 不模拟 HTTP 以外的协议（MQTT、OPC UA 等）
- 不做 NATS 直连（始终走 Gateway API）
- 不持久化 Mock 设备状态（重启后需重新创建）
- 剩余 7 种工艺类型暂不做机理模型，沿用 DEVICE_TEMPLATES 随机生成
