"""Cross-source deduplication.

Detects the same event collected from multiple sources.
Example: a decision found by both odesa.decisions and odesa.commissions.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..config import Config
from ..models import Analysis, Event, VerificationResult
from ..state import StateManager
from .base import BaseVerifier

SIMILARITY_THRESHOLD = 0.85


class DedupVerifier(BaseVerifier):
    def __init__(self, config: Config, state: StateManager):
        super().__init__(config, state)

    @property
    def verifier_id(self) -> str:
        return "dedup"

    def verify(self, events: list[Event], analyses: list[Analysis]) -> list[VerificationResult]:
        results = []
        seen_titles: list[tuple[str, Event]] = []

        for event in events:
            norm = _normalize(event.title)
            for prev_norm, prev_event in seen_titles:
                if prev_event.city != event.city:
                    continue
                if prev_event.source == event.source:
                    continue
                ratio = SequenceMatcher(None, norm, prev_norm).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    results.append(VerificationResult(
                        event_id=event.id,
                        verifier="dedup",
                        is_duplicate=True,
                        duplicate_of=prev_event.id,
                        confidence=round(ratio, 3),
                        details=f"Duplicate of {prev_event.source}: {prev_event.title[:60]}",
                    ))
                    break
            else:
                seen_titles.append((norm, event))

        return results


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
