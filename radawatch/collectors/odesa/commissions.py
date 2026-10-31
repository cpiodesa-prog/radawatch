"""Collector: Odesa city council commission meetings.

Ported from telegram-bot/commissions.py.
Source: https://deputat.omr.gov.ua/commissions/schedule/ — no PoW protection.
Uses BeautifulSoup for HTML table parsing.
"""

from __future__ import annotations

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ...models import Event
from ..base import BaseCollector
from .. import register_collector

URL = "https://deputat.omr.gov.ua/commissions/schedule/"
DEPUTAT_BASE = "https://deputat.omr.gov.ua"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; radawatch/2.0)"}


@register_collector
class OdesaCommissionsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "odesa.commissions"

    def collect(self) -> list[Event]:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        rows = self._parse(resp.text)
        events = []
        for r in rows:
            key = f"{r.get('commission_url', '')}|{r['date']}|{r['time']}"
            eid = self.make_event_id(key)
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="odesa",
                category="commission",
                title=r["commission"],
                url=r.get("commission_url") or URL,
                detected_at=datetime.now(),
                data=r,
            ))
        return events

    @staticmethod
    def _parse(html_text: str) -> list[dict]:
        soup = BeautifulSoup(html_text, "html.parser")
        table = soup.find("table")
        rows = []
        if not table:
            return rows
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            dt_cell, comm_cell, stream_cell, agenda_cell, protocol_cell, posted_cell = cells[:6]

            dt_text = dt_cell.get_text(" ", strip=True)
            m = re.match(r"(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})", dt_text)
            date_str, time_str = (m.group(1), m.group(2)) if m else (dt_text, "")
            location = dt_text[m.end():].strip() if m else ""

            comm_link = comm_cell.find("a")
            commission = comm_link.get_text(strip=True) if comm_link else comm_cell.get_text(strip=True)
            commission_url = comm_link["href"] if comm_link and comm_link.has_attr("href") else None
            if commission_url and commission_url.startswith("/"):
                commission_url = DEPUTAT_BASE + commission_url

            stream_link = stream_cell.find("a")
            stream_url = stream_link["href"] if stream_link and stream_link.has_attr("href") else None

            agenda_link = agenda_cell.find("a")
            agenda_url = agenda_link["href"] if agenda_link and agenda_link.has_attr("href") else None
            if agenda_url and agenda_url.startswith("/"):
                agenda_url = DEPUTAT_BASE + agenda_url

            rows.append({
                "date": date_str,
                "time": time_str,
                "location": location,
                "commission": commission,
                "commission_url": commission_url,
                "stream_url": stream_url,
                "agenda_url": agenda_url,
            })
        return rows
