"""Automatic person dossier builder.

Trigger: personnel event (appointment/dismissal) or new declaration.
Cross-references: NAZK API for declarations, checks; state for prior events.
"""

from __future__ import annotations

import logging
import re
import time

from ..collectors.nazk._api import make_session, fetch_list_since, api_get_full, RateLimitError
from ..collectors.nazk._verification import full_name_of, name_matches, split_name, step1
from ..config import Config
from ..models import Analysis, Event
from ..state import StateManager
from ..utils.text import esc

log = logging.getLogger("radawatch.intelligence.dossier")

NAME_RE = re.compile(
    r"(?:призначенн\w*|звільненн\w*|переведенн\w*|покладенн\w*)\s+"
    r"((?:[А-ЯІЇЄҐ][а-яіїєґ'`ʼ]+\s+){2,3})",
    re.IGNORECASE,
)


def extract_person_name(event: Event) -> str | None:
    name = event.data.get("name") or event.data.get("person_name")
    if name:
        return name.strip()
    for field in ("description", "title"):
        text = event.data.get(field) or ""
        m = NAME_RE.search(text)
        if m:
            return m.group(1).strip()
    if event.title:
        m = NAME_RE.search(event.title)
        if m:
            return m.group(1).strip()
    return None


class PersonDossierBuilder:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state

    def process(self, events: list[Event], analyses: list[Analysis]) -> None:
        for event in events:
            if event.category not in ("personnel", "declaration"):
                continue
            name = extract_person_name(event)
            if not name:
                continue
            event.data["person_name"] = name
            dossier = self._build_dossier(name, event)
            if dossier:
                event.data["dossier"] = dossier
                log.info("Built dossier for %s (%d decl, %d prior)",
                         name, len(dossier["declarations"]), len(dossier["prior_events"]))

    def _build_dossier(self, name: str, trigger_event: Event) -> dict | None:
        last, first, patronymic = split_name(name)
        dossier = {
            "name": name,
            "trigger": trigger_event.title,
            "trigger_url": trigger_event.url,
            "declarations": [],
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
        except RateLimitError:
            log.warning("NAZK rate limit while building dossier for %s", name)
            return []
        except Exception as exc:
            log.warning("Failed to fetch declarations for %s: %s", name, exc)
            return []

        results = []
        for c in candidates:
            doc_id = c.get("id") or c.get("uuid")
            if not doc_id:
                continue
            try:
                doc = api_get_full(session, doc_id)
            except RateLimitError:
                log.warning("NAZK rate limit on doc %s", doc_id)
                break
            except Exception:
                continue
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
            time.sleep(0.5)

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
        lines.append(f"   📎 {esc(dossier['trigger'])}")
    if dossier.get("trigger_url"):
        lines.append(f"   🔗 {dossier['trigger_url']}")

    if dossier.get("declarations"):
        lines.append("")
        for decl in dossier["declarations"]:
            year = decl.get("year", "?")
            dtype = decl.get("type", "?")
            url = decl.get("url", "")
            lines.append(f"   📋 Декларація {year} (тип {dtype})")
            if decl.get("workpost"):
                lines.append(f"      → {esc(decl['workpost'])}")
            if decl.get("workplace"):
                lines.append(f"      → {esc(decl['workplace'])}")
            if url:
                lines.append(f"      🔗 {url}")

    if dossier.get("prior_events"):
        lines.append("")
        lines.append("   ⚠️ <b>Раніше в моніторингу:</b>")
        for prior in dossier["prior_events"]:
            lines.append(f"      • {esc(prior.get('event_id', ''))}")

    return "\n".join(lines)


def format_document_diff_telegram(event: Event) -> str | None:
    diff = event.data.get("document_diff")
    if not diff or not diff.get("is_significant"):
        return None
    changes = diff.get("changes", [])
    lines = [
        f"📄 <b>Зміна документа</b>",
        f"   {esc(event.title)}",
        f"   Версія: {diff.get('prev_version', '?')} → {diff.get('new_version', '?')}",
    ]
    for ch in changes:
        lines.append(f"   ⚠️ {esc(ch)}")
    if event.url:
        lines.append(f"   🔗 {event.url}")
    return "\n".join(lines)


def format_decision_analysis_telegram(event: Event) -> str | None:
    analysis = event.data.get("decision_analysis")
    if not analysis:
        return None
    subj_labels = {"land": "земля", "lease": "оренда", "privatization": "приватизація",
                   "construction": "будівництво", "communal": "комунальне"}
    parts = []
    if analysis.get("subjects"):
        parts.append("Теми: " + ", ".join(subj_labels.get(s, s) for s in analysis["subjects"]))
    if analysis.get("amounts_uah"):
        max_amt = max(analysis["amounts_uah"])
        parts.append(f"Сума: {max_amt:,.0f} грн")
    if analysis.get("areas"):
        parts.append("Площа: " + ", ".join(analysis["areas"]))
    if analysis.get("suggested_angle"):
        parts.append(f"💡 {analysis['suggested_angle']}")

    if not parts:
        return None

    lines = [f"🔍 <b>Аналіз рішення</b>", f"   {esc(event.title)}"]
    for p in parts:
        lines.append(f"   {esc(p)}")
    if event.url:
        lines.append(f"   🔗 {event.url}")
    return "\n".join(lines)
