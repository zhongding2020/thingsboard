from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from process_opt.agent.sandbox import execute_code

SYSTEM_PROMPT = """你是一位工厂工艺参数分析专家。你的任务是：
1. 理解用户的分析需求
2. 编写 Python 代码来完成分析
3. 执行代码并解读结果

## 可用库
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
- 每次只生成一个版本的代码
- 所有 import 都在代码内部

## 输出格式
在 ```python 代码块中提供完整的 Python 脚本。不要有其他解释，只输出代码块。
"""

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

            messages.append({"role": "assistant", "content": full_response})
            messages.append({
                "role": "user",
                "content": (
                    f"代码执行成功。stdout:\n{result.stdout[:3000]}\n\n"
                    f"请用中文解读分析结果。"
                ),
            })

            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
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
