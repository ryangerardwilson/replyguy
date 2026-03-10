from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from .errors import ReplyGuyError

ID_RE = re.compile(r"id=([^\s]+)")


@dataclass
class PostResult:
    command: list[str]
    stdout: str
    stderr: str
    post_id: str | None


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )


def validate_auth(command: list[str]) -> None:
    result = _run(command)
    if result.returncode != 0:
        raise ReplyGuyError((result.stderr or result.stdout or "auth check failed").strip())


def post_text(command: list[str], text: str) -> PostResult:
    result = _run([*command, text])
    if result.returncode != 0:
        raise ReplyGuyError((result.stderr or result.stdout or "post failed").strip())
    match = ID_RE.search(result.stdout or "")
    return PostResult(
        command=[*command, text],
        stdout=result.stdout,
        stderr=result.stderr,
        post_id=match.group(1) if match else None,
    )
