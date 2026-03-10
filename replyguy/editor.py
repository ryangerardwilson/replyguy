from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_editor() -> str:
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"


def open_in_editor(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return subprocess.run([resolve_editor(), str(path)], check=False).returncode
