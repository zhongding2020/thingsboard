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
