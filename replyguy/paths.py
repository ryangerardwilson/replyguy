from __future__ import annotations

import os
from pathlib import Path

APP = "replyguy"


def _xdg_path(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    if value:
        return Path(value).expanduser()
    return fallback


def config_dir() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config") / APP


def state_dir() -> Path:
    return _xdg_path("XDG_STATE_HOME", Path.home() / ".local" / "state") / APP


def cache_dir() -> Path:
    return _xdg_path("XDG_CACHE_HOME", Path.home() / ".cache") / APP


def config_path() -> Path:
    return config_dir() / "config.json"


def live_muse_path() -> Path:
    return state_dir() / "muse.md"


def bookmark_queue_path() -> Path:
    return state_dir() / "bookmark_queue.json"


def runtime_status_path() -> Path:
    return state_dir() / "runtime_status.json"


def archive_dir() -> Path:
    return state_dir() / "jobs"


def lock_path() -> Path:
    return state_dir() / "replyguy.lock"


def ensure_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    state_dir().mkdir(parents=True, exist_ok=True)
    cache_dir().mkdir(parents=True, exist_ok=True)
    archive_dir().mkdir(parents=True, exist_ok=True)
