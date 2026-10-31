"""Configuration loader: reads config.yaml and resolves ${ENV_VAR} placeholders."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_RE = re.compile(r"\$\{(\w+)\}")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        def _sub(m):
            return os.environ.get(m.group(1), "")
        return _ENV_RE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def load_config(path: str | Path | None = None) -> dict:
    if path is None:
        path = PROJECT_ROOT / "config" / "config.yaml"
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _resolve_env(raw)


class Config:
    def __init__(self, data: dict | None = None):
        self._data = data or load_config()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def collectors(self) -> dict:
        return self._data.get("collectors", {})

    @property
    def analyzers(self) -> dict:
        return self._data.get("analyzers", {})

    @property
    def cities(self) -> dict:
        return self._data.get("cities", {})

    @property
    def cadence(self) -> dict:
        return self._data.get("cadence", {
            "news_per_day": 3,
            "analytics_per_week": 2,
            "investigations_per_month": 1,
        })

    @property
    def topics(self) -> dict:
        return self._data.get("topics", {})

    @property
    def editorial(self) -> dict:
        return self._data.get("editorial", {})

    @property
    def infoprivid(self) -> dict:
        return self._data.get("infoprivid", {})

    @property
    def telegram(self) -> dict:
        return self._data.get("telegram", {})
