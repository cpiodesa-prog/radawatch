"""Optional AI factcheck using Claude API.

Disabled by default. Requires ANTHROPIC_API_KEY in environment.
Only runs on medium+ risk events.
"""

from __future__ import annotations

import json
import logging
import os

from ..config import Config
from ..models import Analysis, Event, VerificationResult
from ..state import StateManager
from ..editorial.prompts import FACTCHECK_SYSTEM_PROMPT
from .base import BaseVerifier

log = logging.getLogger("radawatch.verifiers.ai_factcheck")


class AiFactcheckVerifier(BaseVerifier):
    def __init__(self, config: Config, state: StateManager):
        super().__init__(config, state)

    @property
    def verifier_id(self) -> str:
        return "ai_factcheck"

    def verify(self, events: list[Event], analyses: list[Analysis]) -> list[VerificationResult]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.debug("ANTHROPIC_API_KEY not set — skipping AI factcheck")
            return []

        risk_events = self._filter_risky(events, analyses)
        if not risk_events:
            return []

        results = []
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            log.warning("anthropic package not installed — skipping AI factcheck")
            return []

        for event, risk_level in risk_events:
            try:
                result = self._check_event(client, event, risk_level)
                if result:
                    results.append(result)
            except Exception as exc:
                log.warning("AI factcheck failed for %s: %s", event.id, exc)

        return results

    def _filter_risky(self, events: list[Event], analyses: list[Analysis]) -> list[tuple[Event, str]]:
        risk_map = {}
        for a in analyses:
            if a.analyzer == "risk_keywords" and a.risk_level in ("medium", "high"):
                risk_map[a.event_id] = a.risk_level

        result = []
        for event in events:
            if event.id in risk_map:
                result.append((event, risk_map[event.id]))
        return result

    def _check_event(self, client, event: Event, risk_level: str) -> VerificationResult | None:
        prompt = (
            f"Подія: {event.title}\n"
            f"Джерело: {event.source}\n"
            f"Місто: {event.city}\n"
            f"Рівень ризику: {risk_level}\n"
            f"URL: {event.url}\n"
            f"Дані: {json.dumps(event.data, ensure_ascii=False, default=str)}"
        )

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=FACTCHECK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = resp.content[0].text
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("AI factcheck returned non-JSON for %s", event.id)
            return None

        return VerificationResult(
            event_id=event.id,
            verifier="ai_factcheck",
            is_duplicate=False,
            confidence=data.get("confidence", 0.5),
            details="; ".join(data.get("issues", [])) or data.get("context", ""),
        )
