from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

_logger = logging.getLogger("biteai.feature_flags")

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "feature_flags.yaml"

_flags: dict[str, bool] = {}
_loaded = False


def _load_flags() -> dict[str, bool]:
    flags: dict[str, bool] = {}
    if yaml is not None and _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for k, v in raw.items():
            flags[str(k)] = bool(v)
    return flags


def _env_override(name: str) -> bool | None:
    env_key = f"FF_{name.upper()}"
    val = os.environ.get(env_key)
    if val is None:
        return None
    return val.lower() in ("1", "true", "yes")


def _ensure_loaded() -> None:
    global _loaded, _flags
    if _loaded:
        return
    _flags = _load_flags()
    _loaded = True
    _logger.info("Feature flags loaded: %s", _flags)


def get_flag(name: str, default: bool = False) -> bool:
    _ensure_loaded()
    env = _env_override(name)
    if env is not None:
        return env
    return _flags.get(name, default)


def set_flag(name: str, value: bool) -> None:
    _ensure_loaded()
    _flags[name] = value


def all_flags() -> dict[str, bool]:
    _ensure_loaded()
    return dict(_flags)


def reload_flags() -> None:
    global _loaded, _flags
    _flags = _load_flags()
    _loaded = True
    _logger.info("Feature flags reloaded: %s", _flags)
