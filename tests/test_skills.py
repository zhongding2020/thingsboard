import pytest
from pathlib import Path
from process_opt.agent.skills import (
    _parse_skill_md,
    discover_skills,
    get_process_skills,
    get_capability_skills,
    SKILLS_DIR,
)


SAMPLE_MD = """---
name: test_process
display_name: 测试工艺
type: process
tools:
  - tool_a
  - tool_b
---

## 工艺参数

| temperature | 温度 | C | 100-200 | 150 | critical |
"""


class TestParseSkillMd:
    def test_parses_frontmatter_and_body(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")
        result = _parse_skill_md(md_file)

        assert result["name"] == "test_process"
        assert result["display_name"] == "测试工艺"
        assert result["type"] == "process"
        assert result["tools"] == ["tool_a", "tool_b"]
        assert "## 工艺参数" in result["system_prompt"]

    def test_system_prompt_is_body_text(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")
        result = _parse_skill_md(md_file)

        assert result["system_prompt"].startswith("## 工艺参数")
        assert "temperature" in result["system_prompt"]


class TestDiscoverSkills:
    def test_discovers_md_files_recursively(self, tmp_path: Path, monkeypatch):
        # Setup test directory
        proc = tmp_path / "process"
        cap = tmp_path / "capabilities"
        proc.mkdir()
        cap.mkdir()

        (proc / "adhesive_curing.md").write_text("""---
name: adhesive_curing
type: process
tools: []
---
工艺正文
""", encoding="utf-8")

        (cap / "spc.md").write_text("""---
name: spc-monitoring
type: capability
tools: []
---
SPC 正文
""", encoding="utf-8")

        monkeypatch.setattr("process_opt.agent.skills.SKILLS_DIR", tmp_path)
        registry = discover_skills()

        assert "adhesive_curing" in registry
        assert "spc-monitoring" in registry
        assert registry["adhesive_curing"]["type"] == "process"
        assert registry["spc-monitoring"]["type"] == "capability"


class TestFilterFunctions:
    def test_get_process_skills(self):
        registry = {
            "a": {"type": "process", "name": "a"},
            "b": {"type": "capability", "name": "b"},
            "c": {"type": "process", "name": "c"},
        }
        result = get_process_skills(registry)
        assert len(result) == 2
        assert all(s["type"] == "process" for s in result)

    def test_get_capability_skills(self):
        registry = {
            "a": {"type": "process", "name": "a"},
            "b": {"type": "capability", "name": "b"},
        }
        result = get_capability_skills(registry)
        assert len(result) == 1
        assert result[0]["name"] == "b"
