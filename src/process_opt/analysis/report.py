from __future__ import annotations

import json
from datetime import datetime


def generate_markdown_report(
    title: str,
    sections: list[dict],
    metadata: dict | None = None,
) -> str:
    lines = [
        f"# {title}",
        f"\n> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if metadata:
        lines.append("## 基本信息\n")
        for k, v in metadata.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    for i, sec in enumerate(sections, 1):
        lines.append(f"## {i}. {sec.get('title', '')}")
        lines.append("")
        lines.append(sec.get("content", ""))
        lines.append("")

        if "table" in sec:
            tbl = sec["table"]
            if tbl.get("headers") and tbl.get("rows"):
                lines.append("| " + " | ".join(tbl["headers"]) + " |")
                lines.append("|" + "|".join(["------"] * len(tbl["headers"])) + "|")
                for row in tbl["rows"]:
                    lines.append("| " + " | ".join(str(c) for c in row) + " |")
                lines.append("")

        if "chart_data" in sec:
            cd = sec["chart_data"]
            chart_type = cd.get("type", "bar")
            if chart_type == "echarts":
                lines.append("```echarts")
                lines.append(json.dumps(cd["option"], ensure_ascii=False))
                lines.append("```")
                lines.append("")

    return "\n".join(lines)
