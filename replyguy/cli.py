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
from .paths import config_path, ensure_dirs, live_go_path, live_gi_path

ANSI_RESET = "\033[0m"
ANSI_GRAY = "\033[38;5;245m"
INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/ryangerardwilson/replyguy/main/install.sh"

HELP_TEXT = """Replyguy CLI
turn a vim-first inbox into posted thought leadership and reply drafts

flags:
  replyguy -h
    show this help
  replyguy -v
    print the installed version
  replyguy -u
    upgrade to the latest release

features:
  open the inbox in your editor, then digest it on exit and act on it
  # gi
  replyguy gi

  open the latest digest output in your editor
  # go
  replyguy go

  open the config in your editor
  # conf
  replyguy conf

  install, disable, or inspect the daily timer
  # ti|td|st
  replyguy ti
  replyguy td
  replyguy st
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
    return parser


def _build_runtime_command(*args: str) -> str:
    command_parts = [shlex.quote(str(Path(sys.executable).resolve()))]
    if not getattr(sys, "frozen", False):
        command_parts.append(shlex.quote(str(Path(__file__).resolve().parents[1] / "main.py")))
    command_parts.extend(shlex.quote(arg) for arg in args)
    return " ".join(command_parts)


def _systemctl_user(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=True,
        text=True,
        capture_output=True,
    )


def write_timer_units() -> None:
    ensure_dirs()
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    service_path = systemd_dir / "replyguy.service"
    timer_path = systemd_dir / "replyguy.timer"
    timer_on_calendar = str(load_config().get("timer_on_calendar") or "*-*-* 09:00:00")
    tick_command = _build_runtime_command("_tick")
    service_body = "\n".join(
        [
            "[Unit]",
            "Description=replyguy daily thought-leadership run",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={Path(__file__).resolve().parents[1]}",
            f"ExecStart=/usr/bin/env bash -lc {shlex.quote(tick_command)}",
            "",
        ]
    )
    timer_body = "\n".join(
        [
            "[Unit]",
            "Description=Run replyguy daily",
            "",
            "[Timer]",
            f"OnCalendar={timer_on_calendar}",
            "Persistent=true",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ]
    )
    service_path.write_text(service_body, encoding="utf-8")
    timer_path.write_text(timer_body, encoding="utf-8")


def install_timer() -> int:
    write_timer_units()
    _systemctl_user("daemon-reload")
    _systemctl_user("enable", "--now", "replyguy.timer")
    print("timer enabled: replyguy.timer")
    return 0


def disable_timer() -> int:
    write_timer_units()
    _systemctl_user("disable", "--now", "replyguy.timer")
    print("timer disabled: replyguy.timer")
    return 0


def timer_status() -> int:
    result = _systemctl_user("status", "replyguy.timer")
    print(result.stdout.strip())
    return 0


def open_config() -> int:
    ensure_dirs()
    load_config()
    return open_in_editor(config_path())


def open_gi() -> int:
    ensure_dirs()
    gi_path = live_gi_path()
    if not gi_path.exists():
        gi_path.write_text(
            "<!-- Paste post seeds, URLs, snippets, and reply targets here. -->\n",
            encoding="utf-8",
        )
    rc = open_in_editor(gi_path)
    if rc != 0:
        return rc
    from .pipeline import process_gi_file

    result = process_gi_file()
    if result is None:
        print("replyguy gi: inbox empty")
        return 0
    print(result.summary)
    return 0


def open_go() -> int:
    ensure_dirs()
    go_path = live_go_path()
    if not go_path.exists():
        go_path.write_text("# replyguy digest\n\n- no digest yet\n", encoding="utf-8")
    return open_in_editor(go_path)


def tick() -> int:
    from .pipeline import process_timer_tick

    result = process_timer_tick()
    if result is None:
        print("replyguy tick: no work")
        return 0
    print(result.summary)
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
    if command == "gi":
        return open_gi()
    if command == "go":
        return open_go()
    if command == "conf":
        return open_config()
    if command == "ti":
        return install_timer()
    if command == "td":
        return disable_timer()
    if command == "st":
        return timer_status()
    if command == "_tick":
        return tick()
    raise ReplyGuyError(f"unknown command: {command}")
