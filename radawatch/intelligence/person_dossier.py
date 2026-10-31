"""Automatic person dossier builder.

Trigger: personnel event (appointment/dismissal) or new declaration.
Cross-references: NAZK API for declarations, checks; state for prior events.
"""

from __future__ import annotations

import logging
import time

from ..collectors.nazk._api import make_session, fetch_list_since, api_get_full
from ..collectors.nazk._verification import full_name_of, name_matches, split_name, step1
from ..config import Config
from ..models import Analysis, Event
from ..state import StateManager
from ..utils.text import esc

log = logging.getLogger("radawatch.intelligence.dossier")


class PersonDossierBuilder:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state

    def process(self, events: list[Event], analyses: list[Analysis]) -> None:
        for event in events:
            if event.category in ("personnel", "declaration"):
                name = event.data.get("name") or event.data.get("person_name")
                if name:
                    dossier = self._build_dossier(name, event)
                    if dossier:
                        event.data["dossier"] = dossier

    def _build_dossier(self, name: str, trigger_event: Event) -> dict | None:
        last, first, patronymic = split_name(name)
        dossier = {
            "name": name,
            "trigger": trigger_event.title,
            "declarations": [],
            "checks": [],
            "prior_events": [],
        }

        dossier["declarations"] = self._find_declarations(name, last, first, patronymic)
        dossier["prior_events"] = self._find_prior_events(name)

        if not dossier["declarations"] and not dossier["prior_events"]:
            return None

        return dossier

    def _find_declarations(self, name: str, last: str, first: str, patronymic: str) -> list[dict]:
        try:
            session = make_session()
            since_ts = time.time() - 365 * 24 * 3600
            candidates = fetch_list_since(session, {"query": name}, since_ts, max_pages=2)
        except Exception as exc:
            log.warning("Failed to fetch declarations for %s: %s", name, exc)
            return []

        results = []
        for c in candidates:
            doc_id = c.get("id") or c.get("uuid")
            if not doc_id:
                continue
            doc = api_get_full(session, doc_id)
            if not doc:
                continue
            if not name_matches(doc, last, first, patronymic):
                continue

            s1 = step1(doc)
            results.append({
                "doc_id": doc_id,
                "year": doc.get("declaration_year"),
                "type": doc.get("declaration_type"),
                "workplace": s1.get("workPlace", ""),
                "workpost": s1.get("workPost", ""),
                "url": f"https://public.nazk.gov.ua/documents/{doc_id}",
            })
            time.sleep(0.3)

            if len(results) >= 3:
                break

        return results

    def _find_prior_events(self, name: str) -> list[dict]:
        norm_name = name.lower().strip()
        prior = []
        for person_name, event_ids in self.state.data.get("person_index", {}).items():
            if norm_name in person_name.lower():
                for eid in event_ids[-5:]:
                    prior.append({"event_id": eid, "matched_name": person_name})
        return prior


def format_dossier_telegram(dossier: dict) -> str:
    lines = [f"👤 <b>Досьє: {esc(dossier['name'])}</b>"]

    if dossier.get("trigger"):
        lines.append(f"   {esc(dossier['trigger'])}")

    for decl in dossier.get("declarations", []):
        year = decl.get("year", "?")
        dtype = decl.get("type", "?")
        url = decl.get("url", "")
        lines.append(f"\n   📋 Декларація {year}: тип {dtype}")
        if decl.get("workpost"):
            lines.append(f"      → {esc(decl['workpost'])}")
        if url:
            lines.append(f"      → {url}")

    for prior in dossier.get("prior_events", []):
        lines.append(f"\n   ⚠️ Раніше в моніторингу: {esc(prior.get('event_id', ''))}")

    return "\n".join(lines)
