from __future__ import annotations

import json
import re
from pathlib import Path


def read_opencode_config() -> dict[str, str]:
    """Read opencode config to get LLM provider settings.
    
    Returns { "base_url": "...", "api_key": "...", "model": "..." }
    Designed as fallback when env vars are not set.
    """
    candidates = [
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
        Path("/etc/opencode/opencode.jsonc"),
    ]

    for path in candidates:
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            # Strip JSONC comments while preserving URLs (https://)
            stripped = re.sub(r"(?<!:)//[^\n]*", "", raw)
            stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
            config = json.loads(stripped)

            provider_id, provider_cfg = next(iter(config.get("provider", {}).items()), (None, None))
            if provider_cfg is None:
                break

            base_url = provider_cfg.get("options", {}).get("baseURL", "")
            api_key = provider_cfg.get("options", {}).get("apiKey", "")

            models = provider_cfg.get("models", {})
            user_model = config.get("model", "")
            model = user_model.split("/")[-1] if "/" in user_model else user_model

            if model not in models and models:
                model = next(iter(models.keys()))

            return {"base_url": base_url, "api_key": api_key, "model": model}

    return {"base_url": "", "api_key": "", "model": "gpt-4o"}
