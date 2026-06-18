from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from process_opt.analysis.schemas import SpcRequest


def create_system_tools(
    line_device_repo: Any,
    analysis_service: Any = None,
) -> list:
    @tool
    async def list_production_lines() -> str:
        """列出所有产线信息。返回每条产线的名称、负责人、位置、设备数量。"""
        lines = await line_device_repo.list_lines()
        if not lines:
            return "当前系统没有注册的产线。"

        result = ["## 产线列表", ""]
        result.append(f"共 **{len(lines)}** 条产线：")
        result.append("")
        result.append("| 产线名称 | 负责人 | 位置 | 设备数 |")
        result.append("|----------|--------|------|--------|")
        for line in lines:
            result.append(
                f"| {line.get('name', '-')} | {line.get('responsible', '-')} | "
                f"{line.get('location', '-')} | {line.get('device_count', 0)} |"
            )
        return "\n".join(result)

    @tool
    async def get_production_line(line_id: str) -> str:
        """获取单条产线的详细信息，包含下属设备列表。line_id: 产线ID。"""
        line = await line_device_repo.get_line(line_id)
        if line is None:
            return f"未找到产线 `{line_id}`。"

        devices = await line_device_repo.list_devices(line_id=line_id)

        result = [
            f"## 产线详情: {line.get('name', line_id)}",
            "",
            f"- **负责人**: {line.get('responsible', '-')}",
            f"- **位置**: {line.get('location', '-')}",
            f"- **设备数量**: {len(devices)}",
        ]

        if devices:
            result.append("")
            result.append("### 下属设备")
            result.append("| 设备ID | 名称 | 类型 | 描述 |")
            result.append("|--------|------|------|------|")
            for d in devices:
                result.append(
                    f"| {d.get('id', '-')} | {d.get('name', '-')} | "
                    f"{d.get('type', '-')} | {d.get('description', '-')} |"
                )
        return "\n".join(result)

    @tool
    async def list_registered_devices(line_id: str = "") -> str:
        """列出系统中注册的所有设备。可选按产线过滤。line_id: 产线ID（可选，留空查全部）。"""
        lid = line_id if line_id else None
        devices = await line_device_repo.list_devices(line_id=lid)

        if not devices:
            return "当前系统没有注册的设备。"

        header = f"## 设备列表 (共 {len(devices)} 台)"
        if lid:
            header += f" — 产线 {lid}"

        result = [header, ""]
        result.append("| 设备ID | 名称 | 类型 | 所属产线 |")
        result.append("|--------|------|------|----------|")
        for d in devices:
            result.append(
                f"| {d.get('id', '-')} | {d.get('name', '-')} | "
                f"{d.get('type', '-')} | {d.get('line_name', '-')} |"
            )
        return "\n".join(result)

    @tool
    async def get_registered_device(device_id: str) -> str:
        """获取单个设备的详细信息。device_id: 设备ID。"""
        device = await line_device_repo.get_device(device_id)
        if device is None:
            return f"未找到设备 `{device_id}`。"

        result = [
            f"## 设备详情: {device.get('name', device_id)}",
            "",
            f"- **设备ID**: {device.get('id', '-')}",
            f"- **名称**: {device.get('name', '-')}",
            f"- **类型**: {device.get('type', '-')}",
            f"- **所属产线**: {device.get('line_name', '-')}",
            f"- **描述**: {device.get('description', '-')}",
        ]
        return "\n".join(result)

    @tool
    async def monitor_production_line(line_id: str) -> str:
        """对整条产线进行 SPC 监控总览。line_id: 产线ID。返回各设备的过程能力状态和产线整体评级。"""
        if analysis_service is None:
            return "SPC 分析服务不可用，无法监控产线。"

        line = await line_device_repo.get_line(line_id)
        if line is None:
            return f"未找到产线 `{line_id}`。"

        devices = await line_device_repo.list_devices(line_id=line_id)
        if not devices:
            return f"产线 `{line.get('name', line_id)}` 下没有注册设备。"

        device_summaries: list[dict] = []
        normal = abnormal = marginal = no_spec = 0

        for device in devices:
            try:
                spc_result = await analysis_service.spc(SpcRequest(
                    device_id=device["id"],
                ))
            except Exception:
                device_summaries.append({
                    "device_id": device["id"],
                    "device_name": device.get("name", device["id"]),
                    "type": device.get("type", "-"),
                    "status": "error",
                    "worst_cpk": None,
                    "param_count": 0,
                    "outlier_total": 0,
                })
                continue

            if not spc_result.overview:
                continue

            statuses = [ov.status for ov in spc_result.overview]
            if "abnormal" in statuses:
                dev_status = "abnormal"
            elif "marginal" in statuses:
                dev_status = "marginal"
            elif "no_spec" in statuses:
                dev_status = "no_spec"
            else:
                dev_status = "normal"

            cpks = [ov.cpk for ov in spc_result.overview if ov.cpk is not None]
            device_summaries.append({
                "device_id": device["id"],
                "device_name": device.get("name", device["id"]),
                "type": device.get("type", "-"),
                "status": dev_status,
                "worst_cpk": round(min(cpks), 2) if cpks else None,
                "param_count": len(spc_result.overview),
                "outlier_total": sum(ov.outlier_count for ov in spc_result.overview),
            })

            if dev_status == "abnormal":
                abnormal += 1
            elif dev_status == "marginal":
                marginal += 1
            elif dev_status == "no_spec":
                no_spec += 1
            else:
                normal += 1

        if abnormal > 0:
            line_status = "❌ 异常"
        elif marginal > 0:
            line_status = "⚠ 临界"
        elif no_spec > 0:
            line_status = "⚪ 无规格"
        elif normal > 0:
            line_status = "✅ 正常"
        else:
            line_status = "— 无数据"

        status_emoji = {"normal": "✅", "abnormal": "❌", "marginal": "⚠", "no_spec": "⚪", "error": "💥"}

        result = [
            f"## 产线监控: {line.get('name', line_id)}",
            "",
            f"**整体状态**: {line_status}",
            f"- 正常: {normal} | 异常: {abnormal} | 临界: {marginal} | 无规格: {no_spec}",
            "",
            "| 设备 | 类型 | 状态 | 最差Cpk | 参数数 | 异常数 |",
            "|------|------|------|---------|--------|--------|",
        ]
        for d in device_summaries:
            emoji = status_emoji.get(d["status"], "—")
            cpk_str = f"{d['worst_cpk']}" if d["worst_cpk"] is not None else "N/A"
            result.append(
                f"| {d['device_name']} | {d['type']} | {emoji} {d['status']} | "
                f"{cpk_str} | {d['param_count']} | {d['outlier_total']} |"
            )

        return "\n".join(result)

    return [
        list_production_lines,
        get_production_line,
        list_registered_devices,
        get_registered_device,
        monitor_production_line,
    ]
