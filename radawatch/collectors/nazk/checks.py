"""Collector: NAZK full checks (повні перевірки) — HTML scraping.

Ported from declaration-watcher/scripts/watch_checks.py.
Scrapes the public registry of NAZK full declaration checks.
"""

from __future__ import annotations

import csv
import html as htmllib
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests

from ...config import PROJECT_ROOT
from ...models import Event
from ..base import BaseCollector
from .. import register_collector

log = logging.getLogger("radawatch.nazk.checks")

PAGE_URL = "https://nazk.gov.ua/uk/category/povni-perevirky/"
PER_PAGE = 500
MAX_PAGES = 600
REGION_STEMS = ("одес", "миколаїв", "херсон")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
}


def _clean(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _norm(s: str) -> str:
    s = (s or "").lower().replace("'", "'").replace("ʼ", "'").replace("`", "'")
    return re.sub(r"\s+", " ", s).strip()


def _parse_table(page_html: str) -> list[dict]:
    cols = {}
    head = re.search(r"<thead>(.*?)</thead>", page_html, re.DOTALL | re.IGNORECASE)
    if head:
        ths = [_clean(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.DOTALL)]
        for i, t in enumerate(ths):
            tl = t.lower()
            if tl.startswith("піб"):
                cols["name"] = i
            elif tl.startswith("посада"):
                cols["post"] = i
            elif tl.startswith("категорія"):
                cols["category"] = i
            elif tl.startswith("звітний"):
                cols["period"] = i
            elif tl.startswith("статус"):
                cols["status"] = i
            elif tl.startswith("результат"):
                cols["result"] = i

    for key, idx in (("name", 0), ("post", 1), ("category", 2), ("period", 3), ("status", 4), ("result", 7)):
        cols.setdefault(key, idx)

    records = []
    for key, body in re.findall(r'<tr[^>]*data-key="([^"]+)"[^>]*>(.*?)</tr>',
                                page_html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.DOTALL | re.IGNORECASE)

        def cell(k):
            i = cols[k]
            return _clean(cells[i]) if i < len(cells) else ""

        link = ""
        for c in cells:
            hm = re.search(r'href="([^"]+)"', c)
            if hm:
                link = htmllib.unescape(hm.group(1))
                if link.startswith("/"):
                    link = "https://nazk.gov.ua" + link
                break

        name = cell("name")
        if not name:
            continue
        records.append({
            "key": key, "name": name, "post": cell("post"),
            "category": cell("category"), "period": cell("period"),
            "status": cell("status"), "result": cell("result"), "link": link,
        })
    return records


def _load_people_names() -> set[str]:
    path = PROJECT_ROOT / "data" / "people.csv"
    if not path.exists():
        return set()
    names = set()
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return names
    reader = csv.DictReader(lines)
    for row in reader:
        name = _norm(row.get("name", ""))
        if name:
            names.add(name)
    return names


def _is_relevant(rec: dict, people_names: set[str]) -> bool:
    n = _norm(rec["name"])
    if n in people_names:
        return True
    post = _norm(rec["post"])
    return any(stem in post for stem in REGION_STEMS)


@register_collector
class NazkChecksCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "nazk.checks"

    def collect(self) -> list[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)

        people_names = _load_people_names()
        all_records = []

        page_no = 1
        while page_no <= MAX_PAGES:
            try:
                resp = session.get(PAGE_URL, params={"f-page": page_no, "f-per-page": PER_PAGE}, timeout=45)
                if resp.status_code != 200:
                    break
                records = _parse_table(resp.text)
                if not records:
                    break
                all_records.extend(records)
                if len(records) < PER_PAGE:
                    break
                page_no += 1
                time.sleep(0.3)
            except Exception as exc:
                log.warning("Failed to fetch checks page %d: %s", page_no, exc)
                break

        log.info("Fetched %d NAZK check records", len(all_records))

        events = []
        for rec in all_records:
            if not _is_relevant(rec, people_names):
                continue

            eid = self.make_event_id(rec["key"])
            if self.state.is_seen(eid):
                continue

            events.append(Event(
                id=eid,
                source=self.source_id,
                city="national",
                category="nazk_check",
                title=f"Перевірка НАЗК: {rec['name']}",
                url=rec.get("link") or PAGE_URL,
                detected_at=datetime.now(),
                data={
                    "name": rec["name"],
                    "post": rec["post"],
                    "category": rec["category"],
                    "period": rec["period"],
                    "status": rec["status"],
                    "result": rec["result"],
                },
            ))

        log.info("NAZK checks: %d new relevant records", len(events))
        return events
