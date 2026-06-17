import json
import logging
from pathlib import Path
from typing import Any

from process_opt.knowledge.base import ProcessTemplate

logger = logging.getLogger(__name__)


class KnowledgeLoader:
    def __init__(self, templates_dir: Path | None = None) -> None:
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent / "templates"
        self._dir = templates_dir
        self._cache: dict[str, ProcessTemplate] = {}

    def list_processes(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for fpath in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text())
                results.append({
                    "process_type": data["process_type"],
                    "display_name": data.get("display_name", data["process_type"]),
                })
            except Exception as e:
                logger.warning("Failed to read template %s: %s", fpath, e)
        return results

    def load(self, process_type: str) -> ProcessTemplate | None:
        if process_type in self._cache:
            return self._cache[process_type]
        fpath = self._dir / f"{process_type}.json"
        if not fpath.exists():
            logger.warning("Template not found: %s", fpath)
            return None
        try:
            data: dict[str, Any] = json.loads(fpath.read_text())
            template = ProcessTemplate(**data)
            self._cache[process_type] = template
            return template
        except Exception as e:
            logger.error("Failed to load template %s: %s", fpath, e)
            return None

    def build_system_prompt(self, template: ProcessTemplate) -> str:
        lines: list[str] = []
        lines.append(f"你是一个{template.display_name}工艺参数分析专家。")
        if template.description:
            lines.append(f"\n{template.description}\n")
        if template.parameters:
            lines.append("## 工艺参数\n")
            lines.append("| 参数 | 单位 | 允许范围 | 目标范围 | 等级 |")
            lines.append("|------|------|----------|----------|------|")
            for p in template.parameters:
                lines.append(
                    f"| {p.name}({p.key}) | {p.unit} | {p.range.min}-{p.range.max} | "
                    f"{p.target.min}-{p.target.max} | {p.importance.value} |"
                )
        if template.quality_metrics:
            lines.append("\n## 质量指标\n")
            for m in template.quality_metrics:
                spec = []
                if m.usl is not None: spec.append(f"上限={m.usl}")
                if m.lsl is not None: spec.append(f"下限={m.lsl}")
                spec_str = f" ({', '.join(spec)})" if spec else ""
                lines.append(f"- {m.name}({m.key}): {m.unit}{spec_str}")
        if template.rules:
            lines.append("\n## 工艺规则\n")
            for r in template.rules:
                prefix = "禁止:" if r.type == "hard_constraint" else "建议:"
                lines.append(f"- [{r.type.value}] {prefix} {r.message}")
        if template.analysis_hints:
            lines.append("\n## 分析建议\n")
            for h in template.analysis_hints:
                lines.append(f"- {h}")
        lines.append("\n## 输出要求\n")
        lines.append("- 使用中文回答，用 Markdown 格式（表格、列表）展示")
        lines.append("- 不要输出原始 JSON")
        lines.append("- 引用工艺规则和约束条件")
        return "\n".join(lines)
