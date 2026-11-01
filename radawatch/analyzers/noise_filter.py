"""Noise filter — suppresses routine decisions that clutter Telegram.

Routine land permits for individual citizens are noise unless:
  - the person appears in people.csv (known officials)
  - the same person received multiple permits (tracked in state)
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from ..models import Event
from ..state import StateManager

log = logging.getLogger("radawatch.analyzers.noise_filter")

LAND_KEYWORD_RE = re.compile(r"земельн", re.I)
CITIZEN_ACTION_RE = re.compile(
    r"(?:надання|передач[уі]|відведення).*?"
    r"(?:громадянин[уіа]|громадянц[іи]|гр\.)",
    re.I | re.S,
)

CITIZEN_RE = re.compile(
    r"(?:громадянин[уіа]|громадянц[іи]|гр\.)\s+"
    r"([А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+(?:\s+[А-ЯІЇЄҐ][а-яіїєґ']+)?)",
    re.I,
)


def _load_known_names(data_dir: Path) -> set[str]:
    people_csv = data_dir / "people.csv"
    if not people_csv.exists():
        return set()
    names = set()
    with open(people_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            if name:
                names.add(name.lower())
    return names


class NoiseFilter:
    def __init__(self, data_dir: Path | str = "data", state: StateManager | None = None):
        self._data_dir = Path(data_dir)
        self._state = state
        self._known_names: set[str] | None = None

    @property
    def known_names(self) -> set[str]:
        if self._known_names is None:
            self._known_names = _load_known_names(self._data_dir)
            log.info("Loaded %d known names for noise filter", len(self._known_names))
        return self._known_names

    def is_noise(self, event: Event) -> bool:
        if event.category != "decision":
            return False

        text = event.title or ""
        container = event.data.get("container_text", "")
        full_text = f"{text} {container}"

        if not (LAND_KEYWORD_RE.search(full_text) and CITIZEN_ACTION_RE.search(full_text)):
            return False

        citizen_match = CITIZEN_RE.search(full_text)
        if not citizen_match:
            return False

        person_name = citizen_match.group(1).strip()

        if person_name.lower() in self.known_names:
            log.info("Land permit for known person %s — NOT noise", person_name)
            return False

        if self._state:
            history = self._state.get_person_history(person_name)
            if len(history) >= 1:
                log.info("Land permit for repeat person %s (%d prior) — NOT noise",
                         person_name, len(history))
                return False

        return True

    def extract_citizen_name(self, event: Event) -> str | None:
        text = f"{event.title} {event.data.get('container_text', '')}"
        m = CITIZEN_RE.search(text)
        return m.group(1).strip() if m else None
