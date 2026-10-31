"""Base verifier interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Analysis, Event, VerificationResult
from ..state import StateManager


class BaseVerifier(ABC):
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state

    @property
    @abstractmethod
    def verifier_id(self) -> str:
        """Unique ID like 'dedup'."""

    @abstractmethod
    def verify(self, events: list[Event], analyses: list[Analysis]) -> list[VerificationResult]:
        """Cross-check events and analyses."""
