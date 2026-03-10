from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


def load_generation_instruction_context() -> list[InstructionDocument]:
    candidate_paths = [
        Path("/home/ryan/AGENTS.md"),
        Path("/home/ryan/Documents/agent_context/THOUGHT_LEADERSHIP.md"),
        Path("/home/ryan/Documents/agent_context/BRAND_GUIDELINES.md"),
        Path("/home/ryan/Apps/replyguy/AGENTS.md"),
    ]
    docs: list[InstructionDocument] = []
    for path in candidate_paths:
        content = _read_text(path)
        if content:
            docs.append(InstructionDocument(path=str(path), content=content))
    return docs
