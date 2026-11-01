"""Collector: Odesa council and executive committee decisions.

Ported from omr-monitor/parsers/odesa.py.
Scans decision pages for .docx/.pdf links (project texts for risk analysis).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ...models import Event, FileRef
from ..base import BaseCollector
from .. import register_collector
from . import pow_solver

log = logging.getLogger("radawatch.odesa.decisions")


def _make_id(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts if p)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _guess_file_type(url: str) -> Optional[str]:
    lowered = url.lower().split("?")[0]
    if lowered.endswith((".docx", ".doc")):
        return "docx"
    if lowered.endswith(".pdf"):
        return "pdf"
    return None


@register_collector
class OdesaDecisionsCollector(BaseCollector):
    @property
    def source_id(self) -> str:
        return "odesa.decisions"

    def collect(self) -> list[Event]:
        city_cfg = self.config.cities.get("odesa", {})
        events = []

        for url_key, body in [("decisions_exec_url", "executive"), ("decisions_council_url", "council")]:
            url = city_cfg.get(url_key)
            if not url:
                continue
            events.extend(self._collect_from_page(url, body))

        return events

    def _collect_from_page(self, url: str, body: str) -> list[Event]:
        try:
            html = pow_solver.get(url)
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", url, exc)
            return []

        soup = BeautifulSoup(html, "html.parser")
        events = []

        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]
            file_type = _guess_file_type(href)
            if file_type is None:
                continue

            title = link_tag.get_text(strip=True) or href.rsplit("/", 1)[-1]
            container_text = link_tag.parent.get_text(" ", strip=True) if link_tag.parent else title
            file_url = urljoin(url, href)
            decision_id = _make_id("odesa", title, file_url)

            eid = self.make_event_id(decision_id)
            if self.state.is_seen(eid):
                continue

            events.append(Event(
                id=eid,
                source=self.source_id,
                city="odesa",
                category="decision",
                title=title,
                url=file_url,
                detected_at=datetime.now(),
                data={"body": body, "file_type": file_type, "container_text": container_text},
                files=[FileRef(path=file_url, mime_type=f"application/{file_type}")],
            ))

        log.info("Odesa decisions (%s): %d new", body, len(events))
        return events
