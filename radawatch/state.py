"""Unified state manager: tracks seen events, cadence counters, person index, document versions."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .config import PROJECT_ROOT


class StateManager:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = PROJECT_ROOT / "state" / "state.json"
        self._path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "seen": {},
            "cadence": {
                "today_news": 0,
                "week_analytics": 0,
                "month_investigation": 0,
                "last_reset": date.today().isoformat(),
            },
            "person_index": {},
            "document_versions": {},
        }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, default=str)

    # --- Seen events ---

    def is_seen(self, event_id: str) -> bool:
        return event_id in self._data.get("seen", {})

    def mark_seen(self, event_id: str) -> None:
        self._data.setdefault("seen", {})[event_id] = datetime.now().isoformat()

    def filter_new(self, event_ids: list[str]) -> list[str]:
        seen = self._data.get("seen", {})
        return [eid for eid in event_ids if eid not in seen]

    def trim_seen(self, max_per_source: int = 500) -> None:
        seen = self._data.get("seen", {})
        by_source: dict[str, list[tuple[str, str]]] = {}
        for eid, ts in seen.items():
            src = eid.split("|", 1)[0] if "|" in eid else "_"
            by_source.setdefault(src, []).append((eid, ts))
        new_seen = {}
        for src, items in by_source.items():
            items.sort(key=lambda x: x[1], reverse=True)
            for eid, ts in items[:max_per_source]:
                new_seen[eid] = ts
        self._data["seen"] = new_seen

    # --- Cadence ---

    def _reset_cadence_if_needed(self) -> None:
        cad = self._data.setdefault("cadence", {})
        today = date.today().isoformat()
        last = cad.get("last_reset", "")
        if last != today:
            cad["today_news"] = 0
            if last and date.fromisoformat(last).isocalendar()[1] != date.today().isocalendar()[1]:
                cad["week_analytics"] = 0
            if last and date.fromisoformat(last).month != date.today().month:
                cad["month_investigation"] = 0
            cad["last_reset"] = today

    def update_cadence(self, content_type: str) -> None:
        self._reset_cadence_if_needed()
        cad = self._data["cadence"]
        if content_type == "news":
            cad["today_news"] = cad.get("today_news", 0) + 1
        elif content_type == "analytics":
            cad["week_analytics"] = cad.get("week_analytics", 0) + 1
        elif content_type == "investigation":
            cad["month_investigation"] = cad.get("month_investigation", 0) + 1

    def get_cadence(self) -> dict:
        self._reset_cadence_if_needed()
        return dict(self._data.get("cadence", {}))

    # --- Person index ---

    def record_person(self, name: str, event_id: str) -> None:
        idx = self._data.setdefault("person_index", {})
        idx.setdefault(name, [])
        if event_id not in idx[name]:
            idx[name].append(event_id)

    def get_person_history(self, name: str) -> list[str]:
        return self._data.get("person_index", {}).get(name, [])

    # --- Document versions ---

    def get_document_version(self, doc_id: str) -> Optional[int]:
        versions = self._data.get("document_versions", {}).get(doc_id, {})
        if not versions:
            return None
        return max(int(v) for v in versions.keys())

    def store_document_version(self, doc_id: str, version: int, data: dict) -> None:
        dvs = self._data.setdefault("document_versions", {})
        dvs.setdefault(doc_id, {})[str(version)] = data

    def get_document_data(self, doc_id: str, version: int) -> Optional[dict]:
        return self._data.get("document_versions", {}).get(doc_id, {}).get(str(version))
