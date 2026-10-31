"""Base collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Event
from ..state import StateManager


class BaseCollector(ABC):
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique ID like 'odesa.sessions'."""

    @property
    def city(self) -> str:
        return self.source_id.split(".")[0]

    @abstractmethod
    def collect(self) -> list[Event]:
        """Fetch new events from the source."""

    def make_event_id(self, key: str) -> str:
        return f"{self.source_id}|{key}"
