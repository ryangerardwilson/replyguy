from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import bookmark_queue_path, ensure_dirs


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_queue() -> dict[str, Any]:
    return {
        "synced_at": "",
        "items": [],
    }


def load_queue() -> dict[str, Any]:
    ensure_dirs()
    path = bookmark_queue_path()
    if not path.exists():
        return empty_queue()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_queue()
    if not isinstance(payload, dict):
        return empty_queue()
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "synced_at": str(payload.get("synced_at") or ""),
        "items": [item for item in items if isinstance(item, dict)],
    }


def save_queue(queue: dict[str, Any]) -> None:
    ensure_dirs()
    payload = {
        "synced_at": str(queue.get("synced_at") or ""),
        "items": [deepcopy(item) for item in queue.get("items") or [] if isinstance(item, dict)],
    }
    bookmark_queue_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def active_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "pending")
        if status in {"pending", "posted"}:
            items.append(item)
    return items


def next_pending_item(queue: dict[str, Any]) -> dict[str, Any] | None:
    for item in active_items(queue):
        if str(item.get("status") or "pending") == "pending":
            return item
    return None


def replace_item(queue: dict[str, Any], updated_item: dict[str, Any]) -> None:
    tweet_id = str(updated_item.get("tweet_id") or "")
    items = queue.get("items") or []
    for index, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("tweet_id") or "") == tweet_id:
            items[index] = updated_item
            return
    items.append(updated_item)


def remove_completed_items(queue: dict[str, Any]) -> None:
    queue["items"] = [
        item
        for item in queue.get("items") or []
        if isinstance(item, dict) and str(item.get("status") or "pending") != "done"
    ]
