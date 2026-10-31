"""Collector: Odesa Military Administration (OMVA) orders.

Ported from telegram-bot/omva.py.
Source: https://omr.gov.ua/ua/acts/omva/ — all orders, no keyword filter.
"""

from __future__ import annotations

from datetime import datetime

from ...models import Event
from ..base import BaseCollector
from .. import register_collector
from .pow_solver import get as pow_get
from .omr_parser import BASE, parse_rows

PATH = "/ua/acts/omva/"


@register_collector
class OdesaOmvaCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "odesa.omva"

    def collect(self) -> list[Event]:
        html_text = pow_get(BASE + PATH)
        rows = parse_rows(html_text)
        events = []
        for r in rows:
            eid = self.make_event_id(r["url"])
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="odesa",
                category="omva",
                title=r["description"],
                url=r["url"],
                detected_at=datetime.now(),
                data={"number": r["number"], "date": r["date"], "description": r["description"]},
            ))
        return events
