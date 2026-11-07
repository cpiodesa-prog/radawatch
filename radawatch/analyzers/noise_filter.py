"""Noise filter — suppresses routine decisions that clutter Telegram.

Filtered categories:
  1. All land-related decisions (земельн*) — unless a known official is mentioned
  2. Supporting/aggregate documents (пояснювальна записка, додаток, зведена таблиця)
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

CITIZEN_RE = re.compile(
    r"(?:громадянин[уіа]|громадянц[іи]|гр\.)\s+"
    r"([А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+(?:\s+[А-ЯІЇЄҐ][а-яіїєґ']+)?)",
    re.I,
)

SUPPORTING_DOC_RE = re.compile(
    r"(?:пояснювальн[аі]\s+записк|додаток\b|зведен[аі]\s+таблиц|порівняльн[аі]\s+таблиц)",
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

        if SUPPORTING_DOC_RE.search(text):
            log.debug("Supporting document filtered: %s", text[:80])
            return True

        if LAND_KEYWORD_RE.search(full_text):
            citizen_match = CITIZEN_RE.search(full_text)
            if citizen_match:
                person_name = citizen_match.group(1).strip()
                if person_name.lower() in self.known_names:
                    log.info("Land decision mentions known person %s — NOT noise", person_name)
                    return False
                if self._state:
                    history = self._state.get_person_history(person_name)
                    if len(history) >= 1:
                        log.info("Land decision mentions repeat person %s (%d prior) — NOT noise",
                                 person_name, len(history))
                        return False
            return True

        return False

    def extract_citizen_name(self, event: Event) -> str | None:
        text = f"{event.title} {event.data.get('container_text', '')}"
        m = CITIZEN_RE.search(text)
        return m.group(1).strip() if m else None
