from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool


def create_parameter_tools(parameter_service: Any) -> list:
    @tool
    async def list_parameter_sets(device_type: str = "") -> str:
        """列出所有参数集。可选按 device_type 过滤。
        device_type: 可选，按设备类型过滤（如 adhesive_curing, injection_molding 等）。"""
        sets = await parameter_service.list_sets()
        if device_type:
            sets = [s for s in sets if getattr(s, "device_type", "") == device_type]

        if not sets:
            dtype_info = f" (类型: {device_type})" if device_type else ""
            return f"当前系统没有参数集{dtype_info}。"

        result = [f"## 参数集列表 (共 {len(sets)} 个)", ""]
        result.append("| ID | 名称 | 设备类型 | 版本 | 状态 | 创建者 |")
        result.append("|----|------|----------|------|------|--------|")
        for s in sets:
            status = getattr(s, "status", "unknown")
            status_emoji = {
                "draft": "📝", "proposed": "⏳", "approved": "✅",
                "rejected": "❌", "active": "🟢", "archived": "📦",
            }.get(status, "")
            result.append(
                f"| {s.id} | {s.name} | {s.device_type} | "
                f"v{s.version} | {status_emoji} {status} | {s.created_by} |"
            )
        return "\n".join(result)

    @tool
    async def get_parameter_set(set_id: int) -> str:
        """获取单个参数集的完整详情，包含所有参数项及其值。set_id: 参数集ID。"""
        ps = await parameter_service.get_set_with_items(set_id)
        if ps is None:
            return f"未找到参数集 `{set_id}`。"

        s = ps.parameter_set
        result = [
            f"## 参数集: {s.name}",
            "",
            f"- **ID**: {s.id}",
            f"- **设备类型**: {s.device_type}",
            f"- **版本**: v{s.version}",
            f"- **状态**: {s.status}",
            f"- **创建者**: {s.created_by}",
            f"- **备注**: {s.note or '-'}",
            "",
            "### 参数项",
            "| 参数键 | 值 | 单位 | 数据类型 |",
            "|--------|-----|------|----------|",
        ]
        for item in ps.items:
            val = item.param_value
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            result.append(
                f"| {item.param_key} | {val} | {item.unit or '-'} | {item.data_type} |"
            )
        return "\n".join(result)

    @tool
    async def get_latest_active_parameters(device_type: str) -> str:
        """获取指定设备类型当前激活（active）的参数集及其所有参数项。
        device_type: 设备类型标识（如 adhesive_curing, injection_molding 等）。"""
        ps = await parameter_service.get_latest(device_type)
        if ps is None:
            return f"设备类型 `{device_type}` 没有激活的参数集。"

        s = ps.parameter_set
        result = [
            f"## 当前激活参数: {s.name}",
            "",
            f"- **设备类型**: {s.device_type}",
            f"- **版本**: v{s.version}",
            f"- **激活时间**: {s.activated_at or '-'}",
            "",
            "| 参数键 | 当前值 | 单位 | 数据类型 |",
            "|--------|--------|------|----------|",
        ]
        for item in ps.items:
            val = item.param_value
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            result.append(
                f"| {item.param_key} | {val} | {item.unit or '-'} | {item.data_type} |"
            )
        return "\n".join(result)

    @tool
    async def submit_parameter_set(set_id: int, note: str = "") -> str:
        """提交参数集进入审批流程（draft → proposed）。set_id: 参数集ID。note: 可选备注。"""
        try:
            ps = await parameter_service.submit(set_id, actor="agent", note=note or None)
            return (
                f"✅ 参数集 `{ps.name}` (ID: {ps.id}) 已提交审批。\n"
                f"状态: {ps.status} | 版本: v{ps.version}"
            )
        except Exception as e:
            return f"❌ 提交失败: {e}"

    @tool
    async def approve_parameter_set(set_id: int, note: str = "") -> str:
        """批准参数集（proposed → approved）。set_id: 参数集ID。note: 可选审批意见。"""
        try:
            ps = await parameter_service.approve(set_id, actor="agent", note=note or None)
            return (
                f"✅ 参数集 `{ps.name}` (ID: {ps.id}) 已批准。\n"
                f"状态: {ps.status} | 版本: v{ps.version}"
            )
        except Exception as e:
            return f"❌ 批准失败: {e}"

    @tool
    async def reject_parameter_set(set_id: int, note: str = "") -> str:
        """驳回参数集（proposed → rejected）。set_id: 参数集ID。note: 驳回原因（建议填写）。"""
        try:
            ps = await parameter_service.reject(set_id, actor="agent", note=note or None)
            return (
                f"❌ 参数集 `{ps.name}` (ID: {ps.id}) 已驳回。\n"
                f"状态: {ps.status} | 版本: v{ps.version}\n"
                f"驳回原因: {note or '未提供'}"
            )
        except Exception as e:
            return f"❌ 驳回操作失败: {e}"

    return [
        list_parameter_sets,
        get_parameter_set,
        get_latest_active_parameters,
        submit_parameter_set,
        approve_parameter_set,
        reject_parameter_set,
    ]
