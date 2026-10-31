"""AI-powered news/analytics drafter using Claude API.

Generates draft articles according to CPI editorial standards.
Disabled by default; requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os

from ..editorial.prompts import DRAFTER_SYSTEM_PROMPT
from ..editorial.rules import check_draft
from ..models import Analysis, Draft, Event, VerificationResult

log = logging.getLogger("radawatch.drafters.news_drafter")


class NewsDrafter:
    @property
    def drafter_id(self) -> str:
        return "news_drafter"

    def draft(
        self,
        events: list[Event],
        analyses: list[Analysis],
        verifications: list[VerificationResult],
    ) -> list[Draft]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.debug("ANTHROPIC_API_KEY not set — skipping AI drafting")
            return []

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            log.warning("anthropic package not installed — skipping AI drafting")
            return []

        high_risk = self._select_draftable(events, analyses)
        if not high_risk:
            return []

        drafts = []
        for event, risk in high_risk[:3]:
            try:
                draft = self._generate_draft(client, event, risk, analyses)
                if draft:
                    drafts.append(draft)
            except Exception as exc:
                log.warning("Draft generation failed for %s: %s", event.id, exc)

        return drafts

    def _select_draftable(self, events: list[Event], analyses: list[Analysis]) -> list[tuple[Event, str]]:
        risk_map = {}
        for a in analyses:
            if a.analyzer == "risk_keywords" and a.risk_level in ("medium", "high"):
                risk_map[a.event_id] = a.risk_level
            elif a.analyzer == "newsworthiness":
                score = a.data.get("newsworthiness", 0)
                if score >= 0.6 and a.event_id not in risk_map:
                    risk_map[a.event_id] = a.risk_level

        result = []
        for event in events:
            if event.id in risk_map:
                result.append((event, risk_map[event.id]))
        result.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x[1], 0), reverse=True)
        return result

    def _generate_draft(self, client, event: Event, risk: str, analyses: list[Analysis]) -> Draft | None:
        context_parts = [
            f"Подія: {event.title}",
            f"Місто: {event.city}",
            f"Категорія: {event.category}",
            f"Джерело: {event.source}",
            f"URL: {event.url}",
            f"Рівень ризику: {risk}",
        ]
        for key, val in event.data.items():
            if key not in ("raw_text", "dossier", "decision_analysis", "document_diff"):
                context_parts.append(f"{key}: {val}")

        event_analyses = [a for a in analyses if a.event_id == event.id]
        for a in event_analyses:
            if a.findings:
                for f in a.findings:
                    context_parts.append(f"[{a.analyzer}] {f.keyword}: {f.context}")

        prompt = (
            "Напиши новину за стандартами ЦПР.\n\n"
            + "\n".join(context_parts)
        )

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=DRAFTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = resp.content[0].text
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("AI drafter returned non-JSON for %s", event.id)
            return None

        draft = Draft(
            content_type="news",
            title=data.get("title", event.title),
            lede=data.get("lede", ""),
            body_html=data.get("body_html", ""),
            city=event.city,
            event_ids=[event.id],
            tags=data.get("tags", []),
            source_urls=data.get("source_urls", [event.url]),
            status="auto_draft",
        )

        score_result = check_draft(draft)
        draft.editorial_score = int(score_result.score)
        draft.editorial_issues = [
            {"severity": i.severity, "rule": i.rule, "message": i.message}
            for i in score_result.issues
        ]

        return draft
