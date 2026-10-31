"""CSV report publisher: saves per-city reports in reports/ directory.

Ported from omr-monitor/monitor.py save_csv_report().
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

from ..config import PROJECT_ROOT
from ..models import Analysis, Draft, Event
from .base import BasePublisher

log = logging.getLogger("radawatch.publishers.csv")

REPORTS_DIR = PROJECT_ROOT / "reports"


class CsvReportPublisher(BasePublisher):
    @property
    def publisher_id(self) -> str:
        return "csv_report"

    def publish(self, draft: Draft, events: list[Event], analyses: list[Analysis]) -> bool:
        return True

    def save_city_report(self, city_id: str, events: list[Event], analyses: list[Analysis]) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        report_path = REPORTS_DIR / f"{city_id}_{today}.csv"

        decisions = [e for e in events if e.category == "decision"]
        commissions = [e for e in events if e.category == "commission"]
        risk_analyses = [a for a in analyses if a.analyzer == "risk_keywords" and a.findings]

        with open(report_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(["=== Засідання комісій ==="])
            writer.writerow(["Назва", "Дата", "Посилання"])
            for e in commissions:
                writer.writerow([e.title, e.data.get("date", ""), e.url])

            writer.writerow([])
            writer.writerow(["=== Рішення ==="])
            writer.writerow(["Назва", "Тип", "Посилання"])
            for d in decisions:
                writer.writerow([d.title, d.data.get("body", ""), d.url])

            writer.writerow([])
            writer.writerow(["=== Ризики ==="])
            writer.writerow(["Ключове слово", "Сума (грн)", "High-risk", "Контекст"])
            for a in risk_analyses:
                for f_ in a.findings:
                    is_high = "так" if f_.detail == "high-risk" else "ні"
                    writer.writerow([f_.keyword, f_.amount_uah or "", is_high, f_.context[:200]])

        log.info("[%s] CSV report saved: %s", city_id, report_path)
        return report_path
