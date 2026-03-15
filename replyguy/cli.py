from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from _version import __version__
from rgw_cli_contract import AppSpec, resolve_install_script_path, run_app

from .config import load_config
from .editor import open_in_editor
from .errors import ReplyGuyError
from .paths import config_path, ensure_dirs

ANSI_RESET = "\033[0m"
ANSI_GRAY = "\033[38;5;245m"
INSTALL_SCRIPT = resolve_install_script_path(Path(__file__).resolve().parents[1] / "main.py")

HELP_TEXT = """Replyguy CLI
turn bookmarked X posts into replies you can post fast

flags:
  replyguy -h
    show this help
  replyguy -v
    print the installed version
  replyguy -u
    upgrade to the latest release

features:
  inhale bookmarked X posts into a prepared reply queue in the background
  # inhale
  replyguy inhale

  run inhale hourly in the background, disable it, or inspect the timer
  # ti | td | st
  replyguy ti
  replyguy td
  replyguy st

  exhale bookmarked X posts, choose a reply, do a final edit, post it, and remove the bookmark
  # exhale
  replyguy exhale

  show whether inhale is running and what is queued
  # status
  replyguy status

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


def _replyguy_unit_name() -> str:
    return "replyguy"


def _timer_environment_lines() -> list[str]:
    allowed_names = {
        "X_CLIENT_ID",
        "X_CLIENT_SECRET",
        "TWITTER_CLIENT_ID",
        "TWITTER_CLIENT_SECRET",
        "X_OAUTH2_TOKEN_FILE",
        "TWITTER_OAUTH2_TOKEN_FILE",
        "XDG_DATA_HOME",
    }
    names = sorted(
        name for name in allowed_names if os.environ.get(name)
    )
    lines: list[str] = []
    for name in names:
        value = os.environ.get(name)
        if not value:
            continue
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'Environment="{name}={escaped}"')
    return lines


def _write_timer_units() -> None:
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    service_path = systemd_dir / f"{_replyguy_unit_name()}.service"
    timer_path = systemd_dir / f"{_replyguy_unit_name()}.timer"
    entrypoint = Path(__file__).resolve().parents[1] / "main.py"
    run_command = _build_runtime_command("_inhale_bookmarks")
    runtime_path = os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin"
    environment_lines = _timer_environment_lines()
    service_body = "\n".join(
        [
            "[Unit]",
            "Description=replyguy inhale bookmarked posts",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={entrypoint.parent}",
            f"Environment=PATH={runtime_path}",
            *environment_lines,
            f"ExecStart=/usr/bin/env bash -lc {shlex.quote(run_command)}",
            "",
        ]
    )
    timer_body = "\n".join(
        [
            "[Unit]",
            "Description=Run replyguy inhale hourly",
            "",
            "[Timer]",
            "OnBootSec=5m",
            "OnUnitActiveSec=1h",
            "Persistent=true",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ]
    )
    service_path.write_text(service_body, encoding="utf-8")
    timer_path.write_text(timer_body, encoding="utf-8")


def _systemctl_user(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=True,
        text=True,
        capture_output=True,
    )


def open_config() -> int:
    ensure_dirs()
    load_config()
    return open_in_editor(config_path())


def open_exhale() -> int:
    from .muse import run_muse_session

    ensure_dirs()
    return run_muse_session()


def inhale_bookmarks() -> int:
    ensure_dirs()
    _spawn_background("_inhale_bookmarks")
    print("replyguy inhale: started background bookmark sync")
    return 0


def process_inhale_bookmarks() -> int:
    from .pipeline import sync_bookmark_queue

    sync_bookmark_queue()
    return 0


def install_timer() -> int:
    _write_timer_units()
    _systemctl_user("daemon-reload")
    _systemctl_user("enable", "--now", f"{_replyguy_unit_name()}.timer")
    print(f"timer enabled: {_replyguy_unit_name()}.timer")
    return 0


def disable_timer() -> int:
    _write_timer_units()
    _systemctl_user("disable", "--now", f"{_replyguy_unit_name()}.timer")
    print(f"timer disabled: {_replyguy_unit_name()}.timer")
    return 0


def timer_status() -> int:
    result = _systemctl_user("status", f"{_replyguy_unit_name()}.timer")
    print(result.stdout.strip())
    return 0


def show_status() -> int:
    from .status import render_status

    ensure_dirs()
    print(_muted_text(render_status()))
    return 0


def _config_path() -> Path:
    ensure_dirs()
    load_config()
    return config_path()


def _dispatch(args: list[str]) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    command = parsed.command
    if command == "exhale":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy exhale`")
        return open_exhale()
    if command == "inhale":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy inhale`")
        return inhale_bookmarks()
    if command == "conf":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy conf`")
        return open_config()
    if command == "status":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy status`")
        return show_status()
    if command == "ti":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy ti`")
        return install_timer()
    if command == "td":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy td`")
        return disable_timer()
    if command == "st":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy st`")
        return timer_status()
    if command == "_inhale_bookmarks":
        if parsed.params:
            raise ReplyGuyError("valid shape: `replyguy _inhale_bookmarks`")
        return process_inhale_bookmarks()
    raise ReplyGuyError(f"unknown command: {command}")


APP_SPEC = AppSpec(
    app_name="replyguy",
    version=__version__,
    help_text=HELP_TEXT,
    install_script_path=INSTALL_SCRIPT,
    no_args_mode="help",
    config_path_factory=_config_path,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_app(APP_SPEC, args, _dispatch)
