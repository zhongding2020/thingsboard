from __future__ import annotations

import json

import pytest

from process_opt.agent.sandbox import execute_code


class TestExecuteCode:
    def test_simple_expression(self) -> None:
        result = execute_code("print(1 + 1)")
        assert result.success
        assert "2" in result.stdout

    def test_json_output(self) -> None:
        code = """
import json
print(json.dumps({"mean": 5.0, "std": 2.0}))
"""
        result = execute_code(code)
        data = json.loads(result.stdout.strip())
        assert data["mean"] == 5.0

    def test_timeout(self) -> None:
        code = "import time; time.sleep(10)"
        result = execute_code(code, timeout=1)
        assert not result.success
        assert "timed out" in result.error.lower()

    def test_numpy_available(self) -> None:
        code = "import numpy as np; print(np.array([1,2,3]).mean())"
        result = execute_code(code)
        assert result.success
        assert "2.0" in result.stdout

    def test_syntax_error(self) -> None:
        code = "print(1/0)"
        result = execute_code(code)
        assert not result.success

    def test_stderr_captured(self) -> None:
        code = "import sys; sys.stderr.write('error msg'); print('ok')"
        result = execute_code(code)
        assert result.success
        assert "error msg" in result.stderr
