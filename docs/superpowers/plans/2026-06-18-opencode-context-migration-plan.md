# OpenCode → Claude Code Context Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract recent 20 OpenCode sessions for the thingsboard project from SQLite into a structured Markdown document that Claude Code can `@`-reference.

**Architecture:** Single Python script (`scripts/migrate_opencode_context.py`) reads OpenCode's SQLite database, extracts sessions/messages/parts/todos, classifies them into workflows, and renders a 6-section Markdown document. Zero external dependencies — only Python stdlib.

**Tech Stack:** Python 3.11+, sqlite3, json, datetime, pathlib, argparse

## Global Constraints

- 仅使用 Python 标准库（`sqlite3`, `json`, `datetime`, `pathlib`, `argparse`）
- 不对 OpenCode 数据库做任何写入（只读连接）
- 输出 Markdown 文档到 `docs/superpowers/specs/2026-06-18-opencode-context-migration.md`
- 脚本位置: `scripts/migrate_opencode_context.py`
- 所有输出使用中文

---

### Task 1: Database connection + session extraction

**Files:**
- Create: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Produces: `extract_sessions(db_path: str, project_id: str, limit: int) -> list[dict]`
- Produces: `extract_messages(db_path: str, session_id: str) -> list[dict]`

- [ ] **Step 1: Create script skeleton with DB connection**

```python
#!/usr/bin/env python3
"""Extract OpenCode session context for Claude Code migration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_db(db_path: str) -> sqlite3.Connection:
    """Open OpenCode SQLite database in read-only mode."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def extract_sessions(
    db_path: str,
    project_id: str,
    limit: int = 20,
) -> list[dict]:
    """Extract recent sessions for a project.

    Returns list of dicts with keys: id, title, time_created, time_updated,
    cost, tokens_input, tokens_output, model
    """
    db = get_db(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT id, title, time_created, time_updated, cost,
                  tokens_input, tokens_output, model
           FROM session
           WHERE project_id = ?
           ORDER BY time_created DESC
           LIMIT ?""",
        (project_id, limit),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def extract_messages(db_path: str, session_id: str) -> list[dict]:
    """Extract all messages for a session, parsed from JSON.

    Returns list of dicts with keys: id, time_created, role, diffs, tokens,
    model_id, provider_id, finish
    """
    db = get_db(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT m.id, m.time_created, m.data
           FROM message m
           WHERE m.session_id = ?
           ORDER BY m.time_created""",
        (session_id,),
    ).fetchall()
    db.close()

    messages = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except json.JSONDecodeError:
            continue
        role = data.get("role", "unknown")
        summary = data.get("summary", {}) or {}
        diffs = summary.get("diffs", []) if isinstance(summary, dict) else []
        tokens = data.get("tokens", {}) or {}
        messages.append({
            "id": row["id"],
            "time_created": row["time_created"],
            "role": role,
            "diffs": diffs,
            "tokens": tokens,
            "model_id": data.get("modelID", ""),
            "provider_id": data.get("providerID", ""),
            "finish": data.get("finish", ""),
        })
    return messages
```

- [ ] **Step 2: Verify extraction functions work**

Run:
```bash
python3 -c "
from scripts.migrate_opencode_context import extract_sessions, extract_messages
import json
sessions = extract_sessions(
    '$HOME/.local/share/opencode/opencode.db',
    'b52e71c68c3d6152862f3ff4892683dce00d6eb1',
    3,
)
print(f'Sessions extracted: {len(sessions)}')
for s in sessions:
    print(f'  - {s[\"id\"][:20]}... | {s[\"title\"][:60]}')
    msgs = extract_messages('$HOME/.local/share/opencode/opencode.db', s['id'])
    print(f'    messages: {len(msgs)}')
"
```
Expected: Prints 3 sessions with message counts.

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_opencode_context.py
git commit -m "feat: add session + message extraction from OpenCode DB"
```

---

### Task 2: Todo + part extraction

**Files:**
- Modify: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Consumes: `get_db` from Task 1
- Produces: `extract_todos(db_path: str, session_ids: list[str]) -> list[dict]`
- Produces: `extract_text_parts(db_path: str, session_id: str) -> list[str]`

- [ ] **Step 1: Add extract_todos function**

```python
def extract_todos(db_path: str, session_ids: list[str]) -> list[dict]:
    """Extract pending todos for given sessions.

    Returns list of dicts with keys: session_id, content, status, priority
    """
    if not session_ids:
        return []
    db = get_db(db_path)
    db.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in session_ids)
    rows = db.execute(
        f"""SELECT session_id, content, status, priority
            FROM todo
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, position""",
        session_ids,
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 2: Add extract_text_parts function**

```python
def extract_text_parts(db_path: str, session_id: str) -> list[str]:
    """Extract text content from part table for a session.

    Returns list of text strings from parts with type='text'.
    """
    db = get_db(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT p.data
           FROM part p
           WHERE p.session_id = ?
           ORDER BY p.time_created""",
        (session_id,),
    ).fetchall()
    db.close()

    texts = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except json.JSONDecodeError:
            continue
        if data.get("type") == "text" and data.get("text"):
            texts.append(data["text"])
    return texts
```

- [ ] **Step 3: Verify extraction in a quick smoke test**

Run:
```bash
python3 -c "
from scripts.migrate_opencode_context import (
    extract_sessions, extract_messages, extract_todos, extract_text_parts,
)
db = '$HOME/.local/share/opencode/opencode.db'
pid = 'b52e71c68c3d6152862f3ff4892683dce00d6eb1'
sessions = extract_sessions(db, pid, 5)
sids = [s['id'] for s in sessions]
todos = extract_todos(db, sids)
print(f'Todos found: {len(todos)}')
for s in sessions:
    texts = extract_text_parts(db, s['id'])
    print(f'  Session {s[\"title\"][:50]}: {len(texts)} text parts')
"
```
Expected: Shows todo count and text parts per session.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_opencode_context.py
git commit -m "feat: add todo + part extraction from OpenCode DB"
```

---

### Task 3: Workflow classification + file aggregation

**Files:**
- Modify: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Consumes: `extract_sessions`, `extract_messages` from Tasks 1-2
- Produces: `classify_workflows(sessions: list[dict], messages_map: dict[str, list[dict]]) -> list[dict]`
- Produces: `aggregate_files(all_messages: list[dict]) -> dict[str, set[str]]`

- [ ] **Step 1: Add classify_workflows function**

```python
def _guess_workflow(title: str) -> str:
    """Guess workflow name from session title.

    Looks for Phase patterns and known workflow keywords.
    """
    title_lower = title.lower()

    if "phase1" in title_lower or "phase 1" in title_lower:
        return "Agent 优化 Phase 1: 基础重构"
    if "phase2" in title_lower or "phase 2" in title_lower:
        return "Agent 优化 Phase 2: 质量修复"
    if "phase3" in title_lower or "phase 3" in title_lower:
        return "Agent 优化 Phase 3: 功能增强"

    # AgentChat component refactor
    if any(kw in title_lower for kw in (
        "agentchat", "chatbubble", "chatinput", "chatview",
        "chatcontent", "chattoolcall", "chatloading", "chatsuggestions",
        "agentheader", "sessionlist", "sidebar", "floatingbutton",
        "composable",
    )):
        return "AgentChat 组件化重构"

    # General explore / audit
    if any(kw in title_lower for kw in ("explore", "audit", "find ", "map ")):
        return "项目探索与审查"

    # Code review
    if "review" in title_lower or "code quality" in title_lower:
        return "代码审查"

    return "其他"


def classify_workflows(
    sessions: list[dict],
    messages_map: dict[str, list[dict]],
) -> list[dict]:
    """Group sessions into workflows with summary info.

    Returns list of workflow dicts:
      {name, sessions: [{session_dict, messages: [...]}]}
    """
    workflows: dict[str, list[dict]] = {}
    for s in sessions:
        wf = _guess_workflow(s["title"])
        workflows.setdefault(wf, []).append({**s, "messages": messages_map.get(s["id"], [])})

    result = []
    for name, sess_list in workflows.items():
        total_tokens_input = sum(
            s.get("tokens_input", 0) or 0 for s in sess_list
        )
        total_tokens_output = sum(
            s.get("tokens_output", 0) or 0 for s in sess_list
        )
        total_cost = sum(s.get("cost", 0) or 0 for s in sess_list)
        result.append({
            "name": name,
            "sessions": sess_list,
            "session_count": len(sess_list),
            "total_tokens_input": total_tokens_input,
            "total_tokens_output": total_tokens_output,
            "total_cost": total_cost,
            "status": _workflow_status(sess_list),
        })

    # Sort by first session time (most recent workflow first)
    result.sort(key=lambda w: max(
        s["time_created"] for s in w["sessions"]
    ), reverse=True)
    return result


def _workflow_status(sessions: list[dict]) -> str:
    """Infer workflow status from session titles."""
    titles = " ".join(s["title"] for s in sessions).lower()
    if any(w in titles for w in ("fix", "review", "re-review", "re-refactor")):
        return "🔄 修复/审查中"
    return "✅ 已完成"
```

- [ ] **Step 2: Add aggregate_files function**

```python
def aggregate_files(all_messages: list[dict]) -> dict[str, set[str]]:
    """Aggregate all files touched across all messages.

    Returns dict: {directory_path: set_of_filenames}
    Groups by top-level directory (src/, web/, db/, Dockerfile, etc.)
    """
    by_dir: dict[str, set[str]] = {}
    for msg in all_messages:
        for diff in msg.get("diffs", []):
            filepath = diff.get("file", "")
            if not filepath:
                continue
            parts = filepath.split("/")
            if len(parts) == 1:
                top = "."
            else:
                top = parts[0]
            by_dir.setdefault(top, set()).add(filepath)
    return by_dir
```

- [ ] **Step 3: Verify classification logic**

Run:
```bash
python3 -c "
from scripts.migrate_opencode_context import (
    extract_sessions, extract_messages, classify_workflows,
)
db = '$HOME/.local/share/opencode/opencode.db'
pid = 'b52e71c68c3d6152862f3ff4892683dce00d6eb1'
sessions = extract_sessions(db, pid, 20)
msgs_map = {s['id']: extract_messages(db, s['id']) for s in sessions}
workflows = classify_workflows(sessions, msgs_map)
for wf in workflows:
    print(f'## {wf[\"name\"]} ({wf[\"session_count\"]} sessions) {wf[\"status\"]}')
    for s in wf['sessions']:
        print(f'  - {s[\"title\"][:70]}')
"
```
Expected: Grouped workflows with sessions, matching the known Phase structure.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_opencode_context.py
git commit -m "feat: add workflow classification + file aggregation"
```

---

### Task 4: Markdown section builders (part 1)

**Files:**
- Modify: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Consumes: `classify_workflows`, `aggregate_files` output shapes from Task 3
- Produces: `build_section_overview(workflows: list[dict]) -> str`
- Produces: `build_section_details(workflows: list[dict]) -> str`

- [ ] **Step 1: Add build_section_overview**

```python
def _ts_to_str(ts: int) -> str:
    """Convert Unix millisecond timestamp to ISO date string."""
    try:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError, OverflowError):
        return str(ts)


def build_section_overview(workflows: list[dict]) -> str:
    """Build Section 1: Work overview with task tree and completion status."""
    lines = ["## 1. 工作总览\n"]
    lines.append(f"共 {sum(w['session_count'] for w in workflows)} 个会话，"
                 f"{len(workflows)} 个工作流。\n")

    total_cost = sum(w["total_cost"] for w in workflows)
    total_in = sum(w["total_tokens_input"] for w in workflows)
    total_out = sum(w["total_tokens_output"] for w in workflows)
    lines.append(f"**总消耗**: ${total_cost:.4f} | "
                 f"输入 {total_in:,} tokens | 输出 {total_out:,} tokens\n")

    for wf in workflows:
        lines.append(f"\n### {wf['name']} {wf['status']}")
        lines.append(f"\n{wf['session_count']} 个会话 | "
                     f"${wf['total_cost']:.4f} | "
                     f"in {wf['total_tokens_input']:,} / out {wf['total_tokens_output']:,}")
        lines.append("")
        for s in wf["sessions"]:
            ts = _ts_to_str(s["time_created"])
            title = s["title"]
            lines.append(f"- [{ts}] {title}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Add build_section_details**

```python
def _summarize_session(session: dict, text_parts_map: dict[str, list[str]]) -> str:
    """Generate a single session's detail block."""
    lines = []
    title = session["title"]
    ts = _ts_to_str(session["time_created"])

    lines.append(f"\n#### {ts} — {title}\n")

    # Extract intent from user messages
    messages = session.get("messages", [])
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]

    # Intent: first user message's text parts (first 200 chars)
    texts = text_parts_map.get(session["id"], [])
    if texts:
        first_text = texts[0][:300].replace("\n", " ")
        lines.append(f"- **意图**: {first_text}...")
    elif user_msgs:
        lines.append(f"- **意图**: {user_msgs[0].get('summary', '')[:200]}")
    else:
        lines.append(f"- **意图**: [无文本记录]")

    # What was done: diffs summary
    all_files: set[str] = set()
    for m in messages:
        for d in m.get("diffs", []):
            all_files.add(d.get("file", ""))
    if all_files:
        files_sorted = sorted(all_files)[:15]
        lines.append(f"- **涉及文件** ({len(all_files)}):")
        for f in files_sorted:
            lines.append(f"  - `{f}`")
        if len(all_files) > 15:
            lines.append(f"  - ... 及其他 {len(all_files) - 15} 个文件")

    # Finish reason for assistant messages
    if assistant_msgs:
        finishes = [m["finish"] for m in assistant_msgs if m.get("finish")]
        if finishes:
            lines.append(f"- **完成方式**: {', '.join(finishes[:3])}")

    # Token usage
    tokens = session.get("tokens_input", 0) or 0
    if tokens:
        lines.append(f"- **Token 消耗**: in {session['tokens_input']:,} / "
                     f"out {session.get('tokens_output', 0) or 0:,}")

    return "\n".join(lines) + "\n"


def build_section_details(
    workflows: list[dict],
    text_parts_map: dict[str, list[str]],
) -> str:
    """Build Section 2: Per-session details."""
    lines = ["## 2. 各会话详情\n"]

    for wf in workflows:
        lines.append(f"\n### {wf['name']}\n")
        for s in wf["sessions"]:
            lines.append(_summarize_session(s, text_parts_map))

    return "\n".join(lines) + "\n"
```

- [ ] **Step 3: Verify section output**

Run:
```bash
python3 -c "
from scripts.migrate_opencode_context import *
db = '$HOME/.local/share/opencode/opencode.db'
pid = 'b52e71c68c3d6152862f3ff4892683dce00d6eb1'
sessions = extract_sessions(db, pid, 5)
msgs_map = {s['id']: extract_messages(db, s['id']) for s in sessions}
text_map = {s['id']: extract_text_parts(db, s['id']) for s in sessions}
workflows = classify_workflows(sessions, msgs_map)
print(build_section_overview(workflows))
"
```
Expected: Structured overview in Markdown format.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_opencode_context.py
git commit -m "feat: add Markdown builders for overview + session details"
```

---

### Task 5: Markdown section builders (part 2) + render

**Files:**
- Modify: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Consumes: `aggregate_files` from Task 3
- Consumes: `extract_todos` from Task 2
- Produces: `build_section_files(file_map: dict[str, set[str]]) -> str`
- Produces: `build_section_todos(todos: list[dict]) -> str`
- Produces: `build_section_next_steps(workflows: list[dict], todos: list[dict]) -> str`
- Produces: `render_markdown(...) -> str`

- [ ] **Step 1: Add sections 3, 4, 5, 6 builders**

```python
def build_section_files(file_map: dict[str, set[str]]) -> str:
    """Build Section 3: All files touched, grouped by directory."""
    lines = ["## 3. 涉及文件总览\n"]
    for dir_name in sorted(file_map):
        files = sorted(file_map[dir_name])
        lines.append(f"\n### `{dir_name}/`\n")
        for f in files:
            lines.append(f"- `{f}`")
    return "\n".join(lines) + "\n"


def build_section_todos(todos: list[dict]) -> str:
    """Build Section 5: Unfinished todo items."""
    lines = ["## 5. 未完成事项\n"]
    pending = [t for t in todos if t.get("status") != "completed"]
    if not pending:
        lines.append("\n无未完成事项。\n")
        return "\n".join(lines)

    lines.append(f"\n| 事项 | 状态 | 优先级 |")
    lines.append(f"|------|------|--------|")
    for t in pending:
        content = t.get("content", "")[:80]
        status = t.get("status", "unknown")
        priority = t.get("priority", "-")
        lines.append(f"| {content} | {status} | {priority} |")
    return "\n".join(lines) + "\n"


def build_section_next_steps(
    workflows: list[dict],
    todos: list[dict],
) -> str:
    """Build Section 6: Suggested next steps based on context."""
    lines = ["## 6. 建议的下一步\n"]

    pending = [t for t in todos if t.get("status") != "completed"]
    if pending:
        lines.append(f"### 未完成事项 ({len(pending)} 项)\n")
        for t in pending[:5]:
            lines.append(f"- {t['content'][:120]}")
        lines.append("")

    # Suggest based on most recent workflow
    if workflows:
        latest = workflows[0]
        lines.append(f"### 最近工作流: {latest['name']}\n")
        latest_session = latest["sessions"][0] if latest["sessions"] else None
        if latest_session:
            lines.append(f"最近会话: **{latest_session['title']}** "
                         f"({_ts_to_str(latest_session['time_created'])})\n")

    lines.append("\n建议: 打开输出文档，使用 `@docs/superpowers/specs/"
                 "2026-06-18-opencode-context-migration.md` "
                 "在 Claude Code 中引用此上下文继续工作。")
    return "\n".join(lines) + "\n"


def render_markdown(
    workflows: list[dict],
    file_map: dict[str, set[str]],
    todos: list[dict],
    text_parts_map: dict[str, list[str]],
) -> str:
    """Render the complete Markdown document."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = (
        "# OpenCode → Claude Code 工作上下文迁移\n\n"
        f"> 提取自 OpenCode CLI v1.15.13 | 项目: thingsboard\n"
        f"> 会话范围: 最近 {sum(w['session_count'] for w in workflows)} 个"
        f" | 提取时间: {now}\n\n"
        "---\n\n"
    )

    parts = [
        header,
        build_section_overview(workflows),
        build_section_details(workflows, text_parts_map),
        build_section_files(file_map),
        _build_section_decisions(workflows),
        build_section_todos(todos),
        build_section_next_steps(workflows, todos),
    ]
    return "\n".join(parts)


def _build_section_decisions(workflows: list[dict]) -> str:
    """Build Section 4: Key design decisions extracted from session titles.

    This is a heuristic extraction — it surface notable work from session
    titles that indicate design decisions (refactors, architecture changes,
    etc.)
    """
    lines = ["## 4. 关键设计决策\n"]

    decision_keywords = [
        "refactor", "rewrite", "replace", "migrate", "extract",
        "convert", "integrate",
    ]

    found = []
    for wf in workflows:
        for s in wf["sessions"]:
            title_lower = s["title"].lower()
            if any(kw in title_lower for kw in decision_keywords):
                found.append(f"- **{s['title']}** ({_ts_to_str(s['time_created'])})")

    if found:
        lines.extend(found)
        lines.append("")
    else:
        lines.append("\n（从会话标题中未检测到明确的设计决策关键词）\n")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Verify full render pipeline**

Run:
```bash
python3 -c "
from scripts.migrate_opencode_context import *
db = '$HOME/.local/share/opencode/opencode.db'
pid = 'b52e71c68c3d6152862f3ff4892683dce00d6eb1'
sessions = extract_sessions(db, pid, 10)
msgs_map = {s['id']: extract_messages(db, s['id']) for s in sessions}
text_map = {s['id']: extract_text_parts(db, s['id']) for s in sessions}
workflows = classify_workflows(sessions, msgs_map)
all_msgs = [m for ms in msgs_map.values() for m in ms]
file_map = aggregate_files(all_msgs)
todos = extract_todos(db, [s['id'] for s in sessions])
md = render_markdown(workflows, file_map, todos, text_map)
print(md[:2000])
print('...')
print(f'Total length: {len(md)} chars')
"
```
Expected: Complete Markdown with all 6 sections, >2000 chars.

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_opencode_context.py
git commit -m "feat: add remaining Markdown sections + render pipeline"
```

---

### Task 6: CLI main + error handling + output

**Files:**
- Modify: `scripts/migrate_opencode_context.py`

**Interfaces:**
- Produces: `main()` — argparse CLI entry point
- Produces: `write_output(path: str, content: str) -> None`

- [ ] **Step 1: Add write_output and main**

```python
def write_output(path: str, content: str) -> None:
    """Write content to output file, creating directories if needed."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract OpenCode session context for Claude Code migration",
    )
    parser.add_argument(
        "--db",
        default=str(Path.home() / ".local/share/opencode/opencode.db"),
        help="Path to OpenCode SQLite database",
    )
    parser.add_argument(
        "--project-id",
        default="b52e71c68c3d6152862f3ff4892683dce00d6eb1",
        help="OpenCode project ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of recent sessions to extract",
    )
    parser.add_argument(
        "--output",
        default="docs/superpowers/specs/2026-06-18-opencode-context-migration.md",
        help="Output Markdown file path",
    )
    args = parser.parse_args()

    # Validate DB exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {args.db}", flush=True)
        raise SystemExit(1)

    print(f"提取 OpenCode 会话上下文...", flush=True)
    print(f"  数据库: {args.db}", flush=True)
    print(f"  项目ID: {args.project_id}", flush=True)
    print(f"  会话数: {args.limit}", flush=True)
    print(f"  输出: {args.output}", flush=True)
    print("", flush=True)

    # Extract
    sessions = extract_sessions(str(db_path), args.project_id, args.limit)
    if not sessions:
        print("警告: 未找到匹配的会话，将输出空报告", flush=True)

    session_ids = [s["id"] for s in sessions]
    print(f"提取消息和内容 ...", flush=True)
    msgs_map = {}
    text_map = {}
    for s in sessions:
        msgs_map[s["id"]] = extract_messages(str(db_path), s["id"])
        text_map[s["id"]] = extract_text_parts(str(db_path), s["id"])

    print(f"提取待办事项 ...", flush=True)
    todos = extract_todos(str(db_path), session_ids)

    # Process
    print(f"分类工作流 ...", flush=True)
    workflows = classify_workflows(sessions, msgs_map)

    all_msgs = [m for ms in msgs_map.values() for m in ms]
    file_map = aggregate_files(all_msgs)

    # Render
    print(f"生成 Markdown ...", flush=True)
    markdown = render_markdown(workflows, file_map, todos, text_map)

    # Write
    write_output(args.output, markdown)
    print(f"\n完成! 输出: {args.output}", flush=True)
    print(f"  {len(sessions)} 个会话, {sum(w['session_count'] for w in workflows)} 个会话已分类", flush=True)
    print(f"  {len(file_map)} 个目录, {sum(len(f) for f in file_map.values())} 个文件", flush=True)
    print(f"  {len(todos)} 个待办事项", flush=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full script end-to-end**

Run:
```bash
python3 scripts/migrate_opencode_context.py \
  --limit 20 \
  --output docs/superpowers/specs/2026-06-18-opencode-context-migration.md
```
Expected: Prints extraction progress, creates output file.

- [ ] **Step 3: Verify output file structure**

Run:
```bash
head -60 docs/superpowers/specs/2026-06-18-opencode-context-migration.md
```
Expected: Header with metadata and Section 1 overview. All 6 sections present.

Run:
```bash
wc -l docs/superpowers/specs/2026-06-18-opencode-context-migration.md
```
Expected: Reasonable line count (>100 lines).

- [ ] **Step 4: Test error handling: nonexistent DB**

Run:
```bash
python3 scripts/migrate_opencode_context.py --db /nonexistent/path.db
```
Expected: Exit code 1 with "错误: 数据库文件不存在" message.

- [ ] **Step 5: Test error handling: wrong project_id**

Run:
```bash
python3 scripts/migrate_opencode_context.py --project-id nonexistent --limit 3
```
Expected: Prints warning "未找到匹配的会话", outputs empty report.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_opencode_context.py docs/superpowers/specs/2026-06-18-opencode-context-migration.md
git commit -m "feat: add CLI main + error handling + generate migration doc"
```

---

### Task 7: Manual verification

- [ ] **Step 1: Verify session count and grouping**

Check that the output document's section 1 correctly groups the 20 most recent sessions into:
- Agent 优化 Phase 1-3
- AgentChat 组件化重构
- 其他 (项目探索/代码审查)

Run:
```bash
grep "^### " docs/superpowers/specs/2026-06-18-opencode-context-migration.md
```

- [ ] **Step 2: Spot-check 2 sessions against OpenCode**

Pick 2 sessions from section 2, verify their title, intent text, and file list match what OpenCode shows. Use `sqlite3` to cross-reference:

```bash
sqlite3 ~/.local/share/opencode/opencode.db \
  "SELECT title FROM session WHERE id='<session-id>'"
```

- [ ] **Step 3: Verify file list completeness**

Run:
```bash
grep '`' docs/superpowers/specs/2026-06-18-opencode-context-migration.md \
  | grep -E '^\- `' \
  | sort -u \
  | head -30
```
Check that well-known recently-modified files appear (e.g. `Dockerfile`, `web/src/components/agent/`, `src/process_opt/agent/`).

- [ ] **Step 4: Run git diff to verify script + output are committed**

Run:
```bash
git log --oneline -7
```
Expected: 6 commits for the script build-up + 1 for output doc.

- [ ] **Step 5: Commit any final adjustments**

```bash
git add -A && git diff --cached --stat
# If changes:
git commit -m "chore: final verification adjustments for OpenCode migration"
```
