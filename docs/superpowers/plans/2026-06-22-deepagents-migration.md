# DeepAgents Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the LangGraph agent kernel (StateGraph + Supervisor + 3 Workers) to DeepAgents framework with Markdown-based dual-layer Skills system.

**Architecture:** Replace hand-written StateGraph with `create_deep_agent()` + 5 middleware stack. Skills organized as Markdown files in `process/` (session-level) and `capabilities/` (on-demand). API routes rewrite to use `astream_events()` AsyncGenerator. Frontend SSE events maintained compatible.

**Tech Stack:** Python 3.11+, DeepAgents >=0.5,<1.0, langchain-core, langchain-openai, FastAPI, PyYAML

## Global Constraints

- `deepagents>=0.5,<1.0` pinned for API stability
- All tool functions files unchanged — only wiring changes in main.py
- Frontend zero changes — SSE event format stays backward-compatible
- All API paths unchanged — POST /session, POST /chat, GET /chat/{id}/events, GET /session/{id}/messages, GET /processes, POST /upload
- Help command `?` / `help` must still work (embedded in system_prompt)
- 8 process types must all be supported: adhesive_curing, injection_molding, die_casting, cnc_machining, reflow_soldering, heat_treatment, welding, powder_coating
- `pyyaml` added as explicit dependency (for frontmatter parsing)
- Existing `pyproject.toml` `[tool.pytest.ini_options]` pythonpath = `["src"]`

---

## File Structure

| Action | Path |
|--------|------|
| Create | `src/process_opt/agent/skills/__init__.py` |
| Create | `src/process_opt/agent/skills/process/adhesive_curing.md` |
| Create | `src/process_opt/agent/skills/process/injection_molding.md` |
| Create | `src/process_opt/agent/skills/process/die_casting.md` |
| Create | `src/process_opt/agent/skills/process/cnc_machining.md` |
| Create | `src/process_opt/agent/skills/process/reflow_soldering.md` |
| Create | `src/process_opt/agent/skills/process/heat_treatment.md` |
| Create | `src/process_opt/agent/skills/process/welding.md` |
| Create | `src/process_opt/agent/skills/process/powder_coating.md` |
| Create | `src/process_opt/agent/skills/capabilities/spc-monitoring.md` |
| Create | `src/process_opt/agent/skills/capabilities/doe-design.md` |
| Create | `src/process_opt/agent/skills/capabilities/correlation-analysis.md` |
| Create | `src/process_opt/agent/skills/capabilities/parameter-recommend.md` |
| Create | `src/process_opt/agent/skills/capabilities/report-generation.md` |
| Create | `src/process_opt/agent/skills/capabilities/data-profiling.md` |
| Create | `src/process_opt/agent/skills/capabilities/product-tracing.md` |
| Create | `src/process_opt/agent/skills/capabilities/line-monitoring.md` |
| Create | `src/process_opt/agent/deep_agent.py` |
| Create | `tests/test_skills.py` |
| Create | `tests/test_deep_agent.py` |
| Modify | `pyproject.toml` — add `deepagents`, `pyyaml` |
| Modify | `src/process_opt/api/agent_routes.py` — full rewrite |
| Modify | `src/process_opt/api/app.py` — change create_app params + route registration |
| Modify | `src/process_opt/api/main.py` — tool pool dict + agent factory |
| Delete | `src/process_opt/agent/graph.py` |
| Delete | `src/process_opt/agent/state.py` |
| Delete | `src/process_opt/agent/nodes/supervisor.py` |
| Delete | `src/process_opt/agent/nodes/worker.py` |

---

### Task 1: Dependencies and Scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `src/process_opt/agent/skills/__init__.py` (empty placeholder)
- Create: `src/process_opt/agent/skills/process/.gitkeep`
- Create: `src/process_opt/agent/skills/capabilities/.gitkeep`

**Interfaces:**
- Produces: `src/process_opt/agent/skills/` directory tree for Tasks 2-4
- Produces: `deepagents` and `pyyaml` in lock file for all later tasks

- [ ] **Step 1: Add deepagents and pyyaml to pyproject.toml**

In `pyproject.toml`, under `[project]` `dependencies`, add:

```
"deepagents>=0.5,<1.0",
"pyyaml>=6.0",
```

Run lock:

```bash
cd /Users/zhongding/dev/thingsboard && uv lock
```

Expected: `uv.lock` updated with deepagents and its transitive deps.

- [ ] **Step 2: Create skills directory structure**

```bash
mkdir -p src/process_opt/agent/skills/process
mkdir -p src/process_opt/agent/skills/capabilities
touch src/process_opt/agent/skills/process/.gitkeep
touch src/process_opt/agent/skills/capabilities/.gitkeep
touch src/process_opt/agent/skills/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock src/process_opt/agent/skills/
git commit -m "chore: add deepagents dependency, create skills directory structure"
```

---

### Task 2: Skills Core — discover / parse / filter

**Files:**
- Modify: `src/process_opt/agent/skills/__init__.py`

**Interfaces:**
- Produces:
  - `discover_skills() -> dict[str, dict]` — recursive scan, returns `{name: skill_dict}`
  - `get_process_skills(registry: dict) -> list[dict]` — filter `type == "process"`
  - `get_capability_skills(registry: dict) -> list[dict]` — filter `type == "capability"`
  - `SKILLS_DIR: Path` — package root Path

- [ ] **Step 1: Write the test file**

Create `tests/test_skills.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/test_skills.py -v
```

Expected: FAIL — `_parse_skill_md` not defined.

- [ ] **Step 3: Implement `__init__.py`**

Write `src/process_opt/agent/skills/__init__.py`:

```python
"""Skills system — Markdown-based process and capability skills.

Directory layout:
    skills/
    ├── process/        # type=process skills (session-level, loaded at creation)
    ├── capabilities/   # type=capability skills (on-demand, triggered by LLM)
    └── __init__.py     # This file
"""

from __future__ import annotations

import yaml
from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def _parse_skill_md(path: Path) -> dict:
    """Parse a Markdown skill file: YAML frontmatter + Markdown body.

    The body becomes the ``system_prompt`` field — no programmatic assembly.
    """
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta: dict = yaml.safe_load(fm)
    meta["system_prompt"] = body.strip()
    return meta


def discover_skills() -> dict[str, dict]:
    """Recursively scan the skills/ directory for ``*.md`` files.

    Returns a dict keyed by skill ``name`` (from frontmatter).
    Duplicate names: last file wins (undefined order — don't duplicate).
    """
    registry: dict[str, dict] = {}
    for md_file in SKILLS_DIR.rglob("*.md"):
        skill = _parse_skill_md(md_file)
        registry[skill["name"]] = skill
    return registry


def get_process_skills(registry: dict) -> list[dict]:
    """Return all skills with ``type: process``."""
    return [s for s in registry.values() if s.get("type") == "process"]


def get_capability_skills(registry: dict) -> list[dict]:
    """Return all skills with ``type: capability``."""
    return [s for s in registry.values() if s.get("type") == "capability"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/test_skills.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/agent/skills/__init__.py tests/test_skills.py
git commit -m "feat: add skills core — discover, parse, filter Markdown skills"
```

---

### Task 3: Process Skills — 8 Markdown files from JSON knowledge templates

**Files:**
- Create: `src/process_opt/agent/skills/process/adhesive_curing.md`
- Create: `src/process_opt/agent/skills/process/injection_molding.md`
- Create: `src/process_opt/agent/skills/process/die_casting.md`
- Create: `src/process_opt/agent/skills/process/cnc_machining.md`
- Create: `src/process_opt/agent/skills/process/reflow_soldering.md`
- Create: `src/process_opt/agent/skills/process/heat_treatment.md`
- Create: `src/process_opt/agent/skills/process/welding.md`
- Create: `src/process_opt/agent/skills/process/powder_coating.md`

**Interfaces:**
- Consumes: `knowledge/templates/*.json` — each converted to `.md` with frontmatter
- Produces: 8 `.md` files discoverable by Task 2's `discover_skills()`

**Conversion rules (JSON → Markdown frontmatter):**
- `process_type` → `name`
- `display_name` → `display_name`
- Add `type: process`
- Add `description` from JSON
- `tools`: fixed list per the spec (query_records, get_stats, run_spc, analyze_correlation, run_regression, analyze_importance, design_experiment, recommend_params, trace_product, generate_report, etc.)
- Body: `## 工艺参数` table from JSON parameters (flatten `range.min–range.max`, flatten `target.min–target.max`)
- Body: `## 质量指标` table from JSON quality_metrics
- Body: `## 规则约束` list from JSON rules (type → `[hard]`/`[soft]`, expression → inline code)
- Body: `## 分析提示` list from JSON analysis_hints

- [ ] **Step 1: Write `adhesive_curing.md`**

Write `src/process_opt/agent/skills/process/adhesive_curing.md`:

```markdown
---
name: adhesive_curing
display_name: 点胶固化
type: process
description: 点胶固化工艺，包含点胶（dispensing）和固化（curing）两个步骤。点胶步骤控制胶量、压力；固化步骤控制温度和时间。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| cure_temp | 固化温度 | °C | 80–180 | 120–150 | critical |
| cure_time | 固化时间 | min | 10–120 | 30–60 | critical |
| glue_amount | 胶量 | mg | 5–50 | 15–30 | critical |
| dispense_pressure | 点胶压力 | kPa | 50–300 | 100–200 | important |
| ambient_humidity | 环境湿度 | %RH | 20–80 | 30–60 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| shear_strength | 剪切强度 | kgf/cm² | 80 | — |
| bubble_rate | 气泡率 | % | — | 5.0 |
| glue_overflow | 胶水溢出量 | mm | — | 1.0 |

## 规则约束

- [hard] cure_temp > 180 → 固化温度不得超过180°C，否则会导致胶水老化
- [hard] cure_time < 10 → 固化时间不得少于10分钟
- [soft] cure_temp > 150 and cure_time < 20 → 高温短时间可能导致固化不均匀
- [soft] glue_amount > 40 → 胶量偏大可能导致溢出，建议控制在15-30mg
- [dependency] cure_temp increase → 温度每升高10°C，固化时间可减少约5分钟

## 分析提示

- 优先分析固化温度、固化时间、胶量与剪切强度的相关性
- 如果气泡率高，检查固化温度和时间组合
- 如果胶水溢出量大，检查胶量和点胶压力
```

- [ ] **Step 2: Write remaining 7 process skill files**

Create each file following the same format as above, reading data from the corresponding JSON file in `src/process_opt/knowledge/templates/`.

`injection_molding.md` — from `injection_molding.json`:

```markdown
---
name: injection_molding
display_name: 注塑成型
type: process
description: 注塑成型工艺，包含塑化、注射、保压、冷却四个阶段。关键控制参数包括温度、压力、速度和时间。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| melt_temp | 熔体温度 | °C | 180–280 | 220–250 | critical |
| mold_temp | 模具温度 | °C | 40–120 | 60–80 | critical |
| injection_pressure | 注射压力 | MPa | 50–180 | 90–130 | critical |
| holding_pressure | 保压压力 | MPa | 30–120 | 50–80 | important |
| cooling_time | 冷却时间 | s | 5–40 | 15–25 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| weight | 产品重量 | g | 45 | 50 |
| dimension_x | X方向尺寸 | mm | 99.8 | 100.2 |
| warpage | 翘曲量 | mm | — | 0.3 |

## 规则约束

- [hard] melt_temp > 280 → 熔体温度过高会导致材料降解
- [hard] cooling_time < 5 → 冷却时间过短会导致产品变形
- [soft] injection_pressure > 150 → 过高的注射压力可能导致模具磨损

## 分析提示

- 熔体温度、模具温度是影响尺寸精度的主要因素
- 翘曲通常与冷却时间和模具温度相关
```

`die_casting.md` — from `die_casting.json`:

```markdown
---
name: die_casting
display_name: 压铸
type: process
description: 压铸工艺，将熔融金属在高压下注入模具型腔。关键参数包括压射压力、温度、速度和冷却条件。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| melt_temp | 合金液温度 | °C | 620–680 | 640–660 | critical |
| die_temp | 模具温度 | °C | 150–250 | 180–220 | critical |
| injection_speed | 压射速度 | m/s | 1.5–6.0 | 3.0–4.5 | critical |
| casting_pressure | 铸造压力 | MPa | 50–120 | 70–90 | important |
| holding_time | 保压时间 | s | 2–10 | 4–7 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| porosity | 孔隙率 | % | — | 2.0 |
| tensile_strength | 抗拉强度 | MPa | 180 | — |
| surface_roughness | 表面粗糙度 | μm | — | 6.3 |

## 规则约束

- [hard] melt_temp > 680 → 合金液温度过高会导致氧化和烧损
- [hard] injection_speed < 1.5 → 压射速度过低会导致充型不足
- [soft] die_temp < 160 → 模具温度偏低可能产生冷隔缺陷

## 分析提示

- 孔隙率与压射速度和铸造压力高度相关
- 抗拉强度受合金液温度和保压时间影响大
- 表面粗糙度主要与模具温度和压射速度相关
```

`cnc_machining.md` — from `cnc_machining.json`:

```markdown
---
name: cnc_machining
display_name: CNC加工
type: process
description: CNC（计算机数控）加工工艺，通过程序控制刀具和工件的相对运动实现精密加工。关键参数包括转速、进给、切深和刀具参数。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| spindle_speed | 主轴转速 | rpm | 2000–12000 | 5000–8000 | critical |
| feed_rate | 进给速度 | mm/min | 100–500 | 200–350 | critical |
| cut_depth | 切削深度 | mm | 0.1–3.0 | 0.5–1.5 | important |
| tool_diameter | 刀具直径 | mm | 1–20 | 4–12 | important |
| coolant_flow | 冷却液流量 | L/min | 2–10 | 4–7 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| dimension_tolerance | 尺寸公差 | μm | — | 20 |
| surface_roughness | 表面粗糙度 | Ra | — | 1.6 |
| roundness | 圆度 | μm | — | 10 |

## 规则约束

- [hard] spindle_speed > 12000 → 转速过高会损坏刀具
- [hard] cut_depth > 3.0 → 切削深度过大会导致加工振动
- [soft] feed_rate > 400 → 进给速度过快会降低表面质量

## 分析提示

- 表面粗糙度主要受主轴转速和进给速度影响
- 尺寸公差与刀具直径和切削深度相关
- 圆度受主轴转速和进给比影响
```

`reflow_soldering.md` — from `reflow_soldering.json`:

```markdown
---
name: reflow_soldering
display_name: 回流焊
type: process
description: 回流焊（Reflow Soldering）工艺，通过预热、保温、回流和冷却四个温区实现SMT焊接。关键参数包括各温区温度、链速和气氛控制。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| preheat_temp | 预热温度 | °C | 140–180 | 150–170 | critical |
| soak_temp | 保温温度 | °C | 170–200 | 180–195 | critical |
| reflow_peak_temp | 回流峰值温度 | °C | 220–250 | 235–245 | critical |
| conveyor_speed | 链速 | cm/min | 40–120 | 60–90 | important |
| nitrogen_flow | 氮气流量 | L/min | 0–30 | 10–20 | auxiliary |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| solder_joint_strength | 焊点强度 | N | 15 | — |
| void_rate | 空洞率 | % | — | 25 |
| wetting_angle | 润湿角 | ° | — | 30 |

## 规则约束

- [hard] reflow_peak_temp > 250 → 峰值温度过高会损坏元器件
- [hard] preheat_temp < 130 → 预热不足会导致热冲击
- [soft] conveyor_speed > 100 → 链速过快可能导致冷焊

## 分析提示

- 焊点强度主要受回流峰值温度和保温时间影响
- 空洞率与预热温度曲线和助焊剂活化相关
- 润湿角与峰值温度和氮气流量相关
```

`heat_treatment.md` — from `heat_treatment.json`:

```markdown
---
name: heat_treatment
display_name: 热处理
type: process
description: 金属热处理工艺，通过加热、保温和冷却改变金属内部组织结构。关键参数包括加热温度、保温时间、冷却速率和气氛。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| austenitizing_temp | 奥氏体化温度 | °C | 800–1050 | 850–950 | critical |
| holding_time | 保温时间 | min | 15–120 | 30–60 | critical |
| quench_rate | 淬火冷却速率 | °C/s | 20–200 | 50–120 | critical |
| tempering_temp | 回火温度 | °C | 150–650 | 200–500 | important |
| carbon_potential | 碳势 | %C | 0.2–1.2 | 0.4–0.8 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| hardness | 硬度 | HRC | 40 | 60 |
| case_depth | 硬化层深度 | mm | 0.5 | 2.0 |
| distortion | 变形量 | mm | — | 0.1 |

## 规则约束

- [hard] austenitizing_temp > 1050 → 温度过高会导致晶粒粗化
- [hard] quench_rate < 20 → 冷却速率不足会影响马氏体转变
- [soft] tempering_temp > 600 → 回火温度过高会过度软化

## 分析提示

- 硬度主要受奥氏体化温度和淬火速率影响
- 硬化层深度与碳势和保温时间相关
- 变形量与淬火速率和工件尺寸相关
```

`welding.md` — from `welding.json`:

```markdown
---
name: welding
display_name: 焊接
type: process
description: 金属焊接工艺，通过加热或加压使工件连接。关键参数包括电流、电压、焊接速度和保护气体流量。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| welding_current | 焊接电流 | A | 80–300 | 150–250 | critical |
| arc_voltage | 电弧电压 | V | 16–35 | 22–30 | critical |
| welding_speed | 焊接速度 | cm/min | 15–80 | 30–50 | important |
| gas_flow | 保护气流量 | L/min | 8–25 | 12–20 | important |
| wire_feed_rate | 送丝速度 | m/min | 2–12 | 5–9 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| tensile_strength | 抗拉强度 | MPa | 400 | — |
| weld_penetration | 熔深 | mm | 2.0 | 5.0 |
| porosity_level | 气孔等级 | grade | — | 2 |

## 规则约束

- [hard] welding_current > 300 → 电流过大会烧穿工件
- [hard] welding_speed < 15 → 速度过低会导致过热和变形
- [soft] gas_flow < 10 → 保护气不足会产生气孔

## 分析提示

- 抗拉强度与焊接电流和焊接速度高度相关
- 熔深受焊接电流和电弧电压影响大
- 气孔等级与保护气流量和焊接速度相关
```

`powder_coating.md` — from `powder_coating.json`:

```markdown
---
name: powder_coating
display_name: 粉末涂装
type: process
description: 粉末涂装工艺，通过静电喷涂将粉末涂料附着在工件表面，经烘烤固化形成涂层。关键参数包括电压、气压、烘烤温度和链速。
tools:
  - query_records
  - get_devices
  - get_stats
  - profile_data
  - analyze_correlation
  - analyze_pareto
  - run_regression
  - run_spc
  - analyze_importance
  - design_experiment
  - analyze_experiment
  - recommend_params
  - optimize_parameters
  - trace_product
  - trace_product_full
  - build_dataset
  - preview_dataset
  - generate_report
---

## 工艺参数

| 参数 | 名称 | 单位 | 范围 | 目标值 | 重要性 |
|------|------|------|------|--------|--------|
| electrostatic_voltage | 静电电压 | kV | 40–100 | 60–80 | critical |
| atomizing_pressure | 雾化气压 | MPa | 0.1–0.5 | 0.2–0.35 | critical |
| curing_temp | 固化温度 | °C | 160–220 | 180–200 | critical |
| curing_time | 固化时间 | min | 10–30 | 15–20 | important |
| conveyor_speed | 链速 | m/min | 1.0–4.0 | 2.0–3.0 | important |

## 质量指标

| 指标 | 名称 | 单位 | LSL | USL |
|------|------|------|-----|-----|
| coating_thickness | 涂层厚度 | μm | 60 | 100 |
| adhesion | 附着力 | grade | 0 | 1 |
| gloss | 光泽度 | GU | 80 | 95 |

## 规则约束

- [hard] curing_temp > 220 → 固化温度过高会导致涂层变色
- [hard] curing_time < 10 → 固化时间不足会导致涂层固化不完全
- [soft] electrostatic_voltage < 45 → 静电电压过低会导致上粉率下降

## 分析提示

- 涂层厚度主要受静电电压和雾化气压影响
- 附着力与固化温度和固化时间高度相关
- 光泽度受固化温度曲线和粉末粒度影响
```

- [ ] **Step 3: Verify skills are discoverable**

```bash
cd /Users/zhongding/dev/thingsboard && uv run python -c "
from process_opt.agent.skills import discover_skills, get_process_skills
registry = discover_skills()
skills = get_process_skills(registry)
names = [s['name'] for s in skills]
print(f'Found {len(skills)} process skills: {names}')
assert len(skills) == 8, f'Expected 8, got {len(skills)}'
print('OK')
"
```

Expected: "Found 8 process skills: [...] OK"

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/agent/skills/process/
git commit -m "feat: add 8 process skills (Markdown) converted from JSON knowledge templates"
```

---

### Task 4: Capability Skills — 8 Markdown files

**Files:**
- Create: `src/process_opt/agent/skills/capabilities/spc-monitoring.md`
- Create: `src/process_opt/agent/skills/capabilities/doe-design.md`
- Create: `src/process_opt/agent/skills/capabilities/correlation-analysis.md`
- Create: `src/process_opt/agent/skills/capabilities/parameter-recommend.md`
- Create: `src/process_opt/agent/skills/capabilities/report-generation.md`
- Create: `src/process_opt/agent/skills/capabilities/data-profiling.md`
- Create: `src/process_opt/agent/skills/capabilities/product-tracing.md`
- Create: `src/process_opt/agent/skills/capabilities/line-monitoring.md`

**Interfaces:**
- Consumes: Tool names from global tool pool (Tasks 6-7)
- Produces: 8 .md files, `type: capability`, each with triggers + tools + analysis steps

- [ ] **Step 1: Write all 8 capability skill files**

Write `src/process_opt/agent/skills/capabilities/spc-monitoring.md`:

```markdown
---
name: spc-monitoring
display_name: SPC 监控
type: capability
description: 统计过程控制（I-MR 控制图、Cp/Cpk 过程能力分析）
triggers:
  - spc
  - 控制图
  - 过程能力
  - cpk
  - cp
  - 监控
tools:
  - run_spc
  - query_records
  - get_stats
---

## 功能

对指定设备或产线执行 SPC 监控，生成 I-MR 控制图和过程能力指数（Cp/Cpk）。

## 使用场景

- 用户询问设备过程是否稳定
- 用户要求查看控制图
- 用户询问 Cp/Cpk 值

## 分析步骤

1. 先用 `query_records` 获取该设备最近的数据
2. 用 `run_spc` 对关键参数执行 SPC 分析
3. 判断：Cp < 1.0 → 能力不足；1.0 ≤ Cp < 1.33 → 能力一般；Cp ≥ 1.33 → 能力充分
4. 用 Markdown 表格输出 SPC 结论，含控制图数据

## 输出格式

| 参数 | 均值 | UCL | LCL | Cp | Cpk | 判定 |
|------|------|-----|-----|-----|-----|------|
```

Write `src/process_opt/agent/skills/capabilities/doe-design.md`:

```markdown
---
name: doe-design
display_name: DOE 实验设计
type: capability
description: 实验设计（全因子、Box-Behnken、中心复合、田口方法）+ ANOVA 方差分析
triggers:
  - doe
  - 实验设计
  - 田口
  - box-behnken
  - 全因子
  - 因子
  - anova
  - 方差分析
tools:
  - design_experiment
  - analyze_experiment
  - build_dataset
---

## 功能

为指定工艺设计 DOE 实验方案，分析实验结果（ANOVA），识别显著因子和最优水平组合。

## 使用场景

- 用户要优化工艺参数但不知道哪些因子关键
- 用户需要系统性的实验方案
- 用户要分析因子间的交互效应

## 分析步骤

1. 确认目标工艺类型和关注的因子（通常从工艺参数表中选择 2-5 个 critical 参数）
2. 根据因子数和需求选择设计类型：2-3 因子 → 全因子，3-5 因子 → Box-Behnken，多因子筛选 → 田口
3. 调用 `design_experiment` 生成实验方案
4. 如果有实验结果数据，调用 `analyze_experiment` 做 ANOVA
5. 用 Markdown 表格展示因子水平表和 ANOVA 结果

## 输出格式

因子水平表 + ANOVA 效应分析 + 显著因子排序
```

Write `src/process_opt/agent/skills/capabilities/correlation-analysis.md`:

```markdown
---
name: correlation-analysis
display_name: 相关性分析
type: capability
description: Pearson/Spearman 相关系数、热力图、帕累托分析
triggers:
  - 相关性
  - 相关系数
  - 热力图
  - 帕累托
  - pearson
  - spearman
tools:
  - analyze_correlation
  - analyze_pareto
  - build_dataset
  - preview_dataset
---

## 功能

分析工艺参数与质量指标之间的相关性，输出相关系数矩阵和帕累托排序。

## 使用场景

- 用户要了解哪些参数对质量影响最大
- 用户要查看参数间的共线性
- 用户要做因子筛选

## 分析步骤

1. 先确认数据集（如已上传则用已有 dataset_id，否则用 `build_dataset` 构建）
2. 用 `analyze_correlation` 执行相关性分析（默认 Pearson）
3. 如果参数数量较多（>5），用 `analyze_pareto` 做帕累托排序
4. 用 Markdown 表格输出相关系数矩阵

## 输出格式

| 参数 | 相关系数 | 方向 | 显著性 |
|------|----------|------|--------|
```

Write `src/process_opt/agent/skills/capabilities/parameter-recommend.md`:

```markdown
---
name: parameter-recommend
display_name: 参数推荐
type: capability
description: 网格搜索/LHS 搜索最优参数组合，附带规则校验和预测质量值
triggers:
  - 推荐
  - 优化
  - 最优
  - 改进
  - 提高
  - 降低
  - 改善
tools:
  - recommend_params
  - optimize_parameters
  - run_regression
  - build_dataset
---

## 功能

基于历史数据和回归模型，搜索满足工艺规则约束的最优参数组合。

## 使用场景

- 用户要提升某个质量指标
- 用户要降低不良率
- 用户要在多个约束下寻找最优参数

## 分析步骤

1. 确认优化目标（指标名称 + 方向：maximize/minimize/target）
2. 如果有约束条件（如"不能超过某温度"），先确认
3. 用 `build_dataset` 构建训练数据集
4. 用 `run_regression` 建立预测模型
5. 用 `recommend_params` 或 `optimize_parameters` 搜索最优参数
6. 校验推荐参数是否符合工艺规则
7. 用 Markdown 表格输出推荐参数 + 预测值 + 置信度 + 与当前参数的对比

## 输出格式

| 参数 | 当前值 | 推荐值 | 单位 | 预测指标 | 提升幅度 |
|------|--------|--------|------|----------|----------|
```

Write `src/process_opt/agent/skills/capabilities/report-generation.md`:

```markdown
---
name: report-generation
display_name: 报告生成
type: capability
description: 生成工艺分析报告（Markdown 格式），汇总分析结果
triggers:
  - 报告
  - 总结
  - 汇总
  - 生成报告
tools:
  - generate_report
---

## 功能

基于对话历史中的分析数据，生成结构化 Markdown 工艺分析报告。

## 使用场景

- 用户完成了多步分析后要求汇总
- 用户要求导出分析报告

## 分析步骤

1. 回顾对话历史中的分析结果
2. 调用 `generate_report` 组装报告
3. 报告应包含：工艺概况、数据分析、模型结果、推荐参数、风险提示

## 输出格式

完整的 Markdown 文档，包含标题层级、表格、结论和建议
```

Write `src/process_opt/agent/skills/capabilities/data-profiling.md`:

```markdown
---
name: data-profiling
display_name: 数据画像
type: capability
description: 统计数据分布（均值、标准差、极值、异常值检测）
triggers:
  - 画像
  - 概况
  - 统计
  - 分布
  - 异常值
  - 趋势
tools:
  - profile_data
  - query_records
  - get_stats
---

## 功能

对指定设备和时间范围的工艺数据进行统计分析，检测异常值。

## 使用场景

- 用户要了解设备运行概况
- 用户要查看数据分布
- 用户要识别异常数据点

## 分析步骤

1. 用 `query_records` 或 `get_stats` 获取数据
2. 用 `profile_data` 执行统计画像
3. 用 Markdown 表格输出统计量

## 输出格式

| 参数 | 均值 | 标准差 | 最小值 | 最大值 | 异常值数 |
|------|------|--------|--------|--------|----------|
```

Write `src/process_opt/agent/skills/capabilities/product-tracing.md`:

```markdown
---
name: product-tracing
display_name: 产品追溯
type: capability
description: 按条码追溯完整生产链路（工艺参数 + 质检结果）
triggers:
  - 追溯
  - 条码
  - 链路
  - 产品
tools:
  - trace_product
  - trace_product_full
---

## 功能

通过产品条码追溯完整的生产参数和质检记录。

## 使用场景

- 用户要查看某个产品的生产过程
- 用户要排查质量问题的根因
- 用户要对比良品和不良品的工艺差异

## 分析步骤

1. 确认产品条码（barcode）
2. 用 `trace_product` 或 `trace_product_full` 查询
3. 用 Markdown 表格展示工艺参数 + 质检结果
4. 如有异常，标注偏差项

## 输出格式

| 阶段 | 参数 | 实际值 | 目标值 | 偏差 | 状态 |
|------|------|--------|--------|------|------|
```

Write `src/process_opt/agent/skills/capabilities/line-monitoring.md`:

```markdown
---
name: line-monitoring
display_name: 产线监控
type: capability
description: 产线级 SPC 总览，多设备状态汇总
triggers:
  - 产线
  - 生产线
  - 设备状态
  - 线体
tools:
  - list_production_lines
  - get_production_line
  - list_registered_devices
  - monitor_production_line
---

## 功能

对产线进行全景监控，汇总产线下所有设备的 SPC 状态。

## 使用场景

- 用户要查看产线整体状况
- 用户要对比产线内设备的性能差异
- 用户要识别产线瓶颈

## 分析步骤

1. 用 `list_production_lines` 确定目标产线
2. 用 `get_production_line` 获取产线详情
3. 用 `monitor_production_line` 执行产线级 SPC
4. 用 Markdown 表格汇总各设备状态

## 输出格式

| 设备 | 关键参数 | Cp | Cpk | 状态 | 建议 |
|------|----------|-----|-----|------|------|
```

- [ ] **Step 2: Verify capability skills are discoverable**

```bash
cd /Users/zhongding/dev/thingsboard && uv run python -c "
from process_opt.agent.skills import discover_skills, get_capability_skills
registry = discover_skills()
skills = get_capability_skills(registry)
names = [s['name'] for s in skills]
print(f'Found {len(skills)} capability skills: {names}')
assert len(skills) == 8, f'Expected 8, got {len(skills)}'
print('OK')
"
```

Expected: "Found 8 capability skills: [...] OK"

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/skills/capabilities/
git commit -m "feat: add 8 capability skills (SPC, DOE, correlation, recommend, report, profiling, tracing, line-monitoring)"
```

---

### Task 5: Deep Agent Factory

**Files:**
- Create: `src/process_opt/agent/deep_agent.py`

**Interfaces:**
- Consumes: `discover_skills()`, `get_capability_skills()` from Task 2
- Produces: `create_process_agent(llm, process_type, tool_pool) -> DeepAgent`

- [ ] **Step 1: Write the test**

Create `tests/test_deep_agent.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from process_opt.agent.deep_agent import create_process_agent


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_tool_pool():
    async def fake_query_records(**kwargs):
        return "mock result"
    async def fake_run_spc(**kwargs):
        return "spc result"
    return {
        "query_records": fake_query_records,
        "run_spc": fake_run_spc,
    }


@pytest.fixture
def mock_registry():
    return {
        "adhesive_curing": {
            "name": "adhesive_curing",
            "display_name": "点胶固化",
            "type": "process",
            "tools": ["query_records", "run_spc"],
            "system_prompt": "## 工艺参数\n\n测试正文",
        },
        "spc-monitoring": {
            "name": "spc-monitoring",
            "type": "capability",
            "tools": ["run_spc"],
            "system_prompt": "## SPC 监控",
        },
    }


class TestCreateProcessAgent:
    def test_raises_for_unknown_process_type(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with pytest.raises(ValueError, match="Unknown process type"):
                import asyncio
                asyncio.run(create_process_agent(
                    mock_llm, "nonexistent", mock_tool_pool,
                ))

    def test_merges_process_and_capability_tools(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with patch("process_opt.agent.deep_agent.get_capability_skills") as mock_get_cap:
                with patch("process_opt.agent.deep_agent.create_deep_agent") as mock_create:
                    mock_get_cap.return_value = [
                        s for s in mock_registry.values() if s.get("type") == "capability"
                    ]

                    import asyncio
                    asyncio.run(create_process_agent(
                        mock_llm, "adhesive_curing", mock_tool_pool,
                    ))

                    call_kwargs = mock_create.call_args.kwargs
                    # Should include tools from both process + capability
                    tool_names = {t.__name__ for t in call_kwargs["tools"]}
                    assert "query_records" in tool_names
                    assert "run_spc" in tool_names

    def test_system_prompt_from_skill_body(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with patch("process_opt.agent.deep_agent.get_capability_skills") as mock_get_cap:
                with patch("process_opt.agent.deep_agent.create_deep_agent") as mock_create:
                    mock_get_cap.return_value = []

                    import asyncio
                    asyncio.run(create_process_agent(
                        mock_llm, "adhesive_curing", mock_tool_pool,
                    ))

                    call_kwargs = mock_create.call_args.kwargs
                    assert call_kwargs["system_prompt"] == "## 工艺参数\n\n测试正文"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/test_deep_agent.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `deep_agent.py`**

Write `src/process_opt/agent/deep_agent.py`:

```python
"""DeepAgent factory — one-line agent creation replacing StateGraph + Supervisor + 3 Workers."""

from __future__ import annotations

import logging
from typing import Any

from deepagents import create_deep_agent
from deepagents.middleware import (
    TodoListMiddleware,
    SubAgentMiddleware,
    FilesystemMiddleware,
    SummarizationMiddleware,
)

from process_opt.agent.skills import (
    discover_skills,
    get_capability_skills,
)

logger = logging.getLogger(__name__)

# Global: scanned once at import time — all .md files under skills/
SKILL_REGISTRY: dict[str, dict] = discover_skills()


async def create_process_agent(
    llm: Any,
    process_type: str,
    tool_pool: dict[str, Any],
) -> Any:
    """Create a DeepAgent configured for a specific process type.

    Args:
        llm: Chat model instance (e.g., ChatOpenAI).
        process_type: Key into SKILL_REGISTRY (e.g., ``"adhesive_curing"``).
        tool_pool: Dict mapping tool name → callable (from main.py wiring).

    Returns:
        A DeepAgent ready for ``astream_events()`` or ``ainvoke()``.

    Raises:
        ValueError: If ``process_type`` is not in the skill registry.
    """
    # 1. Get process skill — its Markdown body IS the system prompt
    process_skill = SKILL_REGISTRY.get(process_type)
    if not process_skill:
        available = [s["name"] for s in SKILL_REGISTRY.values() if s.get("type") == "process"]
        raise ValueError(
            f"Unknown process type: {process_type}. "
            f"Available: {', '.join(available)}"
        )

    # 2. Get all capability skills (on-demand, triggered by LLM intent matching)
    capability_skills = get_capability_skills(SKILL_REGISTRY)

    # 3. Merge tool names from process skill + all capability skills
    all_tool_names: set[str] = set(process_skill.get("tools", []))
    for cap in capability_skills:
        all_tool_names.update(cap.get("tools", []))

    tools = [tool_pool[name] for name in all_tool_names if name in tool_pool]
    missing = all_tool_names - set(tool_pool.keys())
    if missing:
        logger.warning("Skill tools not in pool: %s", missing)

    # 4. Assemble DeepAgent with middleware stack
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=process_skill["system_prompt"],  # Markdown body
        middleware=[
            TodoListMiddleware(),
            SkillsMiddleware(
                skills=capability_skills,
            ),
            SubAgentMiddleware(default_model=llm),
            FilesystemMiddleware(backend="state"),
            SummarizationMiddleware(trigger_tokens=0.85),
        ],
    )
    return agent
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/test_deep_agent.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/agent/deep_agent.py tests/test_deep_agent.py
git commit -m "feat: add deep agent factory — create_process_agent() with middleware stack"
```

---

### Task 6: Rewrite agent_routes.py

**Files:**
- Modify: `src/process_opt/api/agent_routes.py` — full rewrite

**Interfaces:**
- Consumes: `agent_factory(llm, process_type) -> DeepAgent` from Task 7
- Produces: `register_agent_routes(app, agent_factory, llm)` — same signature as old but `session_manager`+`knowledge_loader`+`agent_graph` replaced by `agent_factory`

- [ ] **Step 1: Write the rewritten agent_routes.py**

Write `src/process_opt/api/agent_routes.py`:

```python
"""Agent API routes — DeepAgents backend.

Replaces the old LangGraph StateGraph SSE layer. The public API surface
(POST /session, POST /chat, GET /chat/{id}/events, GET /session/{id}/messages,
GET /processes, POST /upload) is unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from langchain_core.messages import AIMessageChunk
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# In-memory session store (replaces SessionManager + AgentSession)
_sessions: dict[str, dict[str, Any]] = {}


def register_agent_routes(
    app: Any,
    agent_factory: Any,        # async callable(llm, process_type) -> DeepAgent
    llm: Any = None,
) -> None:
    """Register agent routes on the FastAPI app.

    Args:
        app: FastAPI application instance.
        agent_factory: Async callable that returns a DeepAgent for a process type.
        llm: Chat model (used for suggestions, etc.).
    """
    router = APIRouter(prefix="/api/v1/agent")

    # --- Background session expiry ---
    _expiry_started = False

    async def _ensure_expiry():
        nonlocal _expiry_started
        if _expiry_started:
            return
        _expiry_started = True
        asyncio.create_task(_expire_stale(ttl=1800))

    async def _expire_stale(ttl: int = 1800):
        while True:
            await asyncio.sleep(300)
            now = time.monotonic()
            expired = [
                sid for sid, s in _sessions.items()
                if now - s.get("created", now) > ttl
            ]
            for sid in expired:
                del _sessions[sid]
                logger.debug("Expired session %s", sid)

    # --- Routes ---

    @router.post("/session")
    async def create_session(request: Request) -> dict:
        await _ensure_expiry()
        user = request.headers.get("X-User", "anonymous")
        body = await request.json()
        process_type = body.get("process_type", "adhesive_curing")

        agent = await agent_factory(llm, process_type)
        sid = f"ses_{uuid.uuid4().hex[:20]}"
        thread_id = f"thread_{uuid.uuid4().hex[:20]}"
        _sessions[sid] = {
            "agent": agent,
            "thread_id": thread_id,
            "user": user,
            "process_type": process_type,
            "messages": [],
            "created": time.monotonic(),
        }
        return {"session_id": sid, "process_type": process_type}

    @router.get("/session")
    async def list_sessions(request: Request) -> list[dict]:
        user = request.headers.get("X-User", "anonymous")
        return [
            {
                "session_id": sid,
                "process_type": s["process_type"],
                "message_count": len(s.get("messages", [])),
            }
            for sid, s in _sessions.items()
            if s.get("user") == user
        ]

    @router.post("/chat")
    async def send_message(request: Request) -> Response:
        body = await request.json()
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        if not session_id or not text:
            raise HTTPException(status_code=400, detail="session_id and text required")

        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")

        session["messages"].append({"role": "user", "content": text})
        session["pending"] = True
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/chat/{session_id}/events")
    async def stream_events(session_id: str) -> StreamingResponse:
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.pop("pending", False):
            # No pending message — return immediately
            async def empty():
                yield b'data: {"type":"session.status","status":"idle"}\n\n'
            return StreamingResponse(empty(), media_type="text/event-stream")

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in session["messages"]
        ]

        async def generate():
            try:
                async for event in session["agent"].astream_events(
                    {"messages": messages},
                    config={"configurable": {"thread_id": session["thread_id"]}},
                    version="v2",
                ):
                    sse = _map_event(event)
                    if sse:
                        yield sse

                # Emit suggestions
                if llm is not None and session.get("messages"):
                    suggestions = await _generate_suggestions(
                        llm,
                        [{"role": m["role"], "content": m["content"]}
                         for m in session["messages"]],
                    )
                    yield f'data: {{"type":"suggestions","questions":{json.dumps(suggestions)}}}\n\n'.encode()

                yield b'data: {"type":"session.status","status":"idle"}\n\n'
            except GeneratorExit:
                logger.debug("SSE client disconnected for session %s", session_id)
            except Exception as exc:
                logger.error("SSE stream error for session %s: %s", session_id, exc)
                err = json.dumps({"type": "error", "message": str(exc)})
                yield f"data: {err}\n\n".encode()
                yield b'data: {"type":"session.status","status":"idle"}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/session/{session_id}/messages")
    async def get_messages(session_id: str) -> list[dict]:
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.get("messages", [])

    @router.get("/processes")
    async def list_processes() -> list[dict]:
        from process_opt.agent.skills import discover_skills, get_process_skills
        registry = discover_skills()
        return [
            {"process_type": s["name"], "display_name": s.get("display_name", s["name"])}
            for s in get_process_skills(registry)
        ]

    @router.post("/upload")
    async def upload_dataset_route(file: UploadFile) -> dict:
        from process_opt.analysis.excel import parse_excel, save_dataset

        if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls / .csv 文件")

        content = await file.read()
        ds = parse_excel(content)
        ds_id = save_dataset(ds)
        feature_fields = sorted({k for f in ds.features for k in f})
        target_fields = sorted({k for t in ds.targets for k in t})
        return {
            "dataset_id": ds_id,
            "fields": {"features": feature_fields, "targets": target_fields},
            "sample_count": ds.sample_count,
        }

    app.include_router(router)


def _map_event(event: dict) -> bytes | None:
    """Map DeepAgents astream_events event to SSE bytes.

    Keeps the same SSE event type names as the old LangGraph layer
    so the frontend needs zero changes.
    """
    kind = event.get("event", "")

    # AI text streaming
    if kind == "on_chat_model_stream":
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            data = json.dumps({"type": "message.delta", "text": str(text)})
            return f"data: {data}\n\n".encode()

    # Tool start
    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})
        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()

    # Tool end
    if kind == "on_tool_end":
        output = event.get("data", {}).get("output", "")
        if hasattr(output, "content"):
            output_str = str(output.content)
        else:
            output_str = str(output)
        data = json.dumps({"type": "tool.result", "name": event.get("name", ""),
                           "data": output_str})
        return f"data: {data}\n\n".encode()

    # Subagent start (maps to old node.start)
    if kind == "on_chain_start":
        name = event.get("name", "")
        data = json.dumps({"type": "node.start", "node": name})
        return f"data: {data}\n\n".encode()

    # Subagent end (maps to old node.end)
    if kind == "on_chain_end":
        name = event.get("name", "")
        data = json.dumps({"type": "node.end", "node": name})
        return f"data: {data}\n\n".encode()

    return None


async def _generate_suggestions(llm: Any, messages: list[dict]) -> list[str]:
    """Generate follow-up question suggestions from conversation context."""
    from langchain_core.messages import SystemMessage

    context = ""
    for msg in messages[-6:]:  # last 6 messages only
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        context += f"[{msg.get('role', 'unknown')}]: {str(content)[:300]}\n"

    prompt = (
        "基于以下对话，生成3个用户可能继续提问的简短问题。\n"
        "问题要具体、与工艺分析相关，用中文。\n"
        "只输出问题列表，每行一个，不要序号和标记。\n\n"
        f"{context}"
    )
    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        lines = [
            l.strip("- 1234567890. ")
            for l in (response.content or "").strip().split("\n")
            if l.strip()
        ]
        return [l for l in lines if len(l) > 3][:3]
    except Exception:
        return []
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/api/agent_routes.py
git commit -m "feat: rewrite agent routes for DeepAgents astream_events"
```

---

### Task 7: Wire main.py and app.py

**Files:**
- Modify: `src/process_opt/api/main.py` — tool pool dict + agent factory
- Modify: `src/process_opt/api/app.py` — change create_app params + route registration

**Interfaces:**
- Consumes: `create_process_agent()` from Task 5, rewritten `register_agent_routes()` from Task 6
- Produces: Running FastAPI app with DeepAgents backend

- [ ] **Step 1: Modify main.py**

In `src/process_opt/api/main.py`, change the imports and agent assembly:

Remove these imports:
```python
from process_opt.agent.graph import SessionManager, build_graph
from process_opt.knowledge.loader import KnowledgeLoader
```

Add these imports:
```python
from process_opt.agent.deep_agent import create_process_agent
```

Replace the tool assembly + graph build block (lines 291-308) — keep all proxy setup:

```python
    # Build tool pool as flat dict keyed by tool name
    tool_pool: dict[str, object] = {}
    all_tools = (
        create_analysis_tools(
            repository_proxy, analysis_service_proxy, parameter_service_proxy,
            knowledge_loader, experiment_repo_proxy,
        ) +
        create_system_tools(line_device_repo_proxy, analysis_service_proxy) +
        create_parameter_tools(parameter_service_proxy) +
        create_experiment_tools(experiment_repo_proxy)
    )
    for t in all_tools:
        tool_pool[t.name] = t

    llm = ChatOpenAI(
        model=settings.agent_model,
        base_url=settings.agent_api_base,
        api_key=settings.agent_api_key,
        temperature=settings.agent_temperature,
        streaming=True,
    )

    async def agent_factory(llm_instance, process_type: str):
        return await create_process_agent(llm_instance, process_type, tool_pool)

    app = create_app(
        repository=repository_proxy,
        parameter_service=parameter_service_proxy,
        analysis_service=analysis_service_proxy,
        line_device_repo=line_device_repo_proxy,
        container_pool=container_pool_proxy,
        agent_factory=agent_factory,
        suggestion_llm=llm,
        experiment_repo=experiment_repo_proxy,
    )
```

- [ ] **Step 2: Modify app.py create_app signature and route registration**

In `src/process_opt/api/app.py`, change the `create_app` function:

Replace the signature (lines 123-134):
```python
def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
    container_pool: "ContainerPoolProxy | None" = None,
    agent_factory: Any = None,
    suggestion_llm: Any = None,
    experiment_repo: Any = None,
) -> FastAPI:
```

Replace the agent route registration (lines 626-628):
```python
    if agent_factory is not None:
        from process_opt.api.agent_routes import register_agent_routes
        register_agent_routes(app, agent_factory, llm=suggestion_llm)
```

- [ ] **Step 3: Verify app starts (import-only check)**

```bash
cd /Users/zhongding/dev/thingsboard && uv run python -c "
from process_opt.api.main import create_api_app_from_settings
print('App factory imports OK')
"
```

Expected: imports succeed (may fail on DB connection — that's OK for import check).

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/api/main.py src/process_opt/api/app.py
git commit -m "feat: wire main.py and app.py for DeepAgents — tool pool dict + agent factory"
```

---

### Task 8: Cleanup — Delete Old Files

**Files:**
- Delete: `src/process_opt/agent/graph.py`
- Delete: `src/process_opt/agent/state.py`
- Delete: `src/process_opt/agent/nodes/supervisor.py`
- Delete: `src/process_opt/agent/nodes/worker.py`

- [ ] **Step 1: Delete old agent kernel files**

```bash
rm src/process_opt/agent/graph.py
rm src/process_opt/agent/state.py
rm src/process_opt/agent/nodes/supervisor.py
rm src/process_opt/agent/nodes/worker.py
```

- [ ] **Step 2: Verify all imports still work**

```bash
cd /Users/zhongding/dev/thingsboard && uv run python -c "
from process_opt.api.main import create_api_app_from_settings
from process_opt.agent.skills import discover_skills
from process_opt.agent.deep_agent import create_process_agent
print('All imports OK after cleanup')
"
```

Expected: "All imports OK after cleanup"

- [ ] **Step 3: Run all tests**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/test_skills.py tests/test_deep_agent.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git rm src/process_opt/agent/graph.py src/process_opt/agent/state.py src/process_opt/agent/nodes/supervisor.py src/process_opt/agent/nodes/worker.py
git commit -m "refactor: remove old LangGraph agent kernel (graph, state, supervisor, worker)"
```

---

### Task 9: Integration Test

**Files:**
- No new files

**Interfaces:**
- Consumes: All previous tasks

- [ ] **Step 1: Start services**

```bash
cd /Users/zhongding/dev/thingsboard && docker compose up -d postgres nats
docker compose up -d backend-api --build
```

- [ ] **Step 2: Create session and send a message**

```bash
# Wait for backend to be ready
sleep 5

# Create session
curl -s -X POST http://localhost:8000/api/v1/agent/session \
  -H 'Content-Type: application/json' \
  -d '{"process_type": "adhesive_curing"}' | python3 -m json.tool

# Send help message
curl -s -X POST http://localhost:8000/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "ses_REPLACE_ME", "text": "?"}'
```

Expected: Session created with 200, chat returns 204.

- [ ] **Step 3: Verify SSE events format**

```bash
curl -s -N http://localhost:8000/api/v1/agent/chat/ses_REPLACE_ME/events 2>&1 | head -20
```

Expected: SSE events with `message.delta`, `tool.call`, `tool.result` types — same format as before.

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/zhongding/dev/thingsboard && uv run pytest tests/ -v --timeout=60
```

Expected: All tests PASS. No import errors from deleted modules.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git diff --cached --stat
git commit -m "test: integration test fixes for DeepAgents migration"
```
