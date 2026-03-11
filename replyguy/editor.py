from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


def resolve_editor() -> str:
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"


def _editor_argv() -> list[str]:
    editor = resolve_editor().strip()
    return shlex.split(editor) if editor else ["vim"]


def open_in_editor(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return subprocess.run(_editor_argv() + [str(path)], check=False).returncode


def edit_text(initial_text: str, suffix: str = ".md") -> str | None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        path = Path(handle.name)
        handle.write(initial_text.encode("utf-8"))

    try:
        rc = open_in_editor(path)
        if rc != 0:
            return None
        return path.read_text(encoding="utf-8").strip()
    finally:
        path.unlink(missing_ok=True)
