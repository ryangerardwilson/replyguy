from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .bookmark_queue import load_queue, now_iso, save_queue
from .codex_client import CodexResponder
from .fetch import fetch_many
from .instruction_context import load_generation_instruction_context
from .notifications import notify
from .parsing import extract_urls
from .paths import archive_dir, ensure_dirs, live_muse_path, lock_path
from .runtime_status import save_runtime_status
from .x_bridge import list_bookmarks


@dataclass
class ProcessResult:
    job_id: str
    summary: str
    digest_path: Path


def _job_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _job_dir(job_id: str) -> Path:
    path = archive_dir() / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def run_lock():
    ensure_dirs()
    lock_file = lock_path()
    lock_file.touch(exist_ok=True)
    with lock_file.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _trim(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _bookmark_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string"},
            "recommended_reply": {"type": "string"},
            "alternate_replies": {
                "type": "array",
                "items": {"type": "string"},
            },
            "why_it_works": {"type": "string"},
            "skip_reason": {"type": "string"},
        },
        "required": [
            "status",
            "recommended_reply",
            "alternate_replies",
            "why_it_works",
            "skip_reason",
        ],
    }


def _bookmark_system_prompt(reply_count: int) -> str:
    return (
        "You prepare sharp reply options for one bookmarked X post.\n"
        "Return JSON only.\n"
        "status must be either `reply` or `skip`.\n"
        "If the post is not worth replying to, set status to `skip` and explain briefly in skip_reason.\n"
        "If status is `reply`, provide one recommended reply and several distinct alternates.\n"
        "Rules:\n"
        "- The app-level prompt owns task coordination and output shape, not voice or taste.\n"
        "- Use the configured instruction context for tone, style, rhetorical strategy, and quality bar.\n"
        "- Keep each option short enough for an X reply unless the configured instruction context clearly calls for a different shape.\n"
        "- In `why_it_works`, briefly explain the winning move.\n"
        "- When only one real angle exists, return fewer options rather than padded rewrites.\n"
        f"- Return at most {reply_count} total reply options.\n"
    )


def _bookmark_user_prompt(
    *,
    bookmark: dict[str, Any],
    config: dict[str, Any],
) -> str:
    instruction_docs = load_generation_instruction_context(config)
    materials: list[dict[str, str]] = [
        {
            "kind": "bookmarked_post",
            "url": str(bookmark.get("url") or ""),
            "title": "Bookmarked X post",
            "text": _trim(str(bookmark.get("text") or ""), 2500),
        }
    ]
    for source in fetch_many(extract_urls(str(bookmark.get("text") or "")), limit=4):
        materials.append(
            {
                "kind": "linked_url",
                "url": source.url,
                "title": source.title,
                "text": _trim(source.text, 4000),
            }
        )
    payload = {
        "workspace_instruction_context": [
            {"path": doc.path, "content": doc.content} for doc in instruction_docs
        ],
        "bookmark": bookmark,
        "materials": materials,
    }
    return json.dumps(payload, indent=2)


def _write_bookmark_digest(digest_path: Path, items: list[dict[str, Any]]) -> None:
    lines = ["# replyguy bookmark queue", ""]
    pending = [item for item in items if str(item.get("status") or "pending") == "pending"]
    lines.append(f"- pending: {len(pending)}")
    lines.append("")
    for index, item in enumerate(pending, start=1):
        lines.extend(
            [
                f"## bookmark {index}",
                f"- tweet_id: {item.get('tweet_id') or '-'}",
                f"- author: @{item.get('author_username') or '-'}",
                f"- url: {item.get('url') or '-'}",
                "",
                _trim(str(item.get("text") or ""), 800),
                "",
            ]
        )
        options = item.get("reply_options") or []
        if options:
            for option_index, option in enumerate(options, start=1):
                lines.append(f"{option_index}. {option}")
        else:
            reason = item.get("generation_error") or item.get("skip_reason") or "no reply prepared"
            lines.append(f"- {reason}")
        lines.append("")
    digest_path.write_text("\n".join(lines), encoding="utf-8")


def _dedupe_replies(recommended: str, alternates: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for raw in [recommended] + list(alternates):
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _draft_bookmark(
    bookmark: dict[str, Any],
    *,
    responder: CodexResponder,
    config: dict[str, Any],
) -> dict[str, Any]:
    reply_count = int(config.get("reply_count_per_target") or 4)
    payload = responder.generate_json_with_schema(
        _bookmark_schema(),
        _bookmark_system_prompt(reply_count),
        _bookmark_user_prompt(bookmark=bookmark, config=config),
    )
    status = str(payload.get("status") or "reply").strip().lower()
    options = _dedupe_replies(
        str(payload.get("recommended_reply") or ""),
        [item for item in payload.get("alternate_replies") or [] if isinstance(item, str)],
        reply_count,
    )
    item = dict(bookmark)
    item["generated_at"] = now_iso()
    item["why_it_works"] = str(payload.get("why_it_works") or "").strip()
    item["skip_reason"] = str(payload.get("skip_reason") or "").strip()
    item["reply_options"] = options if status == "reply" else []
    item["status"] = "pending"
    item["posted_reply_id"] = ""
    item["bookmark_removed"] = False
    item["generation_error"] = ""
    return item

def sync_bookmark_queue() -> ProcessResult:
    ensure_dirs()
    config = load_config()
    responder = CodexResponder(config)

    with run_lock():
        job_id = _job_id("bookmark-sync")
        job_dir = _job_dir(job_id)
        digest_path = job_dir / "muse.md"
        snapshot_path = job_dir / "bookmarks.json"
        started_at = now_iso()
        save_runtime_status(
            {
                "phase": "starting",
                "running": True,
                "job_id": job_id,
                "started_at": started_at,
                "current": 0,
                "total": 0,
                "current_tweet_id": "",
                "last_error": "",
            }
        )
        notify("replyguy", "inhale started")
        try:
            existing_queue = load_queue()
            existing_items = {
                str(item.get("tweet_id") or ""): item
                for item in existing_queue.get("items") or []
                if isinstance(item, dict) and str(item.get("tweet_id") or "")
            }

            bookmarks = list_bookmarks(config, int(config.get("bookmark_sync_limit") or 100))
            merged_items: list[dict[str, Any]] = []
            total = len([bookmark for bookmark in bookmarks if str(bookmark.get("tweet_id") or "")])
            current = 0

            for bookmark in bookmarks:
                tweet_id = str(bookmark.get("tweet_id") or "")
                if not tweet_id:
                    continue
                current += 1
                save_runtime_status(
                    {
                        "phase": "drafting",
                        "running": True,
                        "job_id": job_id,
                        "started_at": started_at,
                        "current": current,
                        "total": total,
                        "current_tweet_id": tweet_id,
                        "last_error": "",
                    }
                )
                existing = existing_items.get(tweet_id)
                if existing and str(existing.get("status") or "pending") in {"pending", "posted"}:
                    if str(existing.get("status") or "pending") == "pending" and not (existing.get("reply_options") or []):
                        existing = None
                    else:
                        updated = dict(existing)
                        updated.update(bookmark)
                        merged_items.append(updated)
                        continue
                try:
                    drafted = _draft_bookmark(bookmark, responder=responder, config=config)
                    merged_items.append(drafted)
                except Exception as exc:
                    failed = dict(bookmark)
                    failed["generated_at"] = now_iso()
                    failed["reply_options"] = []
                    failed["why_it_works"] = ""
                    failed["skip_reason"] = ""
                    failed["status"] = "pending"
                    failed["posted_reply_id"] = ""
                    failed["bookmark_removed"] = False
                    failed["generation_error"] = str(exc)
                    merged_items.append(failed)
                    save_runtime_status(
                        {
                            "phase": "drafting",
                            "running": True,
                            "job_id": job_id,
                            "started_at": started_at,
                            "current": current,
                            "total": total,
                            "current_tweet_id": tweet_id,
                            "last_error": str(exc),
                        }
                    )

            queue = {
                "synced_at": now_iso(),
                "items": merged_items,
            }
            save_queue(queue)
            snapshot_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
            _write_bookmark_digest(digest_path, merged_items)
            live_muse_path().write_text(digest_path.read_text(encoding="utf-8"), encoding="utf-8")
            summary = f"bookmarks={len(merged_items)}"
            notify("replyguy", f"inhale done: {summary}")
            save_runtime_status(
                {
                    "phase": "done",
                    "running": False,
                    "job_id": job_id,
                    "started_at": started_at,
                    "current": current,
                    "total": total,
                    "current_tweet_id": "",
                    "last_error": "",
                }
            )
            return ProcessResult(job_id=job_id, summary=summary, digest_path=digest_path)
        except Exception as exc:
            save_runtime_status(
                {
                    "phase": "failed",
                    "running": False,
                    "job_id": job_id,
                    "started_at": started_at,
                    "current": 0,
                    "total": 0,
                    "current_tweet_id": "",
                    "last_error": str(exc),
                }
            )
            notify("replyguy", f"inhale failed: {exc}")
            raise
