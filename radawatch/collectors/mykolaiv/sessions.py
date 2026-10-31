"""Collector: Mykolaiv city council session convocations.

Ported from telegram-bot/mk_sessions.py.
Source: mkrada.gov.ua mayor orders (category 4), filtered by "скликанн".
"""

from __future__ import annotations

import re
from datetime import datetime

from ...models import Event
from ..base import BaseCollector
from .. import register_collector
from .mkrada_parser import fetch_latest, CATEGORY_MAYOR

KEYWORD_RE = re.compile(r"скликанн", re.I)


@register_collector
class MykolaivSessionsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "mykolaiv.sessions"

    def collect(self) -> list[Event]:
        rows = fetch_latest(CATEGORY_MAYOR)
        events = []
        for r in rows:
            if not KEYWORD_RE.search(r["description"] or ""):
                continue
            eid = self.make_event_id(r["url"])
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="mykolaiv",
                category="session",
                title=r["description"],
                url=r["url"],
                detected_at=datetime.now(),
                data={"number": r["number"], "date": r["date"], "description": r["description"]},
            ))
        return events
