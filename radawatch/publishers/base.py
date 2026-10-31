"""Base publisher interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Analysis, Draft, Event


class BasePublisher(ABC):
    def __init__(self, config: Config):
        self.config = config

    @property
    @abstractmethod
    def publisher_id(self) -> str:
        """Unique ID like 'telegram'."""

    @abstractmethod
    def publish(self, draft: Draft, events: list[Event], analyses: list[Analysis]) -> bool:
        """Publish the draft. Returns True on success."""
