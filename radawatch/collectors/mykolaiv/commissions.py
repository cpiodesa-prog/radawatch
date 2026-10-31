"""Collector: Mykolaiv city council commission meetings.

Ported from telegram-bot/mk_commissions.py.
Source: https://mkrada.gov.ua/content/grafik-zasidan12.html — monthly schedule table.
"""

from __future__ import annotations

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ...models import Event
from ..base import BaseCollector
from .. import register_collector

BASE = "https://mkrada.gov.ua"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; radawatch/2.0)"}
SCHEDULE_URL = f"{BASE}/content/grafik-zasidan12.html"
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


@register_collector
class MykolaivCommissionsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "mykolaiv.commissions"

    def collect(self) -> list[Event]:
        resp = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        rows = self._parse(resp.content)
        events = []
        for r in rows:
            key = f"{r['commission']}|{r['date']}|{r['time']}"
            eid = self.make_event_id(key)
            if self.state.is_seen(eid):
                continue
            events.append(Event(
                id=eid,
                source=self.source_id,
                city="mykolaiv",
                category="commission",
                title=r["commission"],
                url=r.get("agenda_url") or SCHEDULE_URL,
                detected_at=datetime.now(),
                data=r,
            ))
        return events

    @staticmethod
    def _parse(html_bytes: bytes) -> list[dict]:
        soup = BeautifulSoup(html_bytes, "html.parser")
        table = soup.find("table")
        if not table:
            return []
        out = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            name_cell = cells[0]
            full_text = name_cell.get_text("\n", strip=True)
            if not full_text or full_text.lower().startswith("назва"):
                continue

            name = full_text.split("Посилання")[0].strip().rstrip(":").strip()
            if not name:
                continue

            a = name_cell.find("a", href=True)
            agenda_url = None
            if a:
                href = a["href"]
                agenda_url = href if href.startswith("http") else BASE + href

            date_text = cells[1].get_text(strip=True)
            m = DATE_RE.search(date_text)
            if not m:
                continue
            date_str = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

            time_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            out.append({
                "commission": name,
                "date": date_str,
                "time": time_text,
                "agenda_url": agenda_url or SCHEDULE_URL,
            })
        return out
