#!/usr/bin/env python3
"""Import people list from declaration-watcher JSON/text into data/people.csv.

Usage:
    python scripts/import_people.py <source_file> [--append]

Source file can be:
    - JSON: [{"name": "...", "region": "...", "role": "..."}]
    - Text: one name per line, with optional tab-separated region and role
    - CSV:  existing people.csv from declaration-watcher
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "data" / "people.csv"


def load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "people" in data:
        return data["people"]
    return []


def load_text(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            row = {"name": parts[0].strip()}
            if len(parts) > 1:
                row["region"] = parts[1].strip()
            if len(parts) > 2:
                row["role"] = parts[2].strip()
            rows.append(row)
    return rows


def load_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return rows
    reader = csv.DictReader(lines)
    for row in reader:
        if row.get("name", "").strip():
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def main():
    parser = argparse.ArgumentParser(description="Import people list into data/people.csv")
    parser.add_argument("source", type=str, help="Path to source file (JSON, text, or CSV)")
    parser.add_argument("--append", action="store_true", help="Append to existing file instead of overwrite")
    args = parser.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"Source file not found: {src}", file=sys.stderr)
        return 1

    suffix = src.suffix.lower()
    if suffix == ".json":
        people = load_json(src)
    elif suffix == ".csv":
        people = load_csv(src)
    else:
        people = load_text(src)

    if not people:
        print("No people found in source file.", file=sys.stderr)
        return 1

    existing = set()
    if args.append and OUTPUT.exists():
        for row in load_csv(OUTPUT):
            existing.add(row["name"].lower())

    new_people = [p for p in people if p["name"].lower() not in existing]

    mode = "a" if args.append and OUTPUT.exists() else "w"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "region", "role"])
        if mode == "w":
            writer.writeheader()
        for person in new_people:
            writer.writerow({
                "name": person.get("name", ""),
                "region": person.get("region", ""),
                "role": person.get("role", ""),
            })

    total = len(existing) + len(new_people) if args.append else len(new_people)
    print(f"Imported {len(new_people)} people (total: {total}) → {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
