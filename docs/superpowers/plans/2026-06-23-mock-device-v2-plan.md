# 工艺装备模拟器 V2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Web 端多设备工艺装备模拟器，支持创建/启停/配置模拟设备，通过 5 种工艺机理模型生成真实感实验数据

**Architecture:** MechanismEngine (纯函数模型层) → MockDevice (asyncio 任务编排) → MockManager (设备生命周期) → REST + SSE API → Vue 3 前端页面

**Tech Stack:** Python 3.11+, asyncio, httpx, Pydantic, FastAPI + SSE, Vue 3 + Element Plus + TypeScript

## Global Constraints

- 机理模型覆盖 5 种工艺：回流焊、注塑成型、固化炉、CNC钻孔、涂覆机
- 设备生命周期：idle → running → paused，操作即时生效
- 模拟设备始终通过 Gateway HTTP API 上报数据（不走 NATS 直连）
- 后端 SSE 事件类型使用 `status` / `heartbeat` / `experiment.progress` / `experiment.complete` / `data.reported` / `error`
- 前端使用 Element Plus 组件，路由 `/mock-devices`，导航栏新增「装备模拟」入口
- 所有后端测试使用 pytest + httpx AsyncClient，前端类型检查 `npm run typecheck` 零错误

---

### Task 1: 机理模型基类 + 注册表

**Files:**
- Create: `src/process_opt/mock/mechanism/__init__.py`
- Create: `src/process_opt/mock/mechanism/base.py`
- Create: `tests/mock/test_mechanism_base.py`

**Interfaces:**
- Consumes: `process_opt.common.schemas.InspectionItem`
- Produces:
  - `MechanismModel` ABC — `param_spec: ClassVar[dict[str, ParamSpec]]`, `result_spec: ClassVar[list[ResultSpec]]`, `simulate(params: dict[str, float]) -> list[InspectionItem]`
  - `ParamSpec` dataclass — `key, unit, min_val, max_val, default`
  - `ResultSpec` dataclass — `name, unit, usl, lsl`
  - `get_mechanism(device_type: str) -> MechanismModel` factory
  - `list_mechanisms() -> list[str]`

- [ ] **Step 1: 写 ParamSpec / ResultSpec 数据类 + MechanismModel 抽象基类**

```python
# src/process_opt/mock/mechanism/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from process_opt.common.schemas import InspectionItem


@dataclass
class ParamSpec:
    key: str
    unit: str = ""
    min_val: float = 0.0
    max_val: float = 100.0
    default: float = 0.0


@dataclass
class ResultSpec:
    name: str
    unit: str = ""
    usl: float = 0.0
    lsl: float = 0.0


class MechanismModel(ABC):
    """工艺机理模型基类。子类需声明 param_spec 和 result_spec，并实现 simulate。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {}
    result_spec: ClassVar[list[ResultSpec]] = []

    @abstractmethod
    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        """输入工艺参数 → 输出检测结果列表（基于领域机理 + 可控噪声）。"""
        ...
```

- [ ] **Step 2: 写注册表工厂**

```python
# src/process_opt/mock/mechanism/__init__.py
from __future__ import annotations

from process_opt.mock.mechanism.base import MechanismModel

_registry: dict[str, type[MechanismModel]] = {}


def register_mechanism(device_type: str):
    """装饰器：将机理模型类注册到工厂表中。"""
    def decorator(cls: type[MechanismModel]):
        _registry[device_type] = cls
        return cls
    return decorator


def get_mechanism(device_type: str) -> MechanismModel:
    """工厂函数：根据设备类型返回机理模型实例。"""
    cls = _registry.get(device_type)
    if cls is None:
        available = list(_registry.keys())
        raise ValueError(
            f"No mechanism model for device_type='{device_type}'. "
            f"Available: {available or '(none registered yet)'}"
        )
    return cls()


def list_mechanisms() -> list[str]:
    """返回已注册的工艺类型列表。"""
    return sorted(_registry.keys())
```

- [ ] **Step 3: 写注册表测试**

```python
# tests/mock/test_mechanism_base.py
import pytest
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec
from process_opt.mock.mechanism import get_mechanism, register_mechanism, list_mechanisms
from process_opt.common.schemas import InspectionItem


class _DummyModel(MechanismModel):
    param_spec = {"temp": ParamSpec(key="temp", unit="C", min_val=0, max_val=100, default=50)}
    result_spec = [ResultSpec(name="quality", usl=1.5, lsl=0.5)]

    def simulate(self, params):
        return [InspectionItem(name="quality", value=1.0, usl=1.5, lsl=0.5)]


def test_param_spec_defaults():
    ps = ParamSpec(key="x")
    assert ps.unit == ""
    assert ps.min_val == 0.0
    assert ps.default == 0.0


def test_result_spec_fields():
    rs = ResultSpec(name="y", unit="mm", usl=2.0, lsl=0.5)
    assert rs.name == "y"
    assert rs.usl == 2.0


def test_mechanism_model_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        MechanismModel()  # type: ignore[abstract]


def test_mechanism_model_concrete_works():
    m = _DummyModel()
    result = m.simulate({"temp": 50})
    assert len(result) == 1
    assert result[0].name == "quality"


@pytest.fixture(autouse=True)
def _clear_registry():
    from process_opt.mock import mechanism
    mechanism._registry.clear()
    yield
    mechanism._registry.clear()


def test_registry_empty_raises():
    with pytest.raises(ValueError, match="No mechanism model"):
        get_mechanism("nonexistent")


def test_register_and_get():
    register_mechanism("dummy")(_DummyModel)
    m = get_mechanism("dummy")
    assert isinstance(m, _DummyModel)
    assert m.param_spec["temp"].unit == "C"


def test_list_mechanisms():
    register_mechanism("dummy")(_DummyModel)
    assert "dummy" in list_mechanisms()
```

- [ ] **Step 4: 运行测试（预期 FAIL — 文件新创建，无导入问题则 PASS）**

Run: `pytest tests/mock/test_mechanism_base.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/mock/mechanism/ tests/mock/test_mechanism_base.py
git commit -m "feat: add mechanism model base class, ParamSpec/ResultSpec, and registry factory"
```

---

### Task 2: 五个工艺机理模型

**Files:**
- Create: `src/process_opt/mock/mechanism/reflow_oven.py`
- Create: `src/process_opt/mock/mechanism/injection_molder.py`
- Create: `src/process_opt/mock/mechanism/oven_curing.py`
- Create: `src/process_opt/mock/mechanism/cnc_drill.py`
- Create: `src/process_opt/mock/mechanism/coating_machine.py`
- Create: `tests/mock/test_mechanism_models.py`

**Interfaces:**
- Consumes: `MechanismModel`, `ParamSpec`, `ResultSpec` from Task 1, `register_mechanism` from Task 1, `InspectionItem` from `process_opt.common.schemas`
- Produces: 5 个已注册的机理模型类，每个实现 `simulate(params) -> list[InspectionItem]`

- [ ] **Step 1: 写 5 个模型测试**

```python
# tests/mock/test_mechanism_models.py
import pytest
from process_opt.mock.mechanism import get_mechanism, list_mechanisms
from process_opt.mock.mechanism.base import MechanismModel


MODELS = ["reflow-oven", "injection-molder", "oven-curing", "cnc-drill", "coating-machine"]

# Import to trigger @register_mechanism decorators
import process_opt.mock.mechanism.reflow_oven       # noqa: F401
import process_opt.mock.mechanism.injection_molder  # noqa: F401
import process_opt.mock.mechanism.oven_curing       # noqa: F401
import process_opt.mock.mechanism.cnc_drill         # noqa: F401
import process_opt.mock.mechanism.coating_machine   # noqa: F401


@pytest.mark.parametrize("device_type", MODELS)
def test_model_is_registered(device_type: str):
    assert device_type in list_mechanisms()


@pytest.mark.parametrize("device_type", MODELS)
def test_model_is_mechanism_instance(device_type: str):
    assert isinstance(get_mechanism(device_type), MechanismModel)


@pytest.mark.parametrize("device_type", MODELS)
def test_model_has_param_spec(device_type: str):
    m = get_mechanism(device_type)
    assert len(m.param_spec) >= 3, f"{device_type} should have >= 3 params"


@pytest.mark.parametrize("device_type", MODELS)
def test_model_has_result_spec(device_type: str):
    m = get_mechanism(device_type)
    assert len(m.result_spec) == 2, f"{device_type} should have 2 results"


@pytest.mark.parametrize("device_type", MODELS)
def test_simulate_returns_inspection_items(device_type: str):
    m = get_mechanism(device_type)
    defaults = {k: v.default for k, v in m.param_spec.items()}
    results = m.simulate(defaults)
    assert len(results) == len(m.result_spec)
    for ri in results:
        assert ri.name in {rs.name for rs in m.result_spec}
        assert ri.result in ("pass", "fail")
        assert isinstance(ri.value, (int, float))


@pytest.mark.parametrize("device_type", MODELS)
def test_simulate_varying_params_gives_different_results(device_type: str):
    m = get_mechanism(device_type)
    defaults = {k: v.default for k, v in m.param_spec.items()}
    low = {k: v.min_val for k, v in m.param_spec.items()}
    high = {k: v.max_val for k, v in m.param_spec.items()}
    r_def = m.simulate(defaults)
    r_low = m.simulate(low)
    r_high = m.simulate(high)
    values_def = [ri.value for ri in r_def]
    values_low = [ri.value for ri in r_low]
    values_high = [ri.value for ri in r_high]
    # At least one result should differ between extremes
    any_diff = any(vl != vh for vl, vh in zip(values_low, values_high))
    assert any_diff, f"{device_type}: simulating min vs max params should produce different results"
```

- [ ] **Step 2: 运行测试（预期 FAIL — 模型文件不存在）**

Run: `pytest tests/mock/test_mechanism_models.py -v`
Expected: ModuleNotFoundError for the first import

- [ ] **Step 3: 实现回流焊模型**

```python
# src/process_opt/mock/mechanism/reflow_oven.py
from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("reflow-oven")
class ReflowOvenModel(MechanismModel):
    """回流焊机理模型：焊点质量由热输入量决定，空洞率由峰值温度和氧含量共同影响。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "temperature": ParamSpec(key="temperature", unit="°C", min_val=100, max_val=300, default=230),
        "conveyor_speed": ParamSpec(key="conveyor_speed", unit="mm/s", min_val=10, max_val=100, default=60),
        "oxygen_ppm": ParamSpec(key="oxygen_ppm", unit="ppm", min_val=0, max_val=1000, default=200),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="solder_joint_quality", usl=1.5, lsl=0.5),
        ResultSpec(name="voiding_pct", unit="%", usl=5.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        temp = params["temperature"]
        speed = params["conveyor_speed"]
        oxygen = params["oxygen_ppm"]

        # 热输入量 = f(temp, speed)，理想值 ~48
        heat_input = temp / max(speed, 1) * 10
        ideal = 240 / 60 * 10  # = 40
        quality = 1.0 - abs(heat_input - ideal) / ideal * 0.8

        # 空洞率：高温 + 高氧 → 更多空洞
        voiding = 0.5 + (temp - 230) * 0.02 + oxygen * 0.003

        # 可控噪声
        quality += random.gauss(0, 0.02)
        voiding += random.gauss(0, 0.15)

        quality = round(quality, 2)
        voiding = round(voiding, 2)

        return [
            InspectionItem(
                name="solder_joint_quality", value=quality, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= quality <= 1.5 else "fail",
            ),
            InspectionItem(
                name="voiding_pct", value=voiding, unit="%", usl=5.0, lsl=0.0,
                result="pass" if voiding <= 5.0 else "fail",
            ),
        ]
```

- [ ] **Step 4: 实现注塑成型模型**

```python
# src/process_opt/mock/mechanism/injection_molder.py
from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("injection-molder")
class InjectionMolderModel(MechanismModel):
    """注塑成型机理：尺寸精度取决于熔体温度与压力的平衡，飞边由压力过高引起。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "melt_temp": ParamSpec(key="melt_temp", unit="°C", min_val=150, max_val=350, default=260),
        "injection_pressure": ParamSpec(key="injection_pressure", unit="MPa", min_val=50, max_val=200, default=120),
        "cooling_time": ParamSpec(key="cooling_time", unit="s", min_val=5, max_val=60, default=25),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="dimensional_accuracy", usl=1.5, lsl=0.5),
        ResultSpec(name="flash_present", usl=1.5, lsl=0.5),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        melt_temp = params["melt_temp"]
        pressure = params["injection_pressure"]
        cooling = params["cooling_time"]

        # 尺寸精度：温度与冷却时间的平衡
        temp_ideal = 260
        cool_ideal = 25
        deviation = abs(melt_temp - temp_ideal) / temp_ideal * 0.5 + abs(cooling - cool_ideal) / cool_ideal * 0.3
        accuracy = 1.0 - deviation

        # 飞边：压力过高 → 飞边增多
        flash = 0.3 + max(0, pressure - 100) * 0.008

        accuracy += random.gauss(0, 0.02)
        flash += random.gauss(0, 0.05)

        accuracy = round(accuracy, 2)
        flash = round(flash, 2)

        return [
            InspectionItem(
                name="dimensional_accuracy", value=accuracy, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= accuracy <= 1.5 else "fail",
            ),
            InspectionItem(
                name="flash_present", value=flash, usl=1.5, lsl=0.5,
                result="pass" if flash <= 1.5 else "fail",
            ),
        ]
```

- [ ] **Step 5: 实现固化炉模型**

```python
# src/process_opt/mock/mechanism/oven_curing.py
from __future__ import annotations

import math
import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("oven-curing")
class OvenCuringModel(MechanismModel):
    """固化炉机理：Arrhenius 固化动力学 — 固化度取决于温度×时间的积分，湿度抑制固化。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "oven_temp": ParamSpec(key="oven_temp", unit="°C", min_val=80, max_val=200, default=150),
        "cure_duration_min": ParamSpec(key="cure_duration_min", unit="min", min_val=10, max_val=120, default=45),
        "humidity_pct": ParamSpec(key="humidity_pct", unit="%", min_val=10, max_val=80, default=40),
        "airflow_rate": ParamSpec(key="airflow_rate", unit="m³/h", min_val=5, max_val=50, default=25),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="cure_complete", usl=1.5, lsl=0.5),
        ResultSpec(name="weight_loss_pct", unit="%", usl=3.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        temp = params["oven_temp"]
        duration = params["cure_duration_min"]
        humidity = params["humidity_pct"]
        airflow = params["airflow_rate"]

        # Arrhenius 简化：固化速率 k = A * exp(-Ea/RT)
        # 简化后固化度 ∝ temp * duration，湿度抑制
        R = 8.314
        T_kelvin = temp + 273.15
        k = math.exp(-50000 / (R * T_kelvin))  # Ea ≈ 50 kJ/mol
        cure_raw = k * duration * (1 - humidity / 200) * airflow / 25
        cure = 0.3 + cure_raw * 8000

        # 失重：高温长时 → 更多挥发
        weight_loss = 0.3 + (temp - 80) * 0.015 + duration * 0.008

        cure += random.gauss(0, 0.03)
        weight_loss += random.gauss(0, 0.1)

        cure = round(cure, 2)
        weight_loss = round(weight_loss, 2)

        return [
            InspectionItem(
                name="cure_complete", value=cure, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= cure <= 1.5 else "fail",
            ),
            InspectionItem(
                name="weight_loss_pct", value=weight_loss, unit="%", usl=3.0, lsl=0.0,
                result="pass" if weight_loss <= 3.0 else "fail",
            ),
        ]
```

- [ ] **Step 6: 实现 CNC 钻孔模型**

```python
# src/process_opt/mock/mechanism/cnc_drill.py
from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("cnc-drill")
class CncDrillModel(MechanismModel):
    """CNC钻孔机理：孔径精度取决于转速/进给的比值，表面粗糙度由进给率和冷却液共同影响。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "spindle_speed": ParamSpec(key="spindle_speed", unit="RPM", min_val=5000, max_val=25000, default=15000),
        "feed_rate": ParamSpec(key="feed_rate", unit="mm/min", min_val=100, max_val=800, default=400),
        "drill_depth": ParamSpec(key="drill_depth", unit="mm", min_val=0.5, max_val=12.0, default=4.5),
        "coolant_flow": ParamSpec(key="coolant_flow", unit="L/min", min_val=2, max_val=15, default=8),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="hole_accuracy", usl=1.5, lsl=0.5),
        ResultSpec(name="surface_roughness_ra", unit="μm", usl=6.0, lsl=0.5),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        speed = params["spindle_speed"]
        feed = params["feed_rate"]
        depth = params["drill_depth"]
        coolant = params["coolant_flow"]

        # 孔径精度：speed/feed 比值的稳定性
        sf_ratio = speed / max(feed, 1)
        ideal_ratio = 15000 / 400  # = 37.5
        accuracy = 1.0 - abs(sf_ratio - ideal_ratio) / ideal_ratio * 0.6 - depth / 20 * 0.1

        # 表面粗糙度：高进给 → 粗糙，充分冷却 → 光滑
        roughness = 1.5 + feed * 0.005 - coolant * 0.15

        accuracy += random.gauss(0, 0.02)
        roughness += random.gauss(0, 0.15)

        accuracy = round(accuracy, 2)
        roughness = round(roughness, 2)

        return [
            InspectionItem(
                name="hole_accuracy", value=accuracy, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= accuracy <= 1.5 else "fail",
            ),
            InspectionItem(
                name="surface_roughness_ra", value=roughness, unit="μm", usl=6.0, lsl=0.5,
                result="pass" if roughness <= 6.0 else "fail",
            ),
        ]
```

- [ ] **Step 7: 实现涂覆机模型**

```python
# src/process_opt/mock/mechanism/coating_machine.py
from __future__ import annotations

import random
from typing import ClassVar

from process_opt.common.schemas import InspectionItem
from process_opt.mock.mechanism import register_mechanism
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec


@register_mechanism("coating-machine")
class CoatingMachineModel(MechanismModel):
    """涂覆机机理：均匀度取决于喷涂压力与移动速度的配合，气泡由固化温度和厚度决定。"""

    param_spec: ClassVar[dict[str, ParamSpec]] = {
        "spray_pressure": ParamSpec(key="spray_pressure", unit="psi", min_val=10, max_val=60, default=35),
        "coating_thickness_um": ParamSpec(key="coating_thickness_um", unit="μm", min_val=5, max_val=100, default=45),
        "cure_temp": ParamSpec(key="cure_temp", unit="°C", min_val=60, max_val=180, default=120),
        "conveyor_speed": ParamSpec(key="conveyor_speed", unit="m/min", min_val=0.5, max_val=5.0, default=2.5),
    }

    result_spec: ClassVar[list[ResultSpec]] = [
        ResultSpec(name="coating_uniformity", usl=1.5, lsl=0.5),
        ResultSpec(name="bubble_count", usl=10.0, lsl=0.0),
    ]

    def simulate(self, params: dict[str, float]) -> list[InspectionItem]:
        pressure = params["spray_pressure"]
        thickness = params["coating_thickness_um"]
        cure_temp = params["cure_temp"]
        speed = params["conveyor_speed"]

        # 均匀度：压力×速度的乘积需在理想窗口内
        pv_product = pressure * speed
        ideal = 35 * 2.5  # = 87.5
        uniformity = 1.0 - abs(pv_product - ideal) / ideal * 0.7

        # 气泡：厚涂层 + 过高固化温度 → 更多气泡
        bubbles = 1.0 + thickness * 0.06 + max(0, cure_temp - 100) * 0.04 - pressure * 0.05

        uniformity += random.gauss(0, 0.02)
        bubbles += random.gauss(0, 0.3)

        uniformity = round(uniformity, 2)
        bubbles = round(bubbles, 2)

        return [
            InspectionItem(
                name="coating_uniformity", value=uniformity, usl=1.5, lsl=0.5,
                result="pass" if 0.5 <= uniformity <= 1.5 else "fail",
            ),
            InspectionItem(
                name="bubble_count", value=bubbles, usl=10.0, lsl=0.0,
                result="pass" if bubbles <= 10.0 else "fail",
            ),
        ]
```

- [ ] **Step 8: 运行测试**

Run: `pytest tests/mock/test_mechanism_models.py -v`
Expected: 25 passed (5 tests × 5 models)

- [ ] **Step 9: Commit**

```bash
git add src/process_opt/mock/mechanism/ tests/mock/test_mechanism_models.py
git commit -m "feat: add 5 mechanism models — reflow-oven, injection-molder, oven-curing, cnc-drill, coating-machine"
```

---

### Task 3: MockDevice + MockManager

**Files:**
- Create: `src/process_opt/mock/device.py`
- Create: `src/process_opt/mock/manager.py`
- Create: `tests/mock/test_manager.py`

**Interfaces:**
- Consumes: `MechanismModel.get_mechanism()` from Task 2, `send_pair()` from existing `mock.sender`, `InspectionItem` / `ProcessMessage` / `InspectionMessage` from `process_opt.common.schemas`
- Produces:
  - `MockDevice` class — `device_id, device_type, state, current_params, start/pause/stop/resume, configure(params), enqueue_experiment(plan), events: asyncio.Queue`
  - `MockManager` class — `create(DeviceConfig), delete(device_id), get(device_id), list_all(), start/pause/stop(device_id)`
  - `DeviceConfig` Pydantic model — `device_id, device_type, name, line_id, report_interval`

- [ ] **Step 1: 写 MockManager + MockDevice 测试**

```python
# tests/mock/test_manager.py
import asyncio
import json
import time

import pytest

from process_opt.mock.manager import MockManager, DeviceConfig


@pytest.fixture
def manager():
    return MockManager(
        api_url="http://test-api:8000",
        gateway_url="http://test-gw:8001",
        api_key="test-key",
    )


def test_create_device_idle(manager):
    cfg = DeviceConfig(
        device_id="test-reflow-001",
        device_type="reflow-oven",
        name="测试回流焊",
        line_id="L1",
        report_interval=999,
    )
    dev = manager.create(cfg)
    assert dev.device_id == "test-reflow-001"
    assert dev.device_type == "reflow-oven"
    assert dev.state == "idle"
    assert dev.name == "测试回流焊"


def test_list_all(manager):
    manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    manager.create(DeviceConfig(device_id="d2", device_type="injection-molder", name="B", line_id="L2"))
    devices = manager.list_all()
    assert len(devices) == 2


def test_get_device(manager):
    manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    dev = manager.get("d1")
    assert dev is not None
    assert dev.name == "A"


def test_get_nonexistent(manager):
    assert manager.get("nope") is None


def test_delete_device(manager):
    manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    manager.delete("d1")
    assert manager.get("d1") is None


def test_delete_running_device_stops_first(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    manager.create(cfg)
    manager.start("d1")
    assert manager.get("d1").state == "running"
    manager.delete("d1")
    assert manager.get("d1") is None


def test_start_stop_pause(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    manager.create(cfg)
    dev = manager.get("d1")
    assert dev.state == "idle"

    manager.start("d1")
    assert dev.state == "running"

    manager.pause("d1")
    assert dev.state == "paused"

    manager.start("d1")  # start from paused = resume
    assert dev.state == "running"

    manager.stop("d1")
    assert dev.state == "idle"


def test_configure_params(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    manager.create(cfg)
    dev = manager.get("d1")
    manager.configure("d1", {"temperature": 260, "conveyor_speed": 70, "oxygen_ppm": 150})
    assert dev.current_params["temperature"] == 260
    assert dev.current_params["conveyor_speed"] == 70


def test_enqueue_experiment(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    manager.create(cfg)
    dev = manager.get("d1")
    manager.enqueue_experiment("d1", 3)
    assert dev.experiment_queue.qsize() == 1
    plan_id = dev.experiment_queue.get_nowait()
    assert plan_id == 3


def test_get_state_snapshot(manager):
    manager.create(DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1"))
    manager.create(DeviceConfig(device_id="d2", device_type="cnc-drill", name="B", line_id="L2"))
    manager.start("d1")
    state = manager.get_state()
    assert state["summary"]["running"] == 1
    assert state["summary"]["idle"] == 1
    assert len(state["devices"]) == 2


def test_duplicate_create_replaces_existing(manager):
    c1 = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    c2 = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A-v2", line_id="L2")
    manager.create(c1)
    manager.start("d1")
    manager.create(c2)  # should stop old, replace with new
    dev = manager.get("d1")
    assert dev.name == "A-v2"
    assert dev.line_id == "L2"
    assert dev.state == "idle"


@pytest.mark.asyncio
async def test_device_events_queue(manager):
    cfg = DeviceConfig(device_id="d1", device_type="reflow-oven", name="A", line_id="L1")
    manager.create(cfg)
    dev = manager.get("d1")
    # Put a test event
    await dev.events.put({"type": "test", "msg": "hello"})
    event = await asyncio.wait_for(dev.events.get(), timeout=0.1)
    assert event["type"] == "test"
```

- [ ] **Step 2: 运行测试（预期 FAIL — 类不存在）**

Run: `pytest tests/mock/test_manager.py -v`
Expected: ModuleNotFoundError or ImportError

- [ ] **Step 3: 实现 MockDevice**

```python
# src/process_opt/mock/device.py
from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from process_opt.mock.mechanism import get_mechanism

logger = logging.getLogger(__name__)


class MockDevice:
    """单设备模拟引擎 — 内部跑 4 个 asyncio.Task。"""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        name: str = "",
        line_id: str = "",
        report_interval: int = 60,
        *,
        gateway_url: str,
        api_url: str,
        api_key: str,
        use_mechanism: bool = True,
    ):
        self.device_id = device_id
        self.device_type = device_type
        self.name = name or device_id
        self.line_id = line_id
        self.report_interval = report_interval

        self._gateway_url = gateway_url.rstrip("/")
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._use_mechanism = use_mechanism
        self._http: httpx.AsyncClient | None = None

        # Mechanism model
        try:
            self._mechanism = get_mechanism(device_type) if use_mechanism else None
        except ValueError:
            self._mechanism = None

        # Build default params from mechanism spec
        if self._mechanism is not None:
            self.current_params: dict[str, Any] = {
                k: v.default for k, v in self._mechanism.param_spec.items()
            }
        else:
            self.current_params = {}

        self.state: str = "idle"  # idle | running | paused
        self.experiment_queue: asyncio.Queue[int] = asyncio.Queue()
        self.events: asyncio.Queue[dict] = asyncio.Queue()

        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._report_count = 0
        self._last_heartbeat: float | None = None

    # ---- lifecycle ----

    async def start(self) -> None:
        if self.state == "running":
            return
        self.state = "running"
        self._stop_event.clear()
        self._http = httpx.AsyncClient()
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._report_loop()),
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(self._experiment_loop()),
        ]
        await self._emit("status", {"status": "running"})

    async def pause(self) -> None:
        if self.state != "running":
            return
        self.state = "paused"
        await self._cancel_tasks()
        await self._emit("status", {"status": "paused"})

    async def stop(self) -> None:
        if self.state == "idle":
            return
        self.state = "idle"
        await self._cancel_tasks()
        if self._http:
            await self._http.aclose()
            self._http = None
        await self._emit("status", {"status": "idle"})

    async def _cancel_tasks(self) -> None:
        self._stop_event.set()
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    # ---- Task loops ----

    async def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._send_heartbeat()
            except Exception:
                await self._emit("error", {"message": "Heartbeat send failed"})
            await self._sleep_or_stop(30)

    async def _report_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._send_data_pair()
            except Exception:
                await self._emit("error", {"message": "Data report failed"})
            await self._sleep_or_stop(self.report_interval)

    async def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._poll_experiments()
            except Exception:
                pass  # polling failures are non-critical
            await self._sleep_or_stop(30)

    async def _experiment_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                plan_id = await asyncio.wait_for(self.experiment_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                continue
            try:
                await self._execute_experiment(plan_id)
            except Exception as exc:
                await self._emit("error", {"message": f"Experiment {plan_id} failed: {exc}"})

    # ---- Network ops ----

    async def _send_heartbeat(self) -> None:
        payload = {
            "message_id": f"hb-{self.device_id}-{int(time.time())}",
            "barcode": "_heartbeat_",
            "device_id": self.device_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "product_model": "",
            "params": {
                "_heartbeat": True,
                "status": self.state,
                "current_params": self.current_params,
            },
        }
        if self._http:
            r = await self._http.post(
                f"{self._gateway_url}/api/v1/data/process",
                json=payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
        self._last_heartbeat = time.monotonic()
        await self._emit("heartbeat", {"status": self.state, "current_params": dict(self.current_params)})

    async def _send_data_pair(self) -> None:
        # Generate params with small noise
        noisy_params = {}
        for k, v in self.current_params.items():
            if isinstance(v, (int, float)):
                sigma = abs(v) * 0.01 + 0.1
                noisy_params[k] = round(v + random.gauss(0, sigma), 2)
            else:
                noisy_params[k] = v

        message_id = str(uuid4())
        barcode = f"MOCK-{uuid4().hex[:8].upper()}"
        now = datetime.now(UTC).isoformat()

        process_payload = {
            "message_id": message_id,
            "barcode": barcode,
            "device_id": self.device_id,
            "processed_at": now,
            "product_model": random.choice(["A", "B", "C"]),
            "params": noisy_params,
        }

        # Generate inspection results via mechanism or fallback
        if self._mechanism is not None:
            results = self._mechanism.simulate(noisy_params)
            insp_results = [
                {"name": r.name, "value": r.value, "unit": r.unit or "",
                 "result": r.result, "usl": r.usl, "lsl": r.lsl}
                for r in results
            ]
        else:
            insp_results = []

        inspection_payload = {
            "message_id": message_id,
            "barcode": barcode,
            "station_id": f"{self.device_id}-qa",
            "inspected_at": now,
            "product_model": process_payload["product_model"],
            "results": insp_results,
        }

        if self._http:
            await self._http.post(
                f"{self._gateway_url}/api/v1/data/process",
                json=process_payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
            await self._http.post(
                f"{self._gateway_url}/api/v1/data/inspection",
                json=inspection_payload,
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
            )
        self._report_count += 1
        await self._emit("data.reported", {"barcode": barcode})

    async def _poll_experiments(self) -> None:
        if self._http is None:
            return
        need_plan = self.experiment_queue.empty()
        if not need_plan:
            return
        try:
            r = await self._http.get(
                f"{self._api_url}/api/v1/experiment/plans",
                params={"process_type": self.device_type, "limit": 5},
            )
            if r.status_code == 200:
                plans = r.json()
                for p in plans:
                    if p.get("status") in ("draft", "ready"):
                        self.experiment_queue.put_nowait(p["id"])
                        break
        except Exception:
            pass

    async def _execute_experiment(self, plan_id: int) -> None:
        if self._http is None:
            return
        # Fetch plan details
        r = await self._http.get(f"{self._api_url}/api/v1/experiment/plans/{plan_id}")
        if r.status_code != 200:
            return
        plan = r.json()
        runs = plan.get("design_runs", [])
        response_name = plan.get("response_name", "response")

        total = len(runs)
        for idx, run in enumerate(runs, start=1):
            # Inject factor values into current_params
            params = dict(self.current_params)
            for factor in run.get("factors", {}):
                params[factor] = run["factors"][factor]

            # Simulate
            if self._mechanism is not None:
                results = self._mechanism.simulate(params)
                # Find response value
                response_value = None
                for ri in results:
                    if ri.name == response_name:
                        response_value = ri.value
                        break
                if response_value is None and results:
                    response_value = results[0].value
            else:
                response_value = random.uniform(0.5, 1.5)

            # Report result
            await self._http.post(
                f"{self._api_url}/api/v1/experiment/plans/{plan_id}/results",
                json={"run_order": run.get("run_order", idx), "response_value": response_value},
            )
            await self._emit("experiment.progress", {
                "plan_id": plan_id, "run_order": idx, "total_runs": total,
            })

        await self._emit("experiment.complete", {"plan_id": plan_id, "total_runs": total})

    # ---- helpers ----

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _emit(self, event_type: str, data: dict) -> None:
        payload = {"type": event_type, "device_id": self.device_id, **data}
        try:
            self.events.put_nowait(payload)
        except asyncio.QueueFull:
            pass
```

- [ ] **Step 4: 实现 MockManager**

```python
# src/process_opt/mock/manager.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from process_opt.mock.device import MockDevice

logger = logging.getLogger(__name__)


class DeviceConfig(BaseModel):
    device_id: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    name: str = ""
    line_id: str = ""
    report_interval: int = Field(default=60, ge=5, le=3600)


class MockManager:
    """管理所有模拟设备生命周期，作为 Backend API 的单例。"""

    def __init__(self, api_url: str, gateway_url: str, api_key: str):
        self._devices: dict[str, MockDevice] = {}
        self._api_url = api_url
        self._gateway_url = gateway_url
        self._api_key = api_key

    def create(self, config: DeviceConfig) -> MockDevice:
        """创建或替换设备（如已存在则先停止旧设备）。"""
        if config.device_id in self._devices:
            old = self._devices[config.device_id]
            asyncio.ensure_future(old.stop())

        device = MockDevice(
            device_id=config.device_id,
            device_type=config.device_type,
            name=config.name,
            line_id=config.line_id,
            report_interval=config.report_interval,
            gateway_url=self._gateway_url,
            api_url=self._api_url,
            api_key=self._api_key,
        )
        self._devices[config.device_id] = device
        return device

    async def delete(self, device_id: str) -> None:
        dev = self._devices.pop(device_id, None)
        if dev is not None:
            await dev.stop()

    def get(self, device_id: str) -> MockDevice | None:
        return self._devices.get(device_id)

    def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "device_id": d.device_id,
                "device_type": d.device_type,
                "name": d.name,
                "line_id": d.line_id,
                "status": d.state,
                "report_interval": d.report_interval,
                "report_count": d._report_count,
                "current_params": d.current_params,
            }
            for d in self._devices.values()
        ]

    async def start(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.start()

    async def pause(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.pause()

    async def stop(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.stop()

    async def configure(self, device_id: str, params: dict[str, Any]) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        dev.current_params.update(params)

    async def enqueue_experiment(self, device_id: str, plan_id: int) -> None:
        dev = self._devices.get(device_id)
        if dev is None:
            raise ValueError(f"Device {device_id} not found")
        await dev.experiment_queue.put(plan_id)

    def get_state(self) -> dict[str, Any]:
        devices = self.list_all()
        summary = {"running": 0, "paused": 0, "idle": 0}
        for d in devices:
            summary[d["status"]] = summary.get(d["status"], 0) + 1
        # Inject line name (from mock data or fallback to line_id)
        for d in devices:
            d["line_name"] = d.get("line_name") or d["line_id"]
        return {"summary": summary, "devices": devices}
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/mock/test_manager.py -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/process_opt/mock/device.py src/process_opt/mock/manager.py tests/mock/test_manager.py
git commit -m "feat: add MockDevice + MockManager — device lifecycle and 4 async task loops"
```

---

### Task 4: REST API 路由 + SSE + 系统集成

**Files:**
- Create: `src/process_opt/api/mock_routes.py`
- Modify: `src/process_opt/api/app.py` — add `mock_manager` parameter + register mock routes
- Modify: `src/process_opt/api/main.py` — create MockManager in lifespan, pass to create_app
- Create: `tests/api/test_mock_routes.py`

**Interfaces:**
- Consumes: `MockManager` from Task 3, `create_app` signature from `app.py`
- Produces: 10 REST endpoints + 1 SSE endpoint, registered under `/api/v1/mock`

- [ ] **Step 1: 写 API 路由测试**

```python
# tests/api/test_mock_routes.py
import json

import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.app import create_app
from process_opt.mock.manager import MockManager, DeviceConfig


@pytest.fixture
def mock_manager():
    return MockManager(
        api_url="http://test-api:8000",
        gateway_url="http://test-gw:8001",
        api_key="test-key",
    )


@pytest.fixture
def app_with_mock(mock_manager):
    return create_app(mock_manager=mock_manager)


@pytest.fixture
async def client(app_with_mock):
    transport = ASGITransport(app=app_with_mock)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---- Create / List / Get / Delete ----

@pytest.mark.asyncio
async def test_create_device(client):
    r = await client.post("/api/v1/mock/devices", json={
        "device_id": "reflow-oven-001",
        "device_type": "reflow-oven",
        "name": "回流焊1号",
        "line_id": "L1",
        "report_interval": 60,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["device_id"] == "reflow-oven-001"
    assert data["status"] == "idle"


@pytest.mark.asyncio
async def test_list_devices(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d2", "device_type": "cnc-drill", "name": "B", "line_id": "L2",
    })
    r = await client.get("/api/v1/mock/devices")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["idle"] == 2
    assert len(data["devices"]) == 2


@pytest.mark.asyncio
async def test_get_device(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    r = await client.get("/api/v1/mock/devices/d1")
    assert r.status_code == 200
    assert r.json()["name"] == "A"


@pytest.mark.asyncio
async def test_get_device_404(client):
    r = await client.get("/api/v1/mock/devices/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_device(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    r = await client.delete("/api/v1/mock/devices/d1")
    assert r.status_code == 200
    r2 = await client.get("/api/v1/mock/devices/d1")
    assert r2.status_code == 404


# ---- Start / Pause / Stop ----

@pytest.mark.asyncio
async def test_start_device(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    r = await client.post("/api/v1/mock/devices/d1/start")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


@pytest.mark.asyncio
async def test_start_nonexistent_device(client):
    r = await client.post("/api/v1/mock/devices/nope/start")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pause_device(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    await client.post("/api/v1/mock/devices/d1/start")
    r = await client.post("/api/v1/mock/devices/d1/pause")
    assert r.status_code == 200
    assert r.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_stop_device(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    await client.post("/api/v1/mock/devices/d1/start")
    r = await client.post("/api/v1/mock/devices/d1/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


# ---- Configure / Experiment ----

@pytest.mark.asyncio
async def test_configure_params(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    r = await client.put("/api/v1/mock/devices/d1/params", json={
        "temperature": 250, "conveyor_speed": 55, "oxygen_ppm": 150,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["current_params"]["temperature"] == 250


@pytest.mark.asyncio
async def test_enqueue_experiment(client):
    await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
    })
    r = await client.post("/api/v1/mock/devices/d1/experiments", json={"plan_id": 3})
    assert r.status_code == 202
    assert r.json()["plan_id"] == 3
    assert r.json()["status"] == "queued"


# ---- Validation ----

@pytest.mark.asyncio
async def test_create_device_missing_required_fields(client):
    r = await client.post("/api/v1/mock/devices", json={"name": "test"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_report_interval(client):
    r = await client.post("/api/v1/mock/devices", json={
        "device_id": "d1", "device_type": "reflow-oven", "name": "A", "line_id": "L1",
        "report_interval": 0,
    })
    assert r.status_code == 422
```

- [ ] **Step 2: 运行测试（预期 FAIL — 路由不存在）**

Run: `pytest tests/api/test_mock_routes.py -v`
Expected: 404 or 422 errors (routes not registered)

- [ ] **Step 3: 实现 mock_routes.py**

```python
# src/process_opt/api/mock_routes.py
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from starlette.responses import StreamingResponse

from process_opt.mock.manager import DeviceConfig, MockManager

logger = logging.getLogger(__name__)


def register_mock_routes(app: Any, mock_manager: MockManager) -> None:
    router = APIRouter(prefix="/api/v1/mock")

    @router.get("/devices")
    async def list_devices() -> dict:
        return mock_manager.get_state()

    @router.post("/devices", status_code=status.HTTP_201_CREATED)
    async def create_device(body: dict[str, Any]) -> dict:
        try:
            config = DeviceConfig(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
        device = mock_manager.create(config)
        return {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "name": device.name,
            "line_id": device.line_id,
            "status": device.state,
            "report_interval": device.report_interval,
            "current_params": device.current_params,
        }

    @router.get("/devices/{device_id}")
    async def get_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return {
            "device_id": dev.device_id,
            "device_type": dev.device_type,
            "name": dev.name,
            "line_id": dev.line_id,
            "status": dev.state,
            "report_interval": dev.report_interval,
            "report_count": dev._report_count,
            "current_params": dev.current_params,
            "last_heartbeat": dev._last_heartbeat,
        }

    @router.delete("/devices/{device_id}")
    async def delete_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.delete(device_id)
        return {"device_id": device_id, "deleted": True}

    @router.post("/devices/{device_id}/start")
    async def start_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.start(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.post("/devices/{device_id}/pause")
    async def pause_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.pause(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.post("/devices/{device_id}/stop")
    async def stop_device(device_id: str) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.stop(device_id)
        return {"device_id": device_id, "status": dev.state}

    @router.put("/devices/{device_id}/params")
    async def update_params(device_id: str, body: dict[str, Any]) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        await mock_manager.configure(device_id, body)
        return {
            "device_id": device_id,
            "current_params": dev.current_params,
            "confirmed": True,
        }

    @router.post("/devices/{device_id}/experiments", status_code=status.HTTP_202_ACCEPTED)
    async def assign_experiment(device_id: str, body: dict[str, Any]) -> dict:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")
        plan_id = body.get("plan_id")
        if not plan_id:
            raise HTTPException(status_code=422, detail="plan_id required")
        await mock_manager.enqueue_experiment(device_id, plan_id)
        return {
            "device_id": device_id,
            "plan_id": plan_id,
            "status": "queued",
            "total_runs": body.get("total_runs", "unknown"),
        }

    @router.get("/devices/{device_id}/events")
    async def stream_events(device_id: str, request: Request) -> StreamingResponse:
        dev = mock_manager.get(device_id)
        if dev is None:
            raise HTTPException(status_code=404, detail="Device not found")

        async def generate():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(dev.events.get(), timeout=15)
                        yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n".encode()
                    except asyncio.TimeoutError:
                        yield b':keepalive\n\n'
            except asyncio.CancelledError:
                pass

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(router)
```

- [ ] **Step 4: 修改 app.py — 添加 mock_manager 参数**

在 `create_app` 函数签名中添加 `mock_manager` 参数，并在函数末尾注册路由：

```python
# src/process_opt/api/app.py — 在 create_app 函数签名中:
def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
    container_pool: Any = None,
    agent_factory: Any = None,
    suggestion_llm: Any = None,
    experiment_repo: Any = None,
    mock_manager: Any = None,   # <-- 新增
) -> FastAPI:

# 在 experiment_repo 路由注册之后 (约第 622 行)，添加:
    if mock_manager is not None:
        from process_opt.api.mock_routes import register_mock_routes
        register_mock_routes(app, mock_manager)
```

- [ ] **Step 5: 修改 main.py — 创建 MockManager 并传入**

在 `create_api_app_from_settings()` 的 lifespan 中创建 MockManager，在 `create_app(...)` 调用中传入：

```python
# src/process_opt/api/main.py

# 在 lifespan 内，pool 创建之后:
from process_opt.mock.manager import MockManager
mock_manager = MockManager(
    api_url=f"http://localhost:8000",
    gateway_url=f"http://localhost:{settings.gateway_port if hasattr(settings, 'gateway_port') else 8001}",
    api_key=settings.gateway_api_key,
)
app.state.mock_manager = mock_manager

# 在 create_app 调用中:
app = create_app(
    ...existing params...,
    mock_manager=mock_manager,
)
```

更精确的编辑：需要让 gateway_url 和 api_url 可配置。在 main.py 中直接用 Settings：

```python
# In lifespan (src/process_opt/api/main.py, ~line 268):
mock_manager = MockManager(
    api_url=f"http://localhost:8000",
    gateway_url=f"http://localhost:8001",
    api_key=settings.gateway_api_key,
)
app.state.mock_manager = mock_manager

# In create_app call (~line 330):
app = create_app(
    repository=repository_proxy,
    parameter_service=parameter_service_proxy,
    analysis_service=analysis_service_proxy,
    line_device_repo=line_device_repo_proxy,
    container_pool=container_pool_proxy,
    agent_factory=agent_factory,
    suggestion_llm=llm,
    experiment_repo=experiment_repo_proxy,
    mock_manager=mock_manager,
)
```

- [ ] **Step 6: 运行 API 测试**

Run: `pytest tests/api/test_mock_routes.py -v`
Expected: all 14 tests pass

- [ ] **Step 7: 运行所有已有测试确保无回归**

Run: `pytest --ignore=tests/integration -v`
Expected: all existing tests still pass

- [ ] **Step 8: Commit**

```bash
git add src/process_opt/api/mock_routes.py src/process_opt/api/app.py src/process_opt/api/main.py tests/api/test_mock_routes.py
git commit -m "feat: add mock device REST API routes + SSE streaming + system integration"
```

---

### Task 5: Vue 3 前端 — 装备模拟页面 + 组件

**Files:**
- Create: `web/src/views/MockDevices.vue`
- Create: `web/src/components/mock/DeviceCard.vue`
- Create: `web/src/components/mock/AddDeviceDialog.vue`
- Create: `web/src/components/mock/DeviceConfigDrawer.vue`
- Create: `web/src/components/mock/ExperimentPanel.vue`
- Modify: `web/src/router/index.ts` — add `/mock-devices` route
- Modify: `web/src/components/AppLayout.vue` — add navigation item

**Interfaces:**
- Consumes: `GET/POST/PUT/DELETE /api/v1/mock/devices` REST API from Task 4, `GET /api/v1/mock/devices/{id}/events` SSE endpoint
- Produces: Functional UI matching spec layout

- [ ] **Step 1: 添加路由和导航**

```typescript
// web/src/router/index.ts — 在 children 数组中添加:
{ path: 'mock-devices', component: () => import('@/views/MockDevices.vue') },
```

```vue
<!-- web/src/components/AppLayout.vue — 在 el-menu 中，参数管理之后添加: -->
<el-menu-item index="/mock-devices">
  <el-icon class="nav-icon-mock"><Cpu /></el-icon>
  <span>装备模拟</span>
</el-menu-item>
```

在 `<script setup>` 导入中添加 `Cpu`：
```typescript
import { Monitor, DocumentCopy, TrendCharts, DataAnalysis, Setting, Tools, Fold, Expand, Cpu } from '@element-plus/icons-vue'
```

- [ ] **Step 2: 写 MockDevices.vue 主页面**

```vue
<!-- web/src/views/MockDevices.vue -->
<template>
  <div class="mock-devices-page">
    <div class="page-header">
      <h2 class="page-title">工艺装备模拟器</h2>
      <el-button type="primary" @click="showAddDialog = true">+ 添加设备</el-button>
    </div>

    <!-- 概览条 -->
    <div class="summary-bar">
      <span class="summary-item running">🟢 运行中: {{ summary.running }}</span>
      <span class="summary-item paused">🟡 暂停: {{ summary.paused }}</span>
      <span class="summary-item idle">⚪ 空闲: {{ summary.idle }}</span>
    </div>

    <!-- 设备卡片网格 -->
    <div v-if="devices.length" class="device-grid">
      <DeviceCard
        v-for="d in devices"
        :key="d.device_id"
        :device="d"
        @configure="openConfig"
        @experiment="openExperiment"
        @start="handleStart(d.device_id)"
        @pause="handlePause(d.device_id)"
        @stop="handleStop(d.device_id)"
        @delete="handleDelete(d.device_id)"
      />
    </div>
    <el-empty v-else description="暂无模拟设备，点击右上角「添加设备」创建" />

    <!-- 添加设备弹窗 -->
    <AddDeviceDialog
      v-model:visible="showAddDialog"
      @created="fetchDevices"
    />

    <!-- 参数配置抽屉 -->
    <DeviceConfigDrawer
      v-model:visible="configDrawer.visible"
      :device="configDrawer.device"
      @updated="fetchDevices"
    />

    <!-- 实验面板抽屉 -->
    <ExperimentPanel
      v-model:visible="experimentDrawer.visible"
      :device="experimentDrawer.device"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DeviceCard from '@/components/mock/DeviceCard.vue'
import AddDeviceDialog from '@/components/mock/AddDeviceDialog.vue'
import DeviceConfigDrawer from '@/components/mock/DeviceConfigDrawer.vue'
import ExperimentPanel from '@/components/mock/ExperimentPanel.vue'

interface MockDevice {
  device_id: string
  device_type: string
  name: string
  line_id: string
  line_name: string
  status: string
  report_count: number
  report_interval: number
  current_params: Record<string, any>
  last_heartbeat?: number
}

const devices = ref<MockDevice[]>([])
const summary = reactive({ running: 0, paused: 0, idle: 0 })
const showAddDialog = ref(false)

const configDrawer = reactive<{ visible: boolean; device: MockDevice | null }>({
  visible: false, device: null,
})
const experimentDrawer = reactive<{ visible: boolean; device: MockDevice | null }>({
  visible: false, device: null,
})

async function fetchDevices() {
  try {
    const r = await fetch('/api/v1/mock/devices')
    if (!r.ok) return
    const data = await r.json()
    devices.value = data.devices || []
    summary.running = data.summary?.running ?? 0
    summary.paused = data.summary?.paused ?? 0
    summary.idle = data.summary?.idle ?? 0
  } catch { /* ignore */ }
}

async function handleStart(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/start`, { method: 'POST' })
  fetchDevices()
}
async function handlePause(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/pause`, { method: 'POST' })
  fetchDevices()
}
async function handleStop(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/stop`, { method: 'POST' })
  fetchDevices()
}
async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('删除后历史数据保留。确认删除？', '确认删除', { type: 'warning' })
    await fetch(`/api/v1/mock/devices/${id}`, { method: 'DELETE' })
    ElMessage.success('已删除')
    fetchDevices()
  } catch { /* cancelled */ }
}

function openConfig(d: MockDevice) {
  configDrawer.device = d
  configDrawer.visible = true
}
function openExperiment(d: MockDevice) {
  experimentDrawer.device = d
  experimentDrawer.visible = true
}

let timer: number | undefined
onMounted(() => {
  fetchDevices()
  timer = window.setInterval(fetchDevices, 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.mock-devices-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}
.summary-bar {
  display: flex;
  gap: 20px;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
}
.summary-item.running { color: #67c23a; }
.summary-item.paused { color: #e6a23c; }
.summary-item.idle { color: #909399; }
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}
</style>
```

- [ ] **Step 3: 写 DeviceCard.vue**

```vue
<!-- web/src/components/mock/DeviceCard.vue -->
<template>
  <div class="device-card" :class="`status-${device.status}`">
    <div class="card-header">
      <span class="status-dot" :class="device.status" />
      <span class="device-id">{{ device.device_id }}</span>
      <span class="device-type">{{ typeLabel }}</span>
      <el-popconfirm title="确认删除？" @confirm="$emit('delete')">
        <template #reference>
          <el-button text size="small" type="danger" class="delete-btn">删除</el-button>
        </template>
      </el-popconfirm>
    </div>
    <div class="card-body">
      <div class="info-row"><span class="label">工艺</span><span>{{ typeLabel }}</span></div>
      <div class="info-row"><span class="label">产线</span><span>{{ device.line_name || device.line_id }}</span></div>
      <div class="info-row"><span class="label">状态</span><span>{{ statusLabel }}</span></div>
      <div class="info-row"><span class="label">上报</span><span>{{ device.report_count }} 条</span></div>
    </div>
    <div class="card-footer">
      <el-button size="small" @click="$emit('configure', device)">参数配置</el-button>
      <el-button size="small" @click="$emit('experiment', device)">实验</el-button>
      <template v-if="device.status === 'running'">
        <el-button size="small" type="warning" @click="$emit('pause')">暂停</el-button>
        <el-button size="small" type="danger" @click="$emit('stop')">停止</el-button>
      </template>
      <template v-else-if="device.status === 'paused'">
        <el-button size="small" type="success" @click="$emit('start')">恢复</el-button>
        <el-button size="small" type="danger" @click="$emit('stop')">停止</el-button>
      </template>
      <el-button v-else size="small" type="primary" @click="$emit('start')">启动</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ device: any }>()
defineEmits(['configure', 'experiment', 'start', 'pause', 'stop', 'delete'])

const TYPE_LABELS: Record<string, string> = {
  'reflow-oven': '回流焊',
  'injection-molder': '注塑成型',
  'oven-curing': '固化炉',
  'cnc-drill': 'CNC钻孔',
  'coating-machine': '涂覆机',
  'pick-and-place': '贴片',
  'wave-solder': '波峰焊',
  '3d-printer': '3D打印',
  'testing-station': '测试站',
  'laser-cutter': '激光切割',
  'xray-inspection': 'X-Ray检测',
  'wire-bonder': '键合',
  'ultrasonic-cleaner': '超声清洗',
}
const STATUS_LABELS: Record<string, string> = {
  idle: '空闲', running: '运行中', paused: '已暂停',
}

const typeLabel = computed(() => TYPE_LABELS[props.device.device_type] || props.device.device_type)
const statusLabel = computed(() => STATUS_LABELS[props.device.status] || props.device.status)
</script>

<style scoped>
.device-card {
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  padding: 14px;
  background: var(--el-bg-color);
  transition: box-shadow 0.2s;
}
.device-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
.device-card.status-running { border-left: 3px solid #67c23a; }
.device-card.status-paused { border-left: 3px solid #e6a23c; }
.device-card.status-idle { border-left: 3px solid #909399; }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.running { background: #67c23a; }
.status-dot.paused { background: #e6a23c; }
.status-dot.idle { background: #909399; }
.device-id { font-weight: 600; font-size: 14px; flex: 1; }
.device-type { font-size: 11px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); padding: 1px 6px; border-radius: 4px; }
.delete-btn { margin-left: auto; }

.card-body { margin-bottom: 10px; }
.info-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; color: var(--el-text-color-regular); }
.info-row .label { color: var(--el-text-color-secondary); }

.card-footer { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
```

- [ ] **Step 4: 写 AddDeviceDialog.vue**

```vue
<!-- web/src/components/mock/AddDeviceDialog.vue -->
<template>
  <el-dialog v-model="visible" title="添加模拟设备" width="480px" @close="resetForm">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" size="default">
      <el-form-item label="工艺类型" prop="device_type">
        <el-select v-model="form.device_type" placeholder="选择工艺类型" style="width:100%">
          <el-option v-for="t in deviceTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="设备编号" prop="device_id">
        <el-input v-model="form.device_id" placeholder="如 reflow-oven-005" />
      </el-form-item>
      <el-form-item label="设备名称">
        <el-input v-model="form.name" placeholder="如 回流焊 5号" />
      </el-form-item>
      <el-form-item label="上报间隔(秒)">
        <el-input-number v-model="form.report_interval" :min="5" :max="3600" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits(['update:visible', 'created'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const deviceTypes = [
  { label: '回流焊 (reflow-oven)', value: 'reflow-oven' },
  { label: '注塑成型 (injection-molder)', value: 'injection-molder' },
  { label: '固化炉 (oven-curing)', value: 'oven-curing' },
  { label: 'CNC钻孔 (cnc-drill)', value: 'cnc-drill' },
  { label: '涂覆机 (coating-machine)', value: 'coating-machine' },
  { label: '贴片 (pick-and-place)', value: 'pick-and-place' },
  { label: '波峰焊 (wave-solder)', value: 'wave-solder' },
  { label: '3D打印 (3d-printer)', value: '3d-printer' },
  { label: '测试站 (testing-station)', value: 'testing-station' },
  { label: '激光切割 (laser-cutter)', value: 'laser-cutter' },
  { label: 'X-Ray检测 (xray-inspection)', value: 'xray-inspection' },
  { label: '键合 (wire-bonder)', value: 'wire-bonder' },
  { label: '超声清洗 (ultrasonic-cleaner)', value: 'ultrasonic-cleaner' },
]

const formRef = ref()
const submitting = ref(false)
const form = reactive({
  device_type: 'reflow-oven',
  device_id: '',
  name: '',
  report_interval: 60,
})

const rules = {
  device_type: [{ required: true, message: '请选择工艺类型' }],
  device_id: [{ required: true, message: '请输入设备编号' }],
}

function resetForm() {
  form.device_type = 'reflow-oven'
  form.device_id = ''
  form.name = ''
  form.report_interval = 60
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const r = await fetch('/api/v1/mock/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (!r.ok) {
      const err = await r.json()
      ElMessage.error(err.detail || '创建失败')
      return
    }
    ElMessage.success('设备已创建')
    visible.value = false
    emit('created')
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 5: 写 DeviceConfigDrawer.vue + ExperimentPanel.vue**

```vue
<!-- web/src/components/mock/DeviceConfigDrawer.vue -->
<template>
  <el-drawer v-model="visible" title="参数配置" size="400px">
    <template v-if="device">
      <div class="config-device-info">
        <span class="config-device-name">{{ device.name || device.device_id }}</span>
        <el-tag size="small">{{ device.status }}</el-tag>
      </div>
      <el-form v-if="paramEntries.length" label-width="140px" size="default" class="config-form">
        <el-form-item v-for="p in paramEntries" :key="p.key" :label="p.key">
          <el-input-number
            v-model="p.value"
            :min="p.min"
            :max="p.max"
            :step="p.step"
            controls-position="right"
            style="width:100%"
          />
          <span v-if="p.unit" class="param-unit">{{ p.unit }}</span>
        </el-form-item>
      </el-form>
      <el-empty v-else description="该设备类型没有可配置参数" />
      <div class="config-actions" v-if="paramEntries.length">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveParams">保存</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean; device: any }>()
const emit = defineEmits(['update:visible', 'updated'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)

// Derive editable params from device.current_params with range info from DEVICE_TEMPLATES
// Use default ranges (hardcoded for the 5 mechanism types, fallback for others)
const RANGES: Record<string, Record<string, { min: number; max: number; step: number; unit: string }>> = {
  'reflow-oven': {
    temperature: { min: 100, max: 300, step: 1, unit: '°C' },
    conveyor_speed: { min: 10, max: 100, step: 1, unit: 'mm/s' },
    oxygen_ppm: { min: 0, max: 1000, step: 1, unit: 'ppm' },
  },
  'injection-molder': {
    melt_temp: { min: 150, max: 350, step: 1, unit: '°C' },
    injection_pressure: { min: 50, max: 200, step: 1, unit: 'MPa' },
    cooling_time: { min: 5, max: 60, step: 1, unit: 's' },
  },
  'oven-curing': {
    oven_temp: { min: 80, max: 200, step: 1, unit: '°C' },
    cure_duration_min: { min: 10, max: 120, step: 1, unit: 'min' },
    humidity_pct: { min: 10, max: 80, step: 1, unit: '%' },
    airflow_rate: { min: 5, max: 50, step: 1, unit: 'm³/h' },
  },
  'cnc-drill': {
    spindle_speed: { min: 5000, max: 25000, step: 100, unit: 'RPM' },
    feed_rate: { min: 100, max: 800, step: 10, unit: 'mm/min' },
    drill_depth: { min: 0.5, max: 12, step: 0.1, unit: 'mm' },
    coolant_flow: { min: 2, max: 15, step: 0.5, unit: 'L/min' },
  },
  'coating-machine': {
    spray_pressure: { min: 10, max: 60, step: 1, unit: 'psi' },
    coating_thickness_um: { min: 5, max: 100, step: 1, unit: 'μm' },
    cure_temp: { min: 60, max: 180, step: 1, unit: '°C' },
    conveyor_speed: { min: 0.5, max: 5.0, step: 0.1, unit: 'm/min' },
  },
}

interface ParamEntry { key: string; value: number; min: number; max: number; step: number; unit: string }

const paramEntries = computed<ParamEntry[]>(() => {
  if (!props.device?.current_params) return []
  const params = props.device.current_params
  const ranges = RANGES[props.device.device_type] || {}
  return Object.entries(params)
    .filter(([, v]) => typeof v === 'number')
    .map(([key, value]) => {
      const range = ranges[key] || { min: 0, max: (value as number) * 2 || 100, step: 1, unit: '' }
      return { key, value: value as number, ...range }
    })
})

async function saveParams() {
  if (!props.device) return
  saving.value = true
  try {
    const body: Record<string, number> = {}
    paramEntries.value.forEach(p => { body[p.key] = p.value })
    const r = await fetch(`/api/v1/mock/devices/${props.device.device_id}/params`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error('Save failed')
    ElMessage.success('参数已更新')
    emit('updated')
    visible.value = false
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config-device-info { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.config-device-name { font-weight: 600; }
.config-form { margin-bottom: 20px; }
.param-unit { margin-left: 8px; font-size: 12px; color: var(--el-text-color-secondary); }
.config-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
```

```vue
<!-- web/src/components/mock/ExperimentPanel.vue -->
<template>
  <el-drawer v-model="visible" title="实验任务" size="450px">
    <template v-if="device">
      <div class="exp-device-info">
        <span>{{ device.name || device.device_id }}</span>
        <el-tag size="small" :type="device.status === 'running' ? 'success' : 'info'">{{ device.status }}</el-tag>
      </div>

      <el-divider />

      <!-- 分配实验 -->
      <div class="exp-section">
        <h4>分配实验计划</h4>
        <el-select v-model="selectedPlanId" placeholder="选择实验计划" style="width:100%" filterable>
          <el-option v-for="p in availablePlans" :key="p.id" :label="`#${p.id} ${p.name}`" :value="p.id" />
        </el-select>
        <el-button type="primary" :disabled="!selectedPlanId" :loading="assigning" @click="assignExperiment" style="margin-top:10px;width:100%">
          分配到设备
        </el-button>
      </div>

      <el-divider />

      <!-- 当前实验进度 -->
      <div class="exp-section">
        <h4>当前实验</h4>
        <div v-if="currentExp" class="exp-progress">
          <el-progress :percentage="currentExp.progress" :status="currentExp.status" />
          <p class="exp-detail">Plan #{{ currentExp.planId }}: {{ currentExp.done }}/{{ currentExp.total }} runs</p>
        </div>
        <el-empty v-else description="无进行中的实验" :image-size="60" />
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean; device: any }>()
const emit = defineEmits(['update:visible'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const selectedPlanId = ref<number | null>(null)
const assigning = ref(false)
const availablePlans = ref<any[]>([])
const currentExp = ref<any>(null)

watch(() => props.device, async (d) => {
  if (!d) return
  try {
    const r = await fetch(`/api/v1/experiment/plans?process_type=${d.device_type}&limit=10`)
    if (r.ok) availablePlans.value = (await r.json()).filter((p: any) => p.status === 'draft' || p.status === 'ready')
  } catch { /* ignore */ }
}, { immediate: true })

async function assignExperiment() {
  if (!selectedPlanId.value || !props.device) return
  assigning.value = true
  try {
    const r = await fetch(`/api/v1/mock/devices/${props.device.device_id}/experiments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: selectedPlanId.value }),
    })
    if (r.ok) {
      ElMessage.success('实验已分配')
      currentExp.value = { planId: selectedPlanId.value, progress: 0, done: 0, total: '?', status: '' }
      selectedPlanId.value = null
    }
  } catch {
    ElMessage.error('分配失败')
  } finally {
    assigning.value = false
  }
}
</script>

<style scoped>
.exp-device-info { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-weight: 600; }
.exp-section h4 { font-size: 13px; margin: 0 0 10px 0; color: var(--el-text-color-secondary); }
.exp-progress { margin-bottom: 10px; }
.exp-detail { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; }
</style>
```

- [ ] **Step 6: 运行前端类型检查**

Run: `cd web && npm run typecheck`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add web/src/views/MockDevices.vue web/src/components/mock/ web/src/router/index.ts web/src/components/AppLayout.vue
git commit -m "feat: add mock device management page — device cards, config drawer, experiment panel"
```

---

### 验证

所有 Task 完成后运行：

```bash
# 后端
pytest --ignore=tests/integration -v

# 前端
cd web && npm run typecheck && npm run build
```

预期：全部通过，构建成功。
