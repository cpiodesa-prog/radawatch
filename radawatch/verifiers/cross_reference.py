"""Cross-reference events from different sources.

Links related events: e.g., a personnel decision + a new declaration
for the same person, or a commission agenda + a decision document.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..config import Config
from ..models import Analysis, Event, VerificationResult
from ..state import StateManager
from .base import BaseVerifier

NAME_RE = re.compile(r"[А-ЯІЇЄҐ][а-яіїєґ']+ [А-ЯІЇЄҐ][а-яіїєґ']+ [А-ЯІЇЄҐ][а-яіїєґ']+")


class CrossReferenceVerifier(BaseVerifier):
    def __init__(self, config: Config, state: StateManager):
        super().__init__(config, state)

    @property
    def verifier_id(self) -> str:
        return "cross_reference"

    def verify(self, events: list[Event], analyses: list[Analysis]) -> list[VerificationResult]:
        results = []

        person_events: dict[str, list[Event]] = {}
        for event in events:
            names = set()
            name = event.data.get("name")
            if name:
                names.add(_norm_name(name))
            for m in NAME_RE.finditer(event.title):
                names.add(_norm_name(m.group()))
            for n in names:
                person_events.setdefault(n, []).append(event)

        for name, evts in person_events.items():
            if len(evts) < 2:
                continue
            sources = {e.source for e in evts}
            if len(sources) < 2:
                continue
            primary = evts[0]
            for related in evts[1:]:
                results.append(VerificationResult(
                    event_id=primary.id,
                    verifier="cross_reference",
                    is_duplicate=False,
                    related_event_ids=[related.id],
                    confidence=0.8,
                    details=f"Same person «{name}» in {related.source}: {related.title[:60]}",
                ))

        return results


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())
