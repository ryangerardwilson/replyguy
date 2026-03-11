from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import ReplyGuyError


def _default_x_command() -> list[str]:
    configured = os.environ.get("REPLYGUY_X_CMD", "").strip()
    if configured:
        return shlex.split(configured)
    installed = shutil.which("x")
    if installed:
        return [installed]
    sibling_main = Path(__file__).resolve().parents[2] / "x" / "main.py"
    if sibling_main.exists():
        return [sys.executable, str(sibling_main)]
    return ["x"]


def _command_prefix(config: dict[str, Any]) -> list[str]:
    configured = str(config.get("x_command") or "").strip()
    if configured:
        return shlex.split(configured)
    return _default_x_command()


def _run_x(config: dict[str, Any], *args: str) -> str:
    command = _command_prefix(config) + list(args)
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "x command failed").strip()
        raise ReplyGuyError(detail)
    return result.stdout


def list_bookmarks(config: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    stdout = _run_x(config, "b", "ls", "-j", "-n", str(limit))
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ReplyGuyError("x bookmark listing did not return valid JSON") from exc
    bookmarks = payload.get("bookmarks")
    if not isinstance(bookmarks, list):
        raise ReplyGuyError("x bookmark listing returned an unexpected payload")
    return [item for item in bookmarks if isinstance(item, dict)]


def post_reply(config: dict[str, Any], tweet_id: str, text: str) -> str:
    stdout = _run_x(config, "r", tweet_id, text)
    marker = "id="
    line = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    if marker in line:
        return line.split(marker, 1)[1].strip()
    return ""


def remove_bookmark(config: dict[str, Any], tweet_id: str) -> None:
    _run_x(config, "b", "rm", tweet_id)


def remove_bookmark_background(config: dict[str, Any], tweet_id: str) -> None:
    command = _command_prefix(config) + ["b", "rm", tweet_id]
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
