"""Base analyzer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Analysis, Event


class BaseAnalyzer(ABC):
    def __init__(self, config: Config):
        self.config = config

    @property
    @abstractmethod
    def analyzer_id(self) -> str:
        """Unique ID like 'risk_keywords'."""

    @abstractmethod
    def analyze(self, events: list[Event]) -> list[Analysis]:
        """Analyze events and return findings."""
