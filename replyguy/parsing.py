from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s)\]>]+")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_template_comments(text: str) -> str:
    return COMMENT_RE.sub("", text or "")


def extract_urls(text: str) -> list[str]:
    seen: list[str] = []
    for match in URL_RE.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def split_blocks(text: str) -> list[str]:
    cleaned = strip_template_comments(text).replace("\r\n", "\n")
    blocks = [block.strip() for block in re.split(r"\n\s*\n+", cleaned) if block.strip()]
    return blocks


def has_meaningful_text(text: str) -> bool:
    return bool(strip_template_comments(text).strip())
