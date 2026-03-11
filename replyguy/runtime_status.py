from __future__ import annotations

import json
from typing import Any

from .paths import ensure_dirs, runtime_status_path


def load_runtime_status() -> dict[str, Any]:
    ensure_dirs()
    path = runtime_status_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_runtime_status(payload: dict[str, Any]) -> None:
    ensure_dirs()
    runtime_status_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clear_runtime_status() -> None:
    ensure_dirs()
    runtime_status_path().unlink(missing_ok=True)
