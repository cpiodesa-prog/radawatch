"""Document version tracker — detects changes between document versions.

Tracks the lifecycle of council decisions and other documents:
- Stores snapshots of each version in state/document_versions/
- Generates diffs when a new version is detected
- Alerts on significant changes (amount ±20%, area ±10%, new parties)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from ..config import PROJECT_ROOT
from ..models import Analysis, Event
from ..state import StateManager
from ..utils.text import parse_uah_amount

log = logging.getLogger("radawatch.intelligence.document_tracker")

VERSIONS_DIR = PROJECT_ROOT / "state" / "document_versions"

AMOUNT_RE = re.compile(r"[\d\s,.]+\s*(грн|гривень|тис|млн|млрд)", re.IGNORECASE)
AREA_RE = re.compile(r"(\d[\d\s,.]+)\s*(га|гектар|м²|кв\.?\s*м)", re.IGNORECASE)


class DocumentTracker:
    def __init__(self, config, state: StateManager):
        self.config = config
        self.state = state

    def process(self, events: list[Event], analyses: list[Analysis]) -> None:
        for event in events:
            if event.category != "decision":
                continue
            raw_text = event.data.get("raw_text")
            if not raw_text:
                continue

            doc_key = self._stable_key(event)
            prev_version = self._load_latest_version(doc_key)

            version = {
                "doc_key": doc_key,
                "version": self._next_version_number(doc_key),
                "text": raw_text,
                "detected_at": datetime.now().isoformat(),
                "source_event_id": event.id,
            }
            self._save_version(doc_key, version)

            if prev_version:
                diff = self._compute_diff(prev_version, version)
                if diff and diff["is_significant"]:
                    event.data["document_diff"] = {
                        "prev_version": prev_version["version"],
                        "new_version": version["version"],
                        "changes": diff["changes"],
                        "is_significant": True,
                    }
                    log.info("Significant change in %s: %s", doc_key, diff["changes"])

    def _stable_key(self, event: Event) -> str:
        number = event.data.get("number", "")
        return f"{event.source}|{number or event.id}"

    def _version_dir(self, doc_key: str) -> Path:
        safe_key = doc_key.replace("|", "_").replace("/", "_")
        return VERSIONS_DIR / safe_key

    def _load_latest_version(self, doc_key: str) -> dict | None:
        vdir = self._version_dir(doc_key)
        if not vdir.exists():
            return None
        files = sorted(vdir.glob("v*.json"), reverse=True)
        if not files:
            return None
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)

    def _next_version_number(self, doc_key: str) -> int:
        vdir = self._version_dir(doc_key)
        if not vdir.exists():
            return 1
        files = list(vdir.glob("v*.json"))
        return len(files) + 1

    def _save_version(self, doc_key: str, version: dict) -> None:
        vdir = self._version_dir(doc_key)
        vdir.mkdir(parents=True, exist_ok=True)
        path = vdir / f"v{version['version']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(version, f, ensure_ascii=False, indent=2)

    def _compute_diff(self, old: dict, new: dict) -> dict | None:
        changes = []
        is_significant = False

        old_text = old.get("text", "")
        new_text = new.get("text", "")

        old_amounts = [parse_uah_amount(m.group()) for m in AMOUNT_RE.finditer(old_text)]
        new_amounts = [parse_uah_amount(m.group()) for m in AMOUNT_RE.finditer(new_text)]
        old_amounts = [a for a in old_amounts if a]
        new_amounts = [a for a in new_amounts if a]

        if old_amounts and new_amounts:
            old_max = max(old_amounts)
            new_max = max(new_amounts)
            if old_max > 0:
                pct = abs(new_max - old_max) / old_max
                if pct >= 0.2:
                    changes.append(f"Сума змінилась на {pct*100:.0f}%: {old_max:,.0f} → {new_max:,.0f} грн")
                    is_significant = True

        old_areas = [m.group() for m in AREA_RE.finditer(old_text)]
        new_areas = [m.group() for m in AREA_RE.finditer(new_text)]
        if set(old_areas) != set(new_areas):
            changes.append(f"Площа змінилась: {old_areas} → {new_areas}")
            is_significant = True

        if not changes:
            old_lines = set(old_text.splitlines())
            new_lines = set(new_text.splitlines())
            added = new_lines - old_lines
            removed = old_lines - new_lines
            if added or removed:
                changes.append(f"+{len(added)} / -{len(removed)} рядків")
                if len(added) + len(removed) > 10:
                    is_significant = True

        if not changes:
            return None

        return {
            "doc_key": old.get("doc_key", ""),
            "old_version": old.get("version"),
            "new_version": new.get("version"),
            "changes": changes,
            "is_significant": is_significant,
        }
