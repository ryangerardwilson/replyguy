from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .codex_client import CodexResponder
from .errors import ReplyGuyError
from .fetch import FetchedSource, fetch_many, fetch_url
from .instruction_context import load_generation_instruction_context
from .notifications import notify
from .parsing import extract_urls, has_meaningful_text, split_blocks
from .paths import archive_dir, ensure_dirs, live_go_path, live_gi_path, lock_path
from .platforms import post_text, validate_auth
from .storage import (
    complete_job,
    connect_db,
    create_job,
    has_recent_exact_angle,
    recent_post_memory,
    record_post,
    record_reply,
)


@dataclass
class ProcessResult:
    job_id: str
    summary: str
    digest_path: Path
    posted: bool


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


def _build_materials(
    *,
    inbox_text: str,
    config: dict[str, Any],
) -> tuple[str, list[dict[str, str]], list[str]]:
    sources: list[dict[str, str]] = []
    urls = extract_urls(inbox_text)
    fetched_sources = fetch_many(urls, limit=8)
    for source in fetched_sources:
        sources.append(
            {
                "kind": "url",
                "url": source.url,
                "title": source.title,
                "text": _trim(source.text, 5000),
            }
        )

    cleaned_blocks = split_blocks(inbox_text)
    for block in cleaned_blocks:
        block_urls = extract_urls(block)
        sources.append(
            {
                "kind": "inbox_block",
                "url": block_urls[0] if block_urls else "",
                "title": "Inbox block",
                "text": _trim(block, 2500),
            }
        )

    if not cleaned_blocks:
        daily_sources = fetch_many(config.get("daily_topic_sources") or [], limit=5)
        for source in daily_sources:
            sources.append(
                {
                    "kind": "daily_source",
                    "url": source.url,
                    "title": source.title,
                    "text": _trim(source.text, 4000),
                }
            )

    resume_text = ""
    try:
        resume_text = fetch_url(str(config.get("resume_url") or "")).text
    except Exception:
        resume_text = ""
    return _trim(resume_text, 7000), sources, urls


def _system_prompt(reply_count: int) -> str:
    return (
        "You generate thought-leadership posts and sharp reply drafts.\n"
        "Return JSON only.\n"
        "Use this shape:\n"
        "{"
        '"post":{"should_post":true,"topic":"","career_why":"","crux":"","angle":"","linkedin_draft":"","x_draft":"","source_urls":[]},'
        '"replies":[{"source_url":"","source_excerpt":"","recommended_reply":"","alternate_replies":["","",""],"why_it_works":""}],'
        '"skipped":[{"item":"","reason":""}]}'
        "\nRules:\n"
        "- Use timely, defensible, uncommon angles tied to real shipped experience.\n"
        "- Avoid generic LinkedIn sludge.\n"
        "- LinkedIn draft must be plain text.\n"
        "- X draft must be <= 280 characters.\n"
        f"- Return at most {reply_count} replies per target.\n"
        "- Same crux can recur, but avoid the same crux+angle pair from recent memory.\n"
        "- If the materials do not justify a good post, set post.should_post to false.\n"
        "- Reply suggestions should be sharp, specific, and non-cringe.\n"
    )


def _user_prompt(
    *,
    mode: str,
    inbox_text: str,
    resume_text: str,
    sources: list[dict[str, str]],
    recent_memory: list[dict[str, Any]],
    config: dict[str, Any],
) -> str:
    instruction_docs = load_generation_instruction_context()
    payload = {
        "mode": mode,
        "daily_context_notes": config.get("daily_context_notes") or "",
        "resume_text": resume_text,
        "workspace_instruction_context": [
            {"path": doc.path, "content": doc.content} for doc in instruction_docs
        ],
        "recent_post_memory": recent_memory,
        "inbox_text": inbox_text,
        "materials": sources,
    }
    return json.dumps(payload, indent=2)


def _ensure_x_fits(client: CodexResponder, x_text: str) -> str:
    draft = (x_text or "").strip()
    if len(draft) <= 280:
        return draft
    payload = client.generate_json(
        "Return JSON only with {'x_draft':''}. Rewrite the draft to <= 280 chars while keeping the same claim.",
        json.dumps({"x_draft": draft}),
    )
    rewritten = str(payload.get("x_draft") or "").strip()
    if not rewritten:
        raise ReplyGuyError("model failed to shorten the X draft")
    return rewritten[:280]


def _write_digest(
    digest_path: Path,
    *,
    post_block: dict[str, Any] | None,
    linkedin_post_id: str | None,
    x_post_id: str | None,
    replies: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    errors: list[str],
) -> None:
    lines = ["# replyguy digest", ""]
    lines.append("## posted")
    if post_block and (linkedin_post_id or x_post_id):
        lines.extend(
            [
                f"- topic: {post_block.get('topic', '')}",
                f"- crux: {post_block.get('crux', '')}",
                f"- angle: {post_block.get('angle', '')}",
                f"- linkedin_post_id: {linkedin_post_id or '-'}",
                f"- x_post_id: {x_post_id or '-'}",
                "",
                "### linkedin",
                str(post_block.get("linkedin_draft") or ""),
                "",
                "### x",
                str(post_block.get("x_draft") or ""),
                "",
            ]
        )
    else:
        lines.append("- no post published")
        lines.append("")

    lines.append("## reply ideas")
    if replies:
        for index, reply in enumerate(replies, start=1):
            lines.extend(
                [
                    f"### reply {index}",
                    f"- source_url: {reply.get('source_url') or '-'}",
                    f"- why: {reply.get('why_it_works') or '-'}",
                    "",
                    _trim(str(reply.get("source_excerpt") or ""), 1200),
                    "",
                    "recommended:",
                    str(reply.get("recommended_reply") or ""),
                    "",
                ]
            )
            for alt_index, alt in enumerate(reply.get("alternate_replies") or [], start=1):
                if alt:
                    lines.append(f"alt {alt_index}: {alt}")
            lines.append("")
    else:
        lines.append("- no reply suggestions")
        lines.append("")

    lines.append("## skipped")
    if skipped:
        for item in skipped:
            lines.append(f"- {item.get('item', 'item')}: {item.get('reason', 'skipped')}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## failed")
    if errors:
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- none")
    lines.append("")
    digest_path.write_text("\n".join(lines), encoding="utf-8")


def process_inbox(inbox_text: str, mode: str) -> ProcessResult:
    ensure_dirs()
    config = load_config()
    conn = connect_db()
    reply_count = int(config.get("reply_count_per_target") or 4)
    responder = CodexResponder(config)

    with run_lock():
        job_id = _job_id(mode)
        job_dir = _job_dir(job_id)
        snapshot_path = job_dir / "inbox.md"
        digest_path = job_dir / "go.md"
        snapshot_path.write_text(inbox_text, encoding="utf-8")
        create_job(conn, job_id, mode=mode, inbox_snapshot_path=str(snapshot_path))

        errors: list[str] = []
        post_block: dict[str, Any] | None = None
        linkedin_post_id: str | None = None
        x_post_id: str | None = None

        try:
            resume_text, sources, discovered_urls = _build_materials(
                inbox_text=inbox_text,
                config=config,
            )
            recent_memory = recent_post_memory(conn, int(config.get("max_recent_memory") or 12))
            payload = responder.generate_json(
                _system_prompt(reply_count),
                _user_prompt(
                    mode=mode,
                    inbox_text=inbox_text,
                    resume_text=resume_text,
                    sources=sources,
                    recent_memory=recent_memory,
                    config=config,
                ),
            )

            replies = [item for item in payload.get("replies") or [] if isinstance(item, dict)]
            skipped = [item for item in payload.get("skipped") or [] if isinstance(item, dict)]
            post_candidate = payload.get("post") if isinstance(payload.get("post"), dict) else None

            if post_candidate and bool(post_candidate.get("should_post")):
                if has_recent_exact_angle(
                    conn,
                    str(post_candidate.get("crux") or ""),
                    str(post_candidate.get("angle") or ""),
                ):
                    skipped.append(
                        {
                            "item": post_candidate.get("topic") or "post",
                            "reason": "recent crux+angle already used",
                        }
                    )
                else:
                    validate_auth(list(config.get("x_auth_command") or ["x", "ea"]))
                    validate_auth(list(config.get("linkedin_auth_command") or ["linkedin", "ea"]))
                    post_candidate["x_draft"] = _ensure_x_fits(
                        responder,
                        str(post_candidate.get("x_draft") or ""),
                    )
                    linkedin_result = post_text(
                        list(config.get("linkedin_post_command") or ["linkedin", "p"]),
                        str(post_candidate.get("linkedin_draft") or ""),
                    )
                    x_result = post_text(
                        list(config.get("x_post_command") or ["x", "p"]),
                        str(post_candidate.get("x_draft") or ""),
                    )
                    linkedin_post_id = linkedin_result.post_id
                    x_post_id = x_result.post_id
                    post_block = post_candidate
                    record_post(
                        conn,
                        job_id=job_id,
                        crux=str(post_candidate.get("crux") or ""),
                        angle=str(post_candidate.get("angle") or ""),
                        source_urls=list(post_candidate.get("source_urls") or discovered_urls),
                        linkedin_post_id=linkedin_post_id,
                        x_post_id=x_post_id,
                        linkedin_text=str(post_candidate.get("linkedin_draft") or ""),
                        x_text=str(post_candidate.get("x_draft") or ""),
                    )
            for reply in replies:
                record_reply(
                    conn,
                    job_id=job_id,
                    source_url=reply.get("source_url") or None,
                    source_excerpt=str(reply.get("source_excerpt") or ""),
                    recommended_reply=str(reply.get("recommended_reply") or ""),
                    alternates=[str(item) for item in (reply.get("alternate_replies") or []) if str(item).strip()],
                    why_it_works=str(reply.get("why_it_works") or ""),
                )

            _write_digest(
                digest_path,
                post_block=post_block,
                linkedin_post_id=linkedin_post_id,
                x_post_id=x_post_id,
                replies=replies,
                skipped=skipped,
                errors=errors,
            )
            live_go_path().write_text(digest_path.read_text(encoding="utf-8"), encoding="utf-8")
            summary = f"posted={'yes' if post_block else 'no'} replies={len(replies)}"
            complete_job(conn, job_id, "ok", str(digest_path), summary)
            notify("replyguy", f"done: {summary}")
            return ProcessResult(job_id=job_id, summary=summary, digest_path=digest_path, posted=bool(post_block))
        except Exception as exc:
            errors.append(str(exc))
            _write_digest(
                digest_path,
                post_block=post_block,
                linkedin_post_id=linkedin_post_id,
                x_post_id=x_post_id,
                replies=[],
                skipped=[],
                errors=errors,
            )
            live_go_path().write_text(digest_path.read_text(encoding="utf-8"), encoding="utf-8")
            complete_job(conn, job_id, "error", str(digest_path), str(exc))
            notify("replyguy", f"failed: {exc}")
            raise


def process_gi_file() -> ProcessResult | None:
    gi_path = live_gi_path()
    if not gi_path.exists():
        gi_path.write_text(
            "<!-- Paste post seeds, URLs, snippets, and reply targets here. -->\n",
            encoding="utf-8",
        )
    raw_text = gi_path.read_text(encoding="utf-8")
    if not has_meaningful_text(raw_text):
        return None
    result = process_inbox(raw_text, "gi")
    gi_path.write_text("", encoding="utf-8")
    return result


def process_timer_tick() -> ProcessResult | None:
    gi_path = live_gi_path()
    if gi_path.exists() and has_meaningful_text(gi_path.read_text(encoding="utf-8")):
        return process_gi_file()
    return process_inbox("", "tick")
