from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from process_opt.agent.sandbox import execute_code

SYSTEM_PROMPT = """你是一位工厂工艺参数分析专家。

## 工作方式
- 如果用户只是打招呼、问简单问题，直接用文字回复，不要生成代码。
- 如果用户需要数据分析（相关性、帕累托、回归、优化、查询数据等），生成 Python 代码来执行分析。

## 数据分析时可用库
numpy, scipy, scikit-learn, pandas, statsmodels, json, math

## 数据库查询
```python
import sys; sys.path.insert(0, ".")
from process_opt.agent.db import query
rows = query("SELECT * FROM analysis_records LIMIT 10")
```

## 代码要求
- 输出结果用 print(json.dumps(...)) 格式
- 代码必须完整、可独立运行
- 所有 import 都在代码内部
- 只有在需要数据分析时才生成 ```python 代码块
"""

INTERPRET_PROMPT = """代码执行成功。请用中文解读分析结果，给用户直观易懂的结论和建议。
仅用文字回复，不要生成任何代码。"""

MAX_RETRIES = 3


def _extract_code(text: str) -> str | None:
    m = re.search(r"```python\n(.+?)\n```", text, re.DOTALL)
    return m.group(1).strip() if m else None


async def run_agent(
    request_message: str,
    api_key: str,
    model: str = "gpt-4o",
    base_url: str | None = None,
) -> AsyncIterator[str]:
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = AsyncOpenAI(**client_kwargs)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request_message},
    ]

    yield json.dumps({"type": "status", "content": "thinking"}) + "\n"

    for attempt in range(MAX_RETRIES):
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        full_response = ""
        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            full_response += content

        code = _extract_code(full_response)
        if not code:
            yield json.dumps({"type": "text", "content": full_response}) + "\n"
            return

        yield json.dumps({"type": "code", "content": code}) + "\n"
        yield json.dumps({"type": "status", "content": "executing"}) + "\n"

        result = execute_code(code)

        if result.success:
            yield json.dumps({
                "type": "result",
                "content": result.stdout[:2000],
                "execution_time": result.execution_time,
            }) + "\n"

            # Interpret results without code generation
            interpret_messages = [
                {"role": "system", "content": INTERPRET_PROMPT},
                {"role": "user", "content": f"代码输出:\n{result.stdout[:3000]}\n\n任务: {request_message}"},
            ]

            stream = await client.chat.completions.create(
                model=model,
                messages=interpret_messages,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                yield json.dumps({"type": "text", "content": content}) + "\n"
            return
        else:
            error_msg = result.stderr or result.error or "Unknown error"
            yield json.dumps({"type": "error", "content": error_msg[:500]}) + "\n"

            messages.append({"role": "assistant", "content": full_response})
            messages.append({
                "role": "user",
                "content": f"代码执行出错:\n{error_msg}\n\n请修正代码后重新输出，只输出修正后的 ```python 代码块。",
            })

    yield json.dumps({"type": "status", "content": f"failed after {MAX_RETRIES} attempts"}) + "\n"
