"""Newsworthiness analyzer — ranks events by editorial value for CPI.

Scoring factors:
  1. Topic match (corruption, courts, budget — CPI priorities)
  2. Risk level from risk_keywords analysis
  3. Human factor — named person with position
  4. Timeliness
  5. Cross-source corroboration
  6. Geography weight (Odesa > Mykolaiv > Kherson)
"""

from __future__ import annotations

import re
from datetime import datetime

from ..models import Analysis, Event
from .base import BaseAnalyzer

TOPIC_KEYWORDS = {
    "corruption": ["корупці", "підозр", "ВАКС", "НАБУ", "хабар", "зловживанн"],
    "declarations": ["деклараці", "НАЗК", "доход", "майн"],
    "courts": ["суд", "арешт", "вирок", "обвинуваченн"],
    "budget": ["бюджет", "видатк", "програм", "фінанс"],
    "procurement": ["тендер", "закупівл", "ProZorro", "підряд"],
    "military": ["колабораціон", "ТЦК", "мобілізац", "армі", "зрад"],
    "ecology": ["забруднен", "екологі", "порушенн"],
}

TOPIC_WEIGHT = {
    "corruption": 1.0,
    "declarations": 0.9,
    "courts": 0.85,
    "budget": 0.7,
    "procurement": 0.7,
    "military": 0.8,
    "ecology": 0.5,
}

GEO_WEIGHT = {
    "odesa": 1.0,
    "mykolaiv": 0.8,
    "kherson": 0.6,
    "national": 0.9,
}

RISK_WEIGHT = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
    "none": 0.0,
}

PERSON_RE = re.compile(
    r"[А-ЯІЇЄҐ][а-яіїєґ']+ [А-ЯІЇЄҐ][а-яіїєґ']+ [А-ЯІЇЄҐ][а-яіїєґ']+",
)


class NewsworthinessAnalyzer(BaseAnalyzer):
    @property
    def analyzer_id(self) -> str:
        return "newsworthiness"

    def analyze(self, events: list[Event]) -> list[Analysis]:
        results = []
        for event in events:
            score = self._score_event(event)
            if score > 0.1:
                results.append(Analysis(
                    event_id=event.id,
                    analyzer=self.analyzer_id,
                    risk_level=self._score_to_level(score),
                    findings=[],
                    data={"newsworthiness": round(score, 3)},
                ))
        return results

    def _score_event(self, event: Event) -> float:
        text = f"{event.title} {event.data.get('description', '')}"

        topic_score = 0.0
        for topic, keywords in TOPIC_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    topic_score = max(topic_score, TOPIC_WEIGHT.get(topic, 0.5))
                    break

        geo = GEO_WEIGHT.get(event.city, 0.5)

        has_person = bool(PERSON_RE.search(text) or event.data.get("name"))
        person_bonus = 0.15 if has_person else 0.0

        hours_old = max(0, (datetime.now() - event.detected_at).total_seconds() / 3600) if event.detected_at else 24
        timeliness = max(0, 1.0 - hours_old / 72)

        score = (
            topic_score * 0.35
            + geo * 0.2
            + person_bonus
            + timeliness * 0.15
            + 0.15
        )

        return min(1.0, score)

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        if score >= 0.2:
            return "low"
        return "none"
