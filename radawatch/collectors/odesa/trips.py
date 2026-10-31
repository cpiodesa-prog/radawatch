"""Collector: Odesa mayor business trip orders.

Ported from telegram-bot/trips.py.
Source: https://omr.gov.ua/ua/acts/mayor/ — filtered by "відрядженн".
"""

from __future__ import annotations

import re
from datetime import datetime

from ...models import Event
from ..base import BaseCollector
from .. import register_collector
from .pow_solver import get as pow_get
from .omr_parser import BASE, parse_rows

PATH = "/ua/acts/mayor/"
KEYWORD_RE = re.compile(r"відрядженн", re.I)


@register_collector
class OdesaTripsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "odesa.trips"

    def collect(self) -> list[Event]:
        html_text = pow_get(BASE + PATH)
        rows = parse_rows(html_text)
        events = []
        for r in rows:
            if not KEYWORD_RE.search(r["description"]):
                continue
            eid = self.make_event_id(r["url"])
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="odesa",
                category="trip",
                title=r["description"],
                url=r["url"],
                detected_at=datetime.now(),
                data={"number": r["number"], "date": r["date"], "description": r["description"]},
            ))
        return events
