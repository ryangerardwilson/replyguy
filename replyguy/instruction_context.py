from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InstructionDocument:
    path: str
    content: str


def _read_text(path: Path, limit: int = 20000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "\n...[truncated]"


def load_generation_instruction_context(config: dict[str, Any]) -> list[InstructionDocument]:
    configured_paths = config.get("codex_context_paths") or []
    if not isinstance(configured_paths, list):
        configured_paths = []
    docs: list[InstructionDocument] = []
    for raw_path in configured_paths:
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        path = Path(raw_path).expanduser()
        content = _read_text(path)
        if content:
            docs.append(InstructionDocument(path=str(path), content=content))
    return docs
