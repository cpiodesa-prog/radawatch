"""Analyzer registry."""

from __future__ import annotations

from typing import Type

from .base import BaseAnalyzer

ANALYZER_REGISTRY: dict[str, Type[BaseAnalyzer]] = {}


def register_analyzer(cls: Type[BaseAnalyzer]) -> Type[BaseAnalyzer]:
    ANALYZER_REGISTRY[cls.analyzer_id.fget(cls)] = cls  # type: ignore[attr-defined]
    return cls
