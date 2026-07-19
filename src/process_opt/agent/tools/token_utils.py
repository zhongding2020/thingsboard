"""Token estimation and output truncation utilities.

Provides rough token counting for mixed Chinese/English text and
output truncation to keep tool results within reasonable token limits
before they enter the LLM context (via ToolMessage) and reach the frontend.
"""

from __future__ import annotations

import math
import logging

logger = logging.getLogger(__name__)

# CJK Unified Ideographs range
_CJK_START = 0x4E00
_CJK_END = 0x9FFF


def estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Chinese/English text.

    Heuristic:
      - Each CJK character ≈ 1 token
      - Every 4 non-CJK characters ≈ 1 token

    This is a conservative estimate. The actual tokenizer may vary.
    """
    if not text:
        return 0
    cjk_count = sum(1 for c in text if _CJK_START <= ord(c) <= _CJK_END)
    non_cjk = max(0, len(text) - cjk_count)
    return cjk_count + math.ceil(non_cjk / 4)


def truncate_output(
    output: str,
    max_tokens: int = 8000,
    head_lines: int = 8,
    tail_lines: int = 5,
) -> tuple[str, int, bool]:
    """Truncate a tool output string to fit within max_tokens.

    Keeps the head (header + first rows) and tail (last few rows) of
    tabular output, with a truncation notice in between.

    Returns:
        (truncated_text, original_estimated_tokens, was_truncated)
    """
    est = estimate_tokens(output)
    if est <= max_tokens:
        return output, est, False

    lines = output.split("\n")
    if len(lines) > head_lines + tail_lines + 3:
        head = lines[:head_lines]
        tail = lines[-tail_lines:]
        truncated = (
            "\n".join(head)
            + f"\n\n...(中间 {len(lines) - head_lines - tail_lines} 行已截断, "
            f"估算约 {est} tokens, 超出限制 {max_tokens} tokens)...\n\n"
            + "\n".join(tail)
        )
    else:
        # Short content that's still too large — cut by character count
        max_chars = max_tokens * 4
        truncated = (
            output[:max_chars]
            + f"\n\n...(已截断, 估算约 {est} tokens)..."
        )

    logger.info(
        "Truncated output from ~%d tokens to ~%d chars (original %d chars)",
        est, len(truncated), len(output),
    )
    return truncated, est, True
