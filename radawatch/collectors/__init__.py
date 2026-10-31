"""Collector registry: auto-discovers and registers collectors."""

from __future__ import annotations

from typing import Type

from .base import BaseCollector

COLLECTOR_REGISTRY: dict[str, Type[BaseCollector]] = {}


def register_collector(cls: Type[BaseCollector]) -> Type[BaseCollector]:
    sid = cls.source_id.fget(None)  # type: ignore[attr-defined]
    COLLECTOR_REGISTRY[sid] = cls
    return cls


def get_collector(source_id: str) -> Type[BaseCollector] | None:
    return COLLECTOR_REGISTRY.get(source_id)


def list_collectors() -> list[str]:
    return sorted(COLLECTOR_REGISTRY.keys())
