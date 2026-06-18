from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning("Tool %s retry %d/%d: %s", func.__name__, attempt + 1, max_retries, e)
            raise last_error
        return wrapper
    return decorator
