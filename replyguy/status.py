from __future__ import annotations

import fcntl
from pathlib import Path
from typing import Any

from .bookmark_queue import load_queue
from .paths import archive_dir, ensure_dirs, lock_path
from .runtime_status import load_runtime_status


def _is_inhale_running() -> bool:
    ensure_dirs()
    path = lock_path()
    path.touch(exist_ok=True)
    with path.open("r+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False


def _latest_job_dir() -> Path | None:
    jobs = [path for path in archive_dir().iterdir() if path.is_dir()]
    if not jobs:
        return None
    return max(jobs, key=lambda path: path.stat().st_mtime)


def _latest_error(items: list[dict[str, Any]]) -> str:
    latest_item: dict[str, Any] | None = None
    latest_key = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        error = str(item.get("generation_error") or "").strip()
        if not error:
            continue
        sort_key = str(item.get("generated_at") or "")
        if sort_key >= latest_key:
            latest_key = sort_key
            latest_item = item
    if latest_item is None:
        return "-"
    error = str(latest_item.get("generation_error") or "").strip()
    tweet_id = str(latest_item.get("tweet_id") or "").strip()
    if tweet_id:
        return f"{tweet_id}: {error}"
    return error or "-"


def render_status() -> str:
    ensure_dirs()
    queue = load_queue()
    runtime = load_runtime_status()
    items = [item for item in queue.get("items") or [] if isinstance(item, dict)]
    pending = [
        item for item in items if str(item.get("status") or "pending") == "pending"
    ]
    posted_waiting = [
        item
        for item in items
        if str(item.get("status") or "") == "posted" and not item.get("bookmark_removed")
    ]
    latest_job = _latest_job_dir()
    latest_job_value = latest_job.name if latest_job is not None else "-"
    runtime_error = str(runtime.get("last_error") or "").strip()
    inhale_running = _is_inhale_running()
    if runtime_error:
        latest_error_value = runtime_error
    elif inhale_running:
        latest_error_value = "-"
    else:
        latest_error_value = _latest_error(items)

    lines = [
        "replyguy status",
        "",
        f"running      : {'yes' if inhale_running else 'no'}",
        f"phase        : {str(runtime.get('phase') or '-')}",
        f"job_id       : {str(runtime.get('job_id') or '-')}",
        f"last_inhale  : {str(queue.get('synced_at') or '-')}",
        f"last_new     : {int(runtime.get('new_inhaled') or 0)}",
        f"progress     : {int(runtime.get('current') or 0)}/{int(runtime.get('total') or 0)}",
        f"current_id   : {str(runtime.get('current_tweet_id') or '-')}",
        f"pending      : {len(pending)}",
        f"posted_wait  : {len(posted_waiting)}",
        f"tracked      : {len(items)}",
        f"latest_job   : {latest_job_value}",
        f"latest_error : {latest_error_value}",
    ]
    return "\n".join(lines)
