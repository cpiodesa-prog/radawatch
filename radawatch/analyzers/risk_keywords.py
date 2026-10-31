"""Risk keywords analyzer: scans decision document texts for sensitive keywords and monetary amounts.

Ported from omr-monitor/analyzers/risk_keywords.py.
Downloads .docx/.pdf files referenced in decision events, extracts text,
and searches for risk keywords with ±2 sentence context.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import requests

from ..config import Config
from ..models import Analysis, Event, Finding
from ..utils.text import parse_uah_amount
from .base import BaseAnalyzer

log = logging.getLogger("radawatch.analyzers.risk_keywords")

RISK_KEYWORDS = [
    "земля",
    "земельна ділянка",
    "оренда",
    "концесія",
    "закупівля",
    "комунальна власність",
    "субвенція",
    "передача",
    "відчуження",
    "приватизація",
    "безоплатна передача",
    "розірвання договору",
]

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class RiskKeywordsAnalyzer(BaseAnalyzer):
    @property
    def analyzer_id(self) -> str:
        return "risk_keywords"

    def analyze(self, events: list[Event]) -> list[Analysis]:
        results = []
        decision_events = [e for e in events if e.category == "decision" and e.files]

        for event in decision_events:
            file_ref = event.files[0]
            file_type = event.data.get("file_type")
            if not file_type:
                continue

            text = self._download_and_extract(file_ref.path, file_type)
            if not text:
                continue

            city_cfg = self.config.cities.get(event.city, {})
            threshold = city_cfg.get("risk_threshold_uah", 10_000_000)
            findings = self._find_risks(text, threshold)

            if findings:
                max_amount = max((f.amount_uah or 0) for f in findings)
                has_high = any(f.amount_uah and f.amount_uah >= threshold for f in findings)
                risk_level = "high" if has_high else ("medium" if max_amount > 0 else "low")
            else:
                risk_level = "none"

            results.append(Analysis(
                event_id=event.id,
                analyzer=self.analyzer_id,
                risk_level=risk_level,
                findings=findings,
            ))

        log.info("Analyzed %d decisions, found risks in %d",
                 len(decision_events), sum(1 for a in results if a.risk_level != "none"))
        return results

    def _find_risks(self, text: str, threshold: float) -> list[Finding]:
        sentences = SENTENCE_SPLIT_RE.split(text)
        findings = []

        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            matched_keywords = [kw for kw in RISK_KEYWORDS if kw in lowered]
            if not matched_keywords:
                continue

            context_start = max(0, index - 2)
            context_end = min(len(sentences), index + 3)
            context = " ".join(sentences[context_start:context_end]).strip()

            amount = parse_uah_amount(context)

            for keyword in matched_keywords:
                findings.append(Finding(
                    keyword=keyword,
                    context=context[:500],
                    amount_uah=amount,
                    detail=f"high-risk" if (amount and amount >= threshold) else "",
                ))

        return findings

    @staticmethod
    def _download_and_extract(url: str, file_type: str) -> Optional[str]:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Failed to download %s: %s", url, exc)
            return None

        suffix = f".{file_type}"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(resp.content)
        tmp.close()
        tmp_path = Path(tmp.name)

        try:
            from ..utils.doc_extract import extract_text, docx_to_text
            if file_type == "docx":
                return docx_to_text(resp.content)
            return extract_text(tmp_path)
        except Exception as exc:
            log.warning("Failed to extract text from %s: %s", url, exc)
            return None
        finally:
            tmp_path.unlink(missing_ok=True)
