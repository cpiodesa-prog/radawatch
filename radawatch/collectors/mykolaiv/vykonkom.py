"""Collector: Mykolaiv executive committee meeting announcements.

Ported from telegram-bot/mk_vykonkom_announce.py.
Source: mkrada.gov.ua calendar, filtered by vykonkom keywords,
with agenda URLs from the agendas page.
"""

from __future__ import annotations

import re
from datetime import datetime

from ...models import Event
from ..base import BaseCollector
from .. import register_collector
from .mk_calendar import fetch_announcements
from .mk_agendas import fetch_vykonkom_agendas, AGENDA_LIST_URL

KEYWORD_RE = re.compile(r"виконав\w*\s+коміт|засіданн\w*\s+виконком", re.I)


@register_collector
class MykolaivVykonkomCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "mykolaiv.vykonkom"

    def collect(self) -> list[Event]:
        calendar_events = fetch_announcements()
        agendas = None
        events = []

        for e in calendar_events:
            if not KEYWORD_RE.search(e["text"]):
                continue

            stream_url = None
            generic_agenda_link = None
            for link in e["links"]:
                if "youtube.com" in link:
                    stream_url = link
                elif "poryadki-denni-zasidan-vikonkomu" in link:
                    generic_agenda_link = link

            agenda_url = None
            if e["date_str"]:
                if agendas is None:
                    agendas = fetch_vykonkom_agendas()
                agenda_url = agendas.get(e["date_str"])
            if not agenda_url:
                agenda_url = generic_agenda_link or AGENDA_LIST_URL

            key = f"{e['date_str'] or '?'}|{e['time'] or ''}"
            eid = self.make_event_id(key)
            if self.state.is_seen(eid):
                continue

            events.append(Event(
                id=eid,
                source=self.source_id,
                city="mykolaiv",
                category="vykonkom",
                title=f"Засідання виконкому {e['date_str'] or '?'}",
                url=agenda_url,
                detected_at=datetime.now(),
                data={
                    "date": e["date_str"] or "?",
                    "time": e["time"] or "",
                    "text": e["text"],
                    "agenda_url": agenda_url,
                    "stream_url": stream_url,
                },
            ))
        return events
