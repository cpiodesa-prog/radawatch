"""Infoprivid (news hook) suggester — daily digest for the editor.

Ranks events by newsworthiness, formats a Telegram digest,
and accounts for content cadence (news/analytics counts today/week).
"""

from __future__ import annotations

from datetime import datetime

from ..models import Analysis, Event, Infoprivid
from ..state import StateManager
from ..utils.text import esc


RISK_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
    "none": "⚪",
}


def suggest_infoprivids(
    events: list[Event],
    analyses: list[Analysis],
    state: StateManager,
    max_items: int = 5,
    min_risk_level: str = "medium",
) -> list[Infoprivid]:
    score_map: dict[str, float] = {}
    risk_map: dict[str, str] = {}
    for a in analyses:
        if a.analyzer == "newsworthiness":
            score_map[a.event_id] = a.data.get("newsworthiness", 0.0)
            risk_map[a.event_id] = a.risk_level
        elif a.analyzer == "risk_keywords" and a.risk_level != "none":
            existing = risk_map.get(a.event_id)
            if not existing or _risk_rank(a.risk_level) > _risk_rank(existing):
                risk_map[a.event_id] = a.risk_level

    min_rank = _risk_rank(min_risk_level)
    candidates = []
    for event in events:
        risk = risk_map.get(event.id, "none")
        if _risk_rank(risk) < min_rank:
            score = score_map.get(event.id, 0.0)
            if score < 0.5:
                continue

        newsworthiness = score_map.get(event.id, 0.3)
        candidates.append((event, risk, newsworthiness))

    candidates.sort(key=lambda x: x[2], reverse=True)
    candidates = candidates[:max_items]

    findings_map: dict[str, list] = {}
    for a in analyses:
        if a.analyzer == "risk_keywords" and a.findings:
            findings_map[a.event_id] = a.findings

    result = []
    for event, risk, newsworthiness in candidates:
        findings = findings_map.get(event.id, [])
        angle = _suggest_angle(event, risk, findings)
        suggested_type = "analytics" if newsworthiness > 0.7 and risk in ("high", "medium") else "news"

        result.append(Infoprivid(
            event_id=event.id,
            topic=event.category,
            risk_level=risk,
            newsworthiness=newsworthiness,
            angle=angle,
            suggested_type=suggested_type,
            source_urls=[event.url] if event.url else [],
            city=event.city,
            title=event.title,
            event_date=event.event_date,
        ))

    return result


def format_digest(infoprivids: list[Infoprivid], events: list[Event]) -> str:
    if not infoprivids:
        return "📰 Немає інфоприводів на сьогодні."

    event_map = {e.id: e for e in events}
    lines = [f"📰 <b>Інфоприводи дня ({len(infoprivids)})</b>\n"]

    for i, ip in enumerate(infoprivids, 1):
        event = event_map.get(ip.event_id)
        title = esc(event.title if event else ip.title or "(подія)")
        city_key = event.city if event else ip.city
        city_name = CITY_NAMES.get(city_key, city_key)
        cat_label = CATEGORY_LABELS.get(ip.topic, ip.topic)
        icon = RISK_ICONS.get(ip.risk_level, "⚪")
        level = ip.risk_level.upper()
        url = ip.source_urls[0] if ip.source_urls else ""
        type_tag = "📊" if ip.suggested_type == "analytics" else "📰"

        city_part = f"{city_name} · " if city_name else ""
        block = [
            f"{i}. {icon} [{level}] {title}",
            f"   {city_part}{cat_label} · {type_tag} {ip.suggested_type}",
        ]
        if url:
            block.append(f"   → <a href=\"{url}\">Першоджерело</a>")
        if ip.angle:
            block.append(f"   💡 Кут: {esc(ip.angle)}")

        lines.append("\n".join(block))

    return "\n\n".join(lines)


def _risk_rank(level: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(level, 0)


CITY_NAMES = {"odesa": "Одеса", "mykolaiv": "Миколаїв", "kherson": "Херсон", "national": ""}

CATEGORY_LABELS = {
    "session": "сесія ради",
    "personnel": "кадрове рішення",
    "decision": "рішення ради/виконкому",
    "declaration": "декларація",
    "nazk_check": "перевірка НАЗК",
    "commission": "засідання комісії",
    "vykonkom": "виконком",
    "trip": "відрядження",
}


def _suggest_angle(event: Event, risk: str, findings: list = None) -> str:
    cat = event.category
    data = event.data

    if cat == "personnel":
        return "Хто призначений, чи є декларації чи перевірки НАЗК"
    if cat == "declaration":
        return f"Порівняти з попередньою декларацією — {data.get('declaration_type', '')}"
    if cat == "decision" and risk in ("high", "medium"):
        parts = ["Хто отримує, зв'язок із попередніми рішеннями"]
        if findings:
            keywords = list({f.keyword for f in findings[:3]})
            amounts = [f.amount_uah for f in findings if f.amount_uah]
            if amounts:
                max_amt = max(amounts)
                if max_amt >= 1_000_000:
                    parts.append(f"сума {max_amt/1_000_000:.1f} млн грн")
                else:
                    parts.append(f"сума {max_amt:,.0f} грн")
            if keywords:
                parts.append(f"ключові слова: {', '.join(keywords)}")
        return "; ".join(parts)
    if cat == "nazk_check":
        return f"Результат перевірки: {data.get('result', '?')} — наслідки для посадовця"
    if cat == "commission":
        return "Які питання на порядку денному, наявність ризикових рішень"
    if cat == "session":
        return "Порядок денний сесії, ключові голосування"
    return "Перевірити деталі та контекст"
