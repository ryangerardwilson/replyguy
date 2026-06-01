from __future__ import annotations

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
from .paths import config_path, ensure_dirs

ANSI_GRAY = "\033[38;5;245m"
ANSI_RESET = "\033[0m"
INSTALL_SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"
INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/ryangerardwilson/replyguy/main/install.sh"

HELP_TEXT = """Replyguy CLI
turn bookmarked X posts into replies you can post fast

global actions:
  replyguy help
    show this help
  replyguy version
    print the installed version
  replyguy upgrade
    upgrade to the latest release

features:
  inhale bookmarked X posts now and report how many replies are ready
  # inhale
  replyguy inhale

  run inhale hourly in the background, disable it, or inspect timer plus queue state
  # timer install | timer disable | timer status
  replyguy timer install
  replyguy timer disable
  replyguy timer status

  exhale bookmarked X posts, choose a reply, do a final edit, post it, and remove the bookmark
  # exhale
  replyguy exhale

  show whether inhale is running and what is queued
  # status
  replyguy status

  open the config in your editor
  # config
  replyguy config
"""


def muted(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


def print_help() -> None:
    print(muted(HELP_TEXT.rstrip()))


def upgrade_app() -> int:
    if INSTALL_SCRIPT.exists():
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(INSTALL_SCRIPT), "upgrade"],
            check=False,
            text=True,
            env=os.environ.copy(),
        )
        return result.returncode

    with urllib.request.urlopen(INSTALL_SCRIPT_URL) as response:
        script_body = response.read()

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(script_body)
        script_path = Path(handle.name)

    try:
        script_path.chmod(0o700)
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(script_path), "upgrade"],
            check=False,
            text=True,
            env=os.environ.copy(),
        )
        return result.returncode
    finally:
        script_path.unlink(missing_ok=True)


def _build_runtime_command(*args: str) -> str:
    command_parts = [shlex.quote(str(Path(sys.executable).resolve()))]
    if not getattr(sys, "frozen", False):
        command_parts.append(shlex.quote(str(Path(__file__).resolve().parents[1] / "main.py")))
    command_parts.extend(shlex.quote(arg) for arg in args)
    return " ".join(command_parts)


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


def _systemctl_user(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            check=check,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise ReplyGuyError("missing dependency: systemctl") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ReplyGuyError(detail) from exc


def open_config() -> int:
    ensure_dirs()
    load_config()
    return open_in_editor(config_path())


def open_exhale() -> int:
    from .muse import run_muse_session

    ensure_dirs()
    return run_muse_session()


def inhale_bookmarks() -> int:
    from .pipeline import sync_bookmark_queue

    ensure_dirs()
    result = sync_bookmark_queue()
    print(
        f"replyguy inhale: {result.new_inhaled} new, {result.awaiting_exhale} awaiting exhale"
    )
    return 0


def process_inhale_bookmarks() -> int:
    from .pipeline import sync_bookmark_queue

    result = sync_bookmark_queue()
    print(
        f"replyguy inhale: {result.new_inhaled} new, {result.awaiting_exhale} awaiting exhale"
    )
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
    from .status import render_status

    try:
        result = _systemctl_user("status", f"{_replyguy_unit_name()}.timer", check=False)
        timer_output = (result.stdout or result.stderr or "").strip()
        if timer_output:
            print(timer_output)
            print()
        elif result.returncode != 0:
            print(f"timer status unavailable: systemctl exited {result.returncode}")
            print()
    except ReplyGuyError as exc:
        print(f"timer status unavailable: {exc}")
        print()
    print(render_status())
    return 0


def show_status() -> int:
    from .status import render_status

    ensure_dirs()
    print(render_status())
    return 0


def _dispatch(args: list[str]) -> int:
    command = args[0]
    params = args[1:]
    if command == "exhale":
        if params:
            raise ReplyGuyError("valid shape: `replyguy exhale`")
        return open_exhale()
    if command == "inhale":
        if params:
            raise ReplyGuyError("valid shape: `replyguy inhale`")
        return inhale_bookmarks()
    if command == "config":
        if params:
            raise ReplyGuyError("valid shape: `replyguy config`")
        return open_config()
    if command == "status":
        if params:
            raise ReplyGuyError("valid shape: `replyguy status`")
        return show_status()
    if command == "timer":
        if params == ["install"]:
            return install_timer()
        if params == ["disable"]:
            return disable_timer()
        if params == ["status"]:
            return timer_status()
        raise ReplyGuyError("valid shape: `replyguy timer install|disable|status`")
    if command == "_inhale_bookmarks":
        if params:
            raise ReplyGuyError("valid shape: `replyguy _inhale_bookmarks`")
        return process_inhale_bookmarks()
    raise ReplyGuyError(f"unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args:
            print_help()
            return 0
        if args == ["help"]:
            print_help()
            return 0
        if args == ["version"]:
            print(__version__)
            return 0
        if args == ["upgrade"]:
            return upgrade_app()
        if args[0] in {"help", "version", "upgrade"}:
            raise ReplyGuyError("Use replyguy help, replyguy version, or replyguy upgrade by itself.")
        return _dispatch(args)
    except ReplyGuyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
