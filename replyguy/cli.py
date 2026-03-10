from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from _version import __version__

from .config import load_config
from .editor import open_in_editor
from .errors import ReplyGuyError
from .paths import config_path, ensure_dirs, live_muse_path, live_rant_path

ANSI_RESET = "\033[0m"
ANSI_GRAY = "\033[38;5;245m"
INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/ryangerardwilson/replyguy/main/install.sh"

HELP_TEXT = """Replyguy CLI
turn rants into muses you can copy-paste manually

flags:
  replyguy -h
    show this help
  replyguy -v
    print the installed version
  replyguy -u
    upgrade to the latest release

features:
  open the rant file in your editor, then launch drafting in the background
  # rant [<path_to_input_txt_or_md_file>]
  replyguy rant
  replyguy rant ~/tmp/ideas.txt

  open the latest muse output in your editor, then clear it on close
  # muse
  replyguy muse

  open the config in your editor
  # conf
  replyguy conf
"""


def _muted_text(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


def print_help() -> None:
    print(_muted_text(HELP_TEXT.rstrip()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="replyguy", add_help=False)
    parser.add_argument("-h", action="store_true", dest="help")
    parser.add_argument("-v", action="store_true", dest="version")
    parser.add_argument("-u", action="store_true", dest="upgrade")
    parser.add_argument("command", nargs="?")
    parser.add_argument("params", nargs=argparse.REMAINDER)
    return parser


def _build_runtime_command(*args: str) -> str:
    command_parts = [shlex.quote(str(Path(sys.executable).resolve()))]
    if not getattr(sys, "frozen", False):
        command_parts.append(shlex.quote(str(Path(__file__).resolve().parents[1] / "main.py")))
    command_parts.extend(shlex.quote(arg) for arg in args)
    return " ".join(command_parts)


def _runtime_argv(*args: str) -> list[str]:
    command_parts = [str(Path(sys.executable).resolve())]
    if not getattr(sys, "frozen", False):
        command_parts.append(str(Path(__file__).resolve().parents[1] / "main.py"))
    command_parts.extend(args)
    return command_parts


def _spawn_background(*args: str) -> None:
    subprocess.Popen(
        _runtime_argv(*args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


def open_config() -> int:
    ensure_dirs()
    load_config()
    return open_in_editor(config_path())


def open_rant(input_path: str | None = None) -> int:
    ensure_dirs()
    if input_path:
        source_path = Path(input_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            raise ReplyGuyError(f"missing input file: {source_path}")
        _spawn_background("_rant_file", str(source_path))
        print(f"replyguy rant: started background job for {source_path}")
    else:
        rant_path = live_rant_path()
        if not rant_path.exists():
            rant_path.write_text(
                "<!-- Paste the posts, URLs, snippets, and raw ideas you want turned into replies here. -->\n",
                encoding="utf-8",
            )
        rc = open_in_editor(rant_path)
        if rc != 0:
            return rc
        _spawn_background("_rant_live")
        print("replyguy rant: started background job")
    return 0


def open_muse() -> int:
    ensure_dirs()
    muse_path = live_muse_path()
    if not muse_path.exists():
        muse_path.write_text("# replyguy muse\n\n- no muse yet\n", encoding="utf-8")
    rc = open_in_editor(muse_path)
    muse_path.write_text("", encoding="utf-8")
    return rc


def process_rant_live() -> int:
    from .pipeline import process_rant_file

    result = process_rant_file()
    if result is None:
        return 0
    return 0


def process_rant_file_path(input_path: str) -> int:
    from .pipeline import process_inbox

    source_path = Path(input_path).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise ReplyGuyError(f"missing input file: {source_path}")
    try:
        inbox_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReplyGuyError(f"failed to read input file `{source_path}`: {exc}") from exc
    process_inbox(inbox_text, "rant")
    return 0


def upgrade_app() -> int:
    with urllib.request.urlopen(INSTALL_SCRIPT_URL, timeout=20) as response:
        script_body = response.read()
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(script_body)
        script_path = Path(handle.name)
    try:
        script_path.chmod(0o700)
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(script_path), "-u"],
            check=False,
            text=True,
            env=os.environ.copy(),
        )
        return result.returncode
    finally:
        script_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print_help()
        return 0
    if args == ["-h"]:
        print_help()
        return 0
    if args == ["-v"]:
        print(__version__)
        return 0
    if args == ["-u"]:
        return upgrade_app()

    parser = build_parser()
    parsed = parser.parse_args(args)

    if parsed.help:
        print_help()
        return 0
    if parsed.version and len(args) > 1:
        raise ReplyGuyError("`replyguy -v` cannot be combined with another action")
    if parsed.upgrade and len(args) > 1:
        raise ReplyGuyError("`replyguy -u` cannot be combined with another action")

    command = parsed.command
    if command == "rant":
        if len(parsed.params) > 1:
            raise ReplyGuyError("valid shape: `replyguy rant [<path_to_input_txt_or_md_file>]`")
        return open_rant(parsed.params[0] if parsed.params else None)
    if command == "muse":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy muse`")
        return open_muse()
    if command == "conf":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy conf`")
        return open_config()
    if command == "_rant_live":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy _rant_live`")
        return process_rant_live()
    if command == "_rant_file":
        if len(parsed.params) != 1:
            raise ReplyGuyError("valid shape: `replyguy _rant_file <path>`")
        return process_rant_file_path(parsed.params[0])
    raise ReplyGuyError(f"unknown command: {command}")
