from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_path, ensure_dirs

DEFAULT_CONFIG: dict[str, Any] = {
    "codex_model": "gpt-5.4",
    "codex_reasoning_effort": "xhigh",
    "codex_context_paths": [
        "/home/ryan/Documents/agent_context/REPLY_GUY_GUIDELINES.md",
    ],
    "reply_count_per_target": 4,
}


def _merge_defaults(value: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    for key, item in value.items():
        merged[key] = item
    return merged


def load_config() -> dict[str, Any]:
    ensure_dirs()
    path = config_path()
    if not path.exists():
        save_config(deepcopy(DEFAULT_CONFIG))
        return deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        save_config(deepcopy(DEFAULT_CONFIG))
        return deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        save_config(deepcopy(DEFAULT_CONFIG))
        return deepcopy(DEFAULT_CONFIG)
    merged = _merge_defaults(data)
    if merged != data:
        save_config(merged)
    return merged


def save_config(config: dict[str, Any]) -> None:
    ensure_dirs()
    config_path().write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
