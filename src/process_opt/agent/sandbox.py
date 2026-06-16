from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from process_opt.agent.schemas import ExecutionResult


def execute_code(
    code: str,
    timeout: int = 30,
    workdir: str | None = None,
) -> ExecutionResult:
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="agent_sandbox_")

    script_path = Path(workdir) / "_agent_script.py"
    script_path.write_text(code, encoding="utf-8")

    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        return ExecutionResult(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            execution_time=round(elapsed, 3),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return ExecutionResult(
            success=False,
            error=f"Execution timed out after {timeout}s",
            execution_time=round(elapsed, 3),
        )
    except Exception as e:
        elapsed = time.time() - start
        return ExecutionResult(
            success=False,
            error=str(e),
            execution_time=round(elapsed, 3),
        )
