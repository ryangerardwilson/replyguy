from __future__ import annotations

import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .codex_client import CodexResponder
from .fetch import fetch_many
from .instruction_context import load_generation_instruction_context
from .notifications import notify
from .parsing import extract_urls, has_meaningful_text, split_blocks
from .paths import archive_dir, ensure_dirs, live_muse_path, live_rant_path, lock_path


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


def _build_materials(inbox_text: str) -> tuple[list[dict[str, str]], list[str]]:
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
    return sources, urls


def _system_prompt(reply_count: int) -> str:
    return (
        "You turn rough rants into sharp, thoughtful reply drafts.\n"
        "Return JSON only.\n"
        "Use this shape:\n"
        '{"replies":[{"source_url":"","source_excerpt":"","recommended_reply":"","alternate_replies":["","",""],"why_it_works":""}],"skipped":[{"item":"","reason":""}]}'
        "\nRules:\n"
        "- Use the user's pasted ideas and the target post text as the main input.\n"
        "- Produce thoughtful, specific, non-cringe replies.\n"
        "- The literary quality of the reply must be at least as strong as the source post and preferably stronger.\n"
        "- If the source post is elegant, the reply cannot answer in flatter or clumsier prose.\n"
        "- Prefer crisp, thought-provoking replies over longer explanatory paragraphs when both are defensible.\n"
        "- Win with cleaner phrasing and sharper distinctions, not with extra length.\n"
        "- Use dry wit or smart sarcasm when it sharpens the point, but do not drift into unserious snark.\n"
        "- Prefer cleaner distinctions, stronger rhythm, and more exact language than the source material.\n"
        "- Add judgment, tradeoffs, or consequences instead of paraphrasing the post.\n"
        "- Avoid generic applause, vague agreement, and engagement bait.\n"
        "- Replies should sound like a serious builder, not a corporate content bot.\n"
        f"- Return at most {reply_count} replies per target.\n"
        "- The user will post manually, so optimize for copy-paste quality.\n"
    )


def _user_prompt(
    *,
    mode: str,
    inbox_text: str,
    sources: list[dict[str, str]],
    config: dict[str, Any],
) -> str:
    instruction_docs = load_generation_instruction_context(config)
    payload = {
        "mode": mode,
        "workspace_instruction_context": [
            {"path": doc.path, "content": doc.content} for doc in instruction_docs
        ],
        "inbox_text": inbox_text,
        "materials": sources,
    }
    return __import__("json").dumps(payload, indent=2)


def _write_digest(
    digest_path: Path,
    *,
    replies: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    errors: list[str],
) -> None:
    lines = ["# replyguy muse", ""]
    lines.append("## reply ideas")
    if replies:
        for index, reply in enumerate(replies, start=1):
            lines.extend(
                [
                    f"### muse {index}",
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
    reply_count = int(config.get("reply_count_per_target") or 4)
    responder = CodexResponder(config)

    with run_lock():
        job_id = _job_id(mode)
        job_dir = _job_dir(job_id)
        snapshot_path = job_dir / "rant.md"
        digest_path = job_dir / "muse.md"
        snapshot_path.write_text(inbox_text, encoding="utf-8")
        errors: list[str] = []

        try:
            sources, _ = _build_materials(inbox_text)
            payload = responder.generate_json(
                _system_prompt(reply_count),
                _user_prompt(
                    mode=mode,
                    inbox_text=inbox_text,
                    sources=sources,
                    config=config,
                ),
            )

            replies = [item for item in payload.get("replies") or [] if isinstance(item, dict)]
            skipped = [item for item in payload.get("skipped") or [] if isinstance(item, dict)]

            _write_digest(
                digest_path,
                replies=replies,
                skipped=skipped,
                errors=errors,
            )
            live_muse_path().write_text(digest_path.read_text(encoding="utf-8"), encoding="utf-8")
            summary = f"replies={len(replies)}"
            notify("replyguy", f"done: {summary}")
            return ProcessResult(job_id=job_id, summary=summary, digest_path=digest_path)
        except Exception as exc:
            errors.append(str(exc))
            _write_digest(
                digest_path,
                replies=[],
                skipped=[],
                errors=errors,
            )
            live_muse_path().write_text(digest_path.read_text(encoding="utf-8"), encoding="utf-8")
            notify("replyguy", f"failed: {exc}")
            raise


def process_rant_file() -> ProcessResult | None:
    rant_path = live_rant_path()
    if not rant_path.exists():
        rant_path.write_text(
            "<!-- Paste the posts, URLs, snippets, and raw ideas you want turned into replies here. -->\n",
            encoding="utf-8",
        )
    raw_text = rant_path.read_text(encoding="utf-8")
    if not has_meaningful_text(raw_text):
        return None
    result = process_inbox(raw_text, "rant")
    rant_path.write_text("", encoding="utf-8")
    return result
