from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from process_opt.agent.tools.token_utils import truncate_output


def create_experiment_tools(experiment_repo: Any) -> list:
    @tool
    async def list_experiment_plans(limit: int = 20) -> str:
        """列出所有实验方案。limit: 返回数量上限（默认20）。
        返回实验方案的名称、方法、状态、运行次数和创建时间。"""
        plans = await experiment_repo.list_plans(limit)

        if not plans:
            return "当前系统没有实验方案。"

        result = [f"## 实验方案列表 (共 {len(plans)} 个)", ""]
        result.append("| ID | 名称 | 工艺 | 方法 | 状态 | 创建者 | 创建时间 |")
        result.append("|----|------|------|------|------|--------|----------|")
        for p in plans:
            status_emoji = {
                "draft": "📝", "in_progress": "🔄",
                "completed": "✅", "archived": "📦",
            }.get(p.status, "")
            created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-"
            result.append(
                f"| {p.id} | {p.name} | {p.process_type} | "
                f"{p.method} | {status_emoji} {p.status} | "
                f"{p.created_by} | {created} |"
            )
        result_text = "\n".join(result)
        result_text, _, _ = truncate_output(result_text, max_tokens=8000)
        return result_text

    @tool
    async def get_experiment_results(device_id: str, limit: int = 50) -> str:
        """读取指定设备上报的试验结果数据。按记录时间倒序返回。

        Args:
            device_id: 设备ID（必填）。从 list_mock_devices 或 list_registered_devices 获取。
            limit: 返回数量上限（默认50）。

        返回每条结果的方案ID、运行序号、响应值、记录时间。
        可配合 list_experiment_plans 和 get_experiment_plan 关联查看实验详情。
        """
        results = await experiment_repo.get_results_by_device(device_id, limit)

        if not results:
            return f"设备 `{device_id}` 尚未上报任何试验结果。"

        # Aggregate by plan
        plans: dict[int, list] = {}
        for r in results:
            plans.setdefault(r.plan_id, []).append(r)

        lines = [
            f"## 试验结果 — 设备 `{device_id}`",
            "",
            f"共 **{len(results)}** 条结果，涉及 **{len(plans)}** 个实验方案：",
            "",
            "| 方案ID | 运行序 | 响应值 | 记录时间 |",
            "|--------|--------|--------|----------|",
        ]
        for r in results:
            recorded = r.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if r.recorded_at else "-"
            resp = f"{r.response_value:.4f}" if r.response_value is not None else "N/A"
            lines.append(f"| {r.plan_id} | {r.run_order} | {resp} | {recorded} |")

        # Per-plan summary
        lines.append("")
        lines.append("### 按方案汇总")
        for plan_id, items in sorted(plans.items()):
            values = [r.response_value for r in items if r.response_value is not None]
            if values:
                avg = sum(values) / len(values)
                lines.append(
                    f"- 方案 #{plan_id}: {len(items)} 次运行, "
                    f"均值 {avg:.4f}, 最小 {min(values):.4f}, 最大 {max(values):.4f}"
                )

        result_text = "\n".join(lines)
        result_text, _, _ = truncate_output(result_text, max_tokens=8000)
        return result_text

    return [list_experiment_plans, get_experiment_results]
