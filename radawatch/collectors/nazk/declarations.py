"""Collector: NAZK declarations — by people list and by institution EDRPOU.

Ported from declaration-watcher/scripts/watch.py.
Two modes:
  A. People: searches by full name, verifies via ПІБ + region/role
  B. Institutions: searches by workPlaceEdrpou (catches new declarants)
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...config import Config, PROJECT_ROOT
from ...models import Event
from ...state import StateManager
from ..base import BaseCollector
from .. import register_collector
from ._api import make_session, fetch_list_since, api_get_full
from ._verification import (
    full_name_of, split_name, name_matches,
    region_matches_workplace, position_contains, step1,
)

log = logging.getLogger("radawatch.nazk.declarations")

REQUEST_DELAY = 0.2

DECLARATION_TYPE_LABELS = {
    0: "Повідомлення про суттєві зміни",
    1: "Щорічна",
    2: "При звільненні",
    3: "Щорічна (після звільнення)",
    4: "Кандидата на посаду",
}

PUBLIC_VIEW_URL = "https://public.nazk.gov.ua/documents/{doc_id}"
API_BASE_URL = "https://public-api.nazk.gov.ua/v2"


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return rows
    reader = csv.DictReader(lines)
    for row in reader:
        if any((v or "").strip() for v in row.values()):
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


@register_collector
class NazkDeclarationsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "nazk.declarations"

    def collect(self) -> list[Event]:
        nazk_cfg = self.config.get("nazk", {})
        api_base = nazk_cfg.get("api_base_url", API_BASE_URL)

        people_path = PROJECT_ROOT / "data" / "people.csv"
        institutions_path = PROJECT_ROOT / "data" / "institutions.csv"

        people = _load_csv(people_path)
        institutions = _load_csv(institutions_path)

        if not people and not institutions:
            log.info("No people or institutions to watch")
            return []

        session = make_session()
        since_ts = time.time() - 24 * 3600  # last 24 hours by default

        events = []
        events.extend(self._collect_people(session, people, since_ts, api_base))
        events.extend(self._collect_institutions(session, institutions, since_ts, api_base))

        log.info("NAZK declarations: %d new from %d people + %d institutions",
                 len(events), len(people), len(institutions))
        return events

    def _collect_people(self, session, people: list[dict], since_ts: float, api_base: str) -> list[Event]:
        total = len(people)
        events = []

        for i, person in enumerate(people):
            full_name = person.get("name")
            if not full_name:
                continue

            last, first, patronymic = split_name(full_name)
            candidates = fetch_list_since(session, {"query": full_name}, since_ts, base_url=api_base, max_pages=1)

            for c in candidates:
                doc_id = c.get("id") or c.get("uuid")
                if not doc_id:
                    continue
                eid = self.make_event_id(doc_id)
                if self.state.is_seen(eid):
                    continue

                doc = api_get_full(session, doc_id, base_url=api_base)
                if not doc:
                    continue
                time.sleep(REQUEST_DELAY)

                if not name_matches(doc, last, first, patronymic):
                    self.state.mark_seen(eid)
                    continue

                role_lower = (person.get("role") or "").lower()
                if "народний депутат" in role_lower:
                    if not position_contains(doc, "народний депутат"):
                        self.state.mark_seen(eid)
                        continue
                elif not region_matches_workplace(doc, person.get("region")):
                    self.state.mark_seen(eid)
                    continue

                events.append(self._make_event(doc, doc_id, f"зі списку: {full_name}"))

            if (i + 1) % 50 == 0:
                log.info("  progress: %d/%d checked, %d found", i + 1, total, len(events))

        return events

    def _collect_institutions(self, session, institutions: list[dict], since_ts: float, api_base: str) -> list[Event]:
        events = []
        for inst in institutions:
            edrpou = inst.get("edrpou")
            if not edrpou:
                continue
            label = f"{inst.get('name', '?')} ({inst.get('region', '')})"

            candidates = fetch_list_since(session, {"workPlaceEdrpou": edrpou}, since_ts, base_url=api_base)

            for c in candidates:
                doc_id = c.get("id") or c.get("uuid")
                if not doc_id:
                    continue
                eid = self.make_event_id(doc_id)
                if self.state.is_seen(eid):
                    continue

                doc = api_get_full(session, doc_id, base_url=api_base)
                if not doc:
                    continue
                time.sleep(REQUEST_DELAY)

                events.append(self._make_event(doc, doc_id, f"установа: {label}"))

        return events

    def _make_event(self, doc: dict, doc_id: str, matched_label: str) -> Event:
        s1 = step1(doc)
        name = full_name_of(doc) or "(ПІБ не розпізнано)"
        workplace = s1.get("workPlace") or ""
        workpost = s1.get("workPost") or ""
        decl_year = doc.get("declaration_year", "?")
        decl_type_code = doc.get("declaration_type")
        decl_type = DECLARATION_TYPE_LABELS.get(decl_type_code, f"код {decl_type_code}")
        doc_url = PUBLIC_VIEW_URL.format(doc_id=doc_id)

        return Event(
            id=self.make_event_id(doc_id),
            source=self.source_id,
            city="national",
            category="declaration",
            title=f"{name} — {decl_type}, {decl_year}",
            url=doc_url,
            detected_at=datetime.now(),
            data={
                "doc_id": doc_id,
                "name": name,
                "workplace": workplace,
                "workpost": workpost,
                "declaration_type": decl_type,
                "declaration_year": decl_year,
                "matched_label": matched_label,
            },
        )
