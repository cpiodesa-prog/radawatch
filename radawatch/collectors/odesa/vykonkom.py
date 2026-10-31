"""Collector: Odesa executive committee (vykonkom) meeting announcements.

Ported from telegram-bot/vykonkom_announce.py.
Source: https://omr.gov.ua/ua/announce/ — announcement feed with card layout,
filtered by "виконком|виконавч* коміте" keyword.
"""

from __future__ import annotations

import re
from datetime import datetime

from ...models import Event
from ..base import BaseCollector
from .. import register_collector
from .pow_solver import get as pow_get
from .omr_parser import BASE, clean

PATH = "/ua/announce/"

CARD_RE = re.compile(
    r'<div class="post[^"]*">.*?'
    r'<time class="date" datetime="(?P<date>[^"]*)">.*?'
    r'<strong class="title"><a href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a></strong>.*?'
    r'<div class="img-box">.*?</div>\s*'
    r'<p>(?P<desc>.*?)</p>',
    re.S,
)

KEYWORD_RE = re.compile(r"виконком|виконавч\w* коміте", re.I)


@register_collector
class OdesaVykonkomCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "odesa.vykonkom"

    def collect(self) -> list[Event]:
        html_text = pow_get(BASE + PATH)
        rows = self._parse(html_text)
        events = []
        for r in rows:
            if not (KEYWORD_RE.search(r["title"]) or KEYWORD_RE.search(r["description"])):
                continue
            eid = self.make_event_id(r["url"])
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="odesa",
                category="vykonkom",
                title=r["title"],
                url=r["url"],
                detected_at=datetime.now(),
                data={"date": r["date"], "title": r["title"], "description": r["description"]},
            ))
        return events

    @staticmethod
    def _parse(html_text: str) -> list[dict]:
        out = []
        for m in CARD_RE.finditer(html_text):
            link = m.group("link")
            if link.startswith("/"):
                link = BASE + link
            out.append({
                "date": clean(m.group("date")),
                "title": clean(m.group("title")),
                "description": clean(m.group("desc")),
                "url": link,
            })
        return out
