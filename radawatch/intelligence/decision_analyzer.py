"""Decision analyzer — risk assessment and angle suggestion for council decisions.

Extends the basic risk_keywords analysis with:
- Subject extraction (land, lease, privatization + amounts)
- Contractor/recipient tracking across decisions
- Angle suggestion for journalists
"""

from __future__ import annotations

import logging
import re

from ..config import Config
from ..models import Analysis, Event
from ..state import StateManager
from ..utils.text import parse_uah_amount

log = logging.getLogger("radawatch.intelligence.decision_analyzer")

SUBJECT_PATTERNS = {
    "land": re.compile(r"земельн\w+\s+ділянк\w+", re.IGNORECASE),
    "lease": re.compile(r"оренд\w+", re.IGNORECASE),
    "privatization": re.compile(r"приватизац\w+", re.IGNORECASE),
    "construction": re.compile(r"будівництв\w+|реконструкц\w+", re.IGNORECASE),
    "communal": re.compile(r"комунальн\w+\s+(підприємств|власніст|майн)", re.IGNORECASE),
}

AREA_RE = re.compile(r"(\d[\d\s,.]+)\s*(га|гектар|м²|кв\.?\s*м)", re.IGNORECASE)


class DecisionAnalyzer:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state

    def process(self, events: list[Event], analyses: list[Analysis]) -> None:
        risk_events = {a.event_id for a in analyses if a.analyzer == "risk_keywords" and a.risk_level != "none"}

        for event in events:
            if event.id not in risk_events:
                continue
            if event.category not in ("decision",):
                continue

            enrichment = self._analyze_decision(event)
            if enrichment:
                event.data["decision_analysis"] = enrichment

    def _analyze_decision(self, event: Event) -> dict | None:
        text = event.data.get("raw_text") or event.title
        if not text:
            return None

        subjects = []
        for subj, pattern in SUBJECT_PATTERNS.items():
            if pattern.search(text):
                subjects.append(subj)

        amounts = []
        for match in re.finditer(r"[\d\s,.]+\s*(грн|гривень|тис|млн|млрд)", text, re.IGNORECASE):
            amount = parse_uah_amount(match.group())
            if amount and amount > 0:
                amounts.append(amount)

        areas = []
        for m in AREA_RE.finditer(text):
            areas.append(f"{m.group(1).strip()} {m.group(2)}")

        if not subjects and not amounts:
            return None

        angle = self._suggest_angle(subjects, amounts, areas)

        return {
            "subjects": subjects,
            "amounts_uah": amounts,
            "areas": areas,
            "suggested_angle": angle,
        }

    def _suggest_angle(self, subjects: list[str], amounts: list[float], areas: list[str]) -> str:
        parts = []
        if "land" in subjects and areas:
            parts.append(f"Земля: {', '.join(areas)}")
        if amounts:
            max_amount = max(amounts)
            if max_amount >= 10_000_000:
                parts.append(f"Сума: {max_amount:,.0f} грн — хто отримує, порівняти з ринком")
            else:
                parts.append(f"Сума: {max_amount:,.0f} грн")
        if "privatization" in subjects:
            parts.append("Приватизація — перевірити оцінку та покупця")
        if "communal" in subjects:
            parts.append("Комунальне підприємство — вплив на жителів")

        return "; ".join(parts) if parts else "Перевірити деталі рішення"
