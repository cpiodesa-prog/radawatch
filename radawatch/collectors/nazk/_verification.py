"""NAZK document verification: name matching, region checks.

Ported from declaration-watcher/scripts/watch.py verification functions.
"""

from __future__ import annotations

import re


def step1(doc: dict) -> dict:
    data = doc.get("data") or {}
    for key in ("step_1", "step_0"):
        block = data.get(key) or {}
        inner = block.get("data") if isinstance(block, dict) else block
        if isinstance(inner, list) and inner:
            inner = inner[0]
        if isinstance(inner, dict) and inner:
            return inner
    return {}


def full_name_of(doc: dict) -> str | None:
    s1 = step1(doc)
    parts = [s1.get("lastname"), s1.get("firstname"), s1.get("middlename")]
    parts = [p for p in parts if p]
    return " ".join(parts) if parts else None


def split_name(full_name: str) -> tuple[str, str, str]:
    parts = full_name.split()
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return full_name, "", ""


def name_matches(doc: dict, last: str, first: str, patronymic: str = "") -> bool:
    s1 = step1(doc)
    ln = str(s1.get("lastname", "") or "").strip().upper()
    fn = str(s1.get("firstname", "") or "").strip().upper()
    mn = str(s1.get("middlename", "") or "").strip().upper()
    ok_l = last.upper() == ln
    ok_f = (not first) or (first.upper() == fn)
    ok_m = (not patronymic) or (patronymic.upper() == mn)
    return ok_l and ok_f and ok_m


REGION_HINTS = {
    "одеськ": "одеськ",
    "миколаїв": "миколаїв",
    "херсон": "херсон",
}


def region_matches_workplace(doc: dict, region: str) -> bool:
    if not region:
        return True
    hint = None
    region_lower = region.lower()
    for key, val in REGION_HINTS.items():
        if key in region_lower:
            hint = val
            break
    if not hint:
        return True
    s1 = step1(doc)
    haystack = (str(s1.get("workPlace", "") or "") + " " + str(s1.get("workPost", "") or "")).lower()
    return hint in haystack


def position_contains(doc: dict, keyword: str) -> bool:
    s1 = step1(doc)
    workpost = str(s1.get("workPost", "") or "")
    return keyword.strip().upper() in workpost.upper()
