#!/usr/bin/env python3
"""Migrate state from 3 separate bot repositories into unified state/state.json.

Reads existing state files from:
    - telegram-bot/state/seen.json
    - omr-monitor/state/seen.json
    - declaration-watcher/state/seen.json

Merges them into Bot&Cod/state/state.json with the unified ID format.

Usage:
    python scripts/migrate_state.py [--telegram-bot PATH] [--omr-monitor PATH] [--declaration-watcher PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "state" / "state.json"

SOURCE_MAP_TELEGRAM_BOT = {
    "sessions": "odesa.sessions",
    "personnel": "odesa.personnel",
    "trips": "odesa.trips",
    "omva": "odesa.omva",
    "vykonkom": "odesa.vykonkom",
    "commissions": "odesa.commissions",
    "mk_sessions": "mykolaiv.sessions",
    "mk_vykonkom": "mykolaiv.vykonkom",
    "mk_commissions": "mykolaiv.commissions",
}

SOURCE_MAP_OMR_MONITOR = {
    "odesa_decisions": "odesa.decisions",
    "mykolaiv_decisions": "mykolaiv.decisions",
    "kherson_decisions": "kherson.decisions",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def migrate_telegram_bot(repo_path: Path) -> dict[str, str]:
    seen = {}
    state_file = repo_path / "state" / "seen.json"
    data = load_json(state_file)

    for old_key, seen_ids in data.items():
        new_source = SOURCE_MAP_TELEGRAM_BOT.get(old_key)
        if not new_source and isinstance(seen_ids, list):
            new_source = old_key
        if new_source and isinstance(seen_ids, list):
            for sid in seen_ids:
                unified_id = f"{new_source}|{sid}"
                seen[unified_id] = "migrated"
        elif isinstance(seen_ids, dict):
            for sid in seen_ids:
                new_source_2 = SOURCE_MAP_TELEGRAM_BOT.get(old_key, old_key)
                unified_id = f"{new_source_2}|{sid}"
                seen[unified_id] = "migrated"

    print(f"  telegram-bot: {len(seen)} seen IDs from {state_file}")
    return seen


def migrate_omr_monitor(repo_path: Path) -> dict[str, str]:
    seen = {}
    state_file = repo_path / "state" / "seen.json"
    data = load_json(state_file)

    for old_key, seen_ids in data.items():
        new_source = SOURCE_MAP_OMR_MONITOR.get(old_key, old_key)
        if isinstance(seen_ids, list):
            for sid in seen_ids:
                unified_id = f"{new_source}|{sid}"
                seen[unified_id] = "migrated"
        elif isinstance(seen_ids, dict):
            for sid in seen_ids:
                unified_id = f"{new_source}|{sid}"
                seen[unified_id] = "migrated"

    print(f"  omr-monitor: {len(seen)} seen IDs from {state_file}")
    return seen


def migrate_declaration_watcher(repo_path: Path) -> dict[str, str]:
    seen = {}
    state_file = repo_path / "state" / "seen.json"
    data = load_json(state_file)

    for section in ("declarations", "checks"):
        seen_ids = data.get(section, [])
        source = f"nazk.{section}"
        if isinstance(seen_ids, list):
            for sid in seen_ids:
                unified_id = f"{source}|{sid}"
                seen[unified_id] = "migrated"
        elif isinstance(seen_ids, dict):
            for sid in seen_ids:
                unified_id = f"{source}|{sid}"
                seen[unified_id] = "migrated"

    if "seen_ids" in data:
        for sid in data["seen_ids"]:
            unified_id = f"nazk.declarations|{sid}"
            seen[unified_id] = "migrated"

    print(f"  declaration-watcher: {len(seen)} seen IDs from {state_file}")
    return seen


def main():
    parser = argparse.ArgumentParser(description="Migrate state from 3 bot repos")
    parser.add_argument("--telegram-bot", type=str, default=None,
                        help="Path to telegram-bot repo (default: ../telegram-bot)")
    parser.add_argument("--omr-monitor", type=str, default=None,
                        help="Path to omr-monitor repo (default: ../omr-monitor)")
    parser.add_argument("--declaration-watcher", type=str, default=None,
                        help="Path to declaration-watcher repo (default: ../declaration-watcher)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be migrated without writing")
    args = parser.parse_args()

    parent = PROJECT_ROOT.parent
    tb_path = Path(args.telegram_bot) if args.telegram_bot else parent / "telegram-bot"
    om_path = Path(args.omr_monitor) if args.omr_monitor else parent / "omr-monitor"
    dw_path = Path(args.declaration_watcher) if args.declaration_watcher else parent / "declaration-watcher"

    print("Migrating state from 3 bot repositories...")
    all_seen = {}

    if tb_path.exists():
        all_seen.update(migrate_telegram_bot(tb_path))
    else:
        print(f"  telegram-bot: SKIP (not found at {tb_path})")

    if om_path.exists():
        all_seen.update(migrate_omr_monitor(om_path))
    else:
        print(f"  omr-monitor: SKIP (not found at {om_path})")

    if dw_path.exists():
        all_seen.update(migrate_declaration_watcher(dw_path))
    else:
        print(f"  declaration-watcher: SKIP (not found at {dw_path})")

    print(f"\nTotal unique seen IDs: {len(all_seen)}")

    if args.dry_run:
        print("Dry run — not writing state file.")
        return 0

    existing = load_json(OUTPUT)
    existing_seen = existing.get("seen", {})
    existing_seen.update(all_seen)

    state = {
        "seen": existing_seen,
        "cadence": existing.get("cadence", {
            "today_news": 0,
            "week_analytics": 0,
            "month_investigation": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
        }),
        "person_index": existing.get("person_index", {}),
        "document_versions": existing.get("document_versions", {}),
        "migrated_at": datetime.now().isoformat(),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"Written → {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
