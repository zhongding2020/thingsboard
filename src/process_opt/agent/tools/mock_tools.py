"""Agent tools for mock device management — list devices, dispatch experiments."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


def create_mock_tools(mock_manager: Any) -> list:
    """Create tools for interacting with mock devices.

    Args:
        mock_manager: MockManager instance (may be None if mock not available).
    """

    @tool
    async def list_mock_devices() -> str:
        """列出当前所有正在运行的模拟设备。返回设备ID、名称、类型、状态、产线。
        当需要将实验方案下发给模拟设备执行时，先用此工具查看可用的设备列表。
        注意：此工具列出的是模拟设备（mock），并非设备注册表中的全部设备。"""
        if mock_manager is None:
            return "模拟设备管理器不可用。"
        devices = mock_manager.list_all()
        if not devices:
            return "当前没有模拟设备。请在「工艺装备模拟器」页面创建并启动设备。"

        result = [
            f"## 模拟设备列表 (共 {len(devices)} 台)",
            "",
            "| 设备ID | 名称 | 类型 | 状态 | 产线 | 上报数 |",
            "|--------|------|------|------|------|--------|",
        ]
        for d in devices:
            result.append(
                f"| {d['device_id']} | {d.get('name', '-')} | {d['device_type']} | "
                f"{d['status']} | {d.get('line_name', d.get('line_id', '-'))} | "
                f"{d.get('report_count', 0)} |"
            )
        return "\n".join(result)

    @tool
    async def assign_experiment(mock_device_id: str, plan_id: int) -> str:
        """将实验方案下发给指定的模拟设备执行。设备会按照实验方案的运行顺序，
        逐次设置参数因子值、调用机理模型模拟、记录响应结果。

        Args:
            mock_device_id: 模拟设备ID，从 list_mock_devices 获取
            plan_id: 实验方案ID，从 list_experiment_plans 获取（必须是已保存的方案）

        下发后可通过设备的日志面板（SSE）实时观察实验进度。
        """
        if mock_manager is None:
            return "模拟设备管理器不可用。"
        try:
            await mock_manager.enqueue_experiment(mock_device_id, plan_id)
        except ValueError as e:
            # Device not found or other user-facing error
            return f"❌ 下发失败: {e}"

        dev = mock_manager.get(mock_device_id)
        status = dev.state if dev else "unknown"
        return (
            f"✅ 实验方案 #{plan_id} 已下发给设备 `{mock_device_id}`（当前状态: {status}）。\n\n"
            f"设备将在下一个实验轮询周期自动拉取方案并逐次执行。"
            f"可通过设备日志面板观察实时进度。"
        )

    return [list_mock_devices, assign_experiment]
