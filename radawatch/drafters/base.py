"""Base drafter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Analysis, Draft, Event, VerificationResult


class BaseDrafter(ABC):
    def __init__(self, config: Config):
        self.config = config

    @property
    @abstractmethod
    def drafter_id(self) -> str:
        """Unique ID like 'telegram_formatter'."""

    @abstractmethod
    def draft(
        self,
        events: list[Event],
        analyses: list[Analysis],
        verifications: list[VerificationResult],
    ) -> list[Draft]:
        """Generate drafts from events and analyses."""
