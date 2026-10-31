"""Deterministic Telegram message formatter — preserves existing bot formats.

Ported from telegram-bot/run_daily.py fmt_* functions.
Each event category has its own template with source links.
"""

from __future__ import annotations

import re

from ..models import Event
from ..utils.text import esc


def format_event(event: Event) -> str | None:
    formatter = _FORMATTERS.get(f"{event.city}.{event.category}")
    if not formatter:
        formatter = _FORMATTERS.get(event.category)
    if not formatter:
        return _format_generic(event)
    return formatter(event)


def _format_generic(e: Event) -> str:
    return (
        f"📌 <b>{esc(e.title)}</b>\n"
        f"{esc(e.city)} · {esc(e.category)}\n"
        f"{e.url}"
    )


# --- Odesa ---

def _fmt_odesa_session(e: Event) -> str:
    d = e.data
    return (
        f"🗓 <b>Скликання сесії Одеської міськради</b>\n"
        f"№{esc(d.get('number'))} від {esc(d.get('date'))}\n"
        f"{esc(d.get('description'))}\n"
        f"{e.url}"
    )


def _fmt_odesa_personnel(e: Event) -> str:
    d = e.data
    desc = d.get("description", "")
    if re.search(r"призначенн", desc, re.I):
        action, icon = "Призначення", "🆕"
    elif re.search(r"звільненн", desc, re.I):
        action, icon = "Звільнення", "🔚"
    elif re.search(r"покладенн.*обов.?язк", desc, re.I):
        action, icon = "Покладення обов'язків (т.в.о.)", "⏳"
    elif re.search(r"переведенн", desc, re.I):
        action, icon = "Переведення", "🔄"
    else:
        action, icon = "Кадрові зміни", "🧑‍💼"
    return (
        f"{icon} <b>Кадрове розпорядження: {action.lower()}</b>\n"
        f"№{esc(d.get('number'))} від {esc(d.get('date'))}\n"
        f"{esc(desc)}\n"
        f"{e.url}"
    )


def _fmt_odesa_trip(e: Event) -> str:
    d = e.data
    return (
        f"✈️ <b>Службове відрядження мера</b>\n"
        f"№{esc(d.get('number'))} від {esc(d.get('date'))}\n"
        f"{esc(d.get('description'))}\n"
        f"{e.url}"
    )


def _fmt_odesa_omva(e: Event) -> str:
    d = e.data
    return (
        f"🪖 <b>Розпорядження керівника ОМВА</b>\n"
        f"№{esc(d.get('number'))} від {esc(d.get('date'))}\n"
        f"{esc(d.get('description'))}\n"
        f"{e.url}"
    )


def _fmt_odesa_vykonkom(e: Event) -> str:
    d = e.data
    return (
        f"📋 <b>Засідання виконкому</b>\n"
        f"{esc(d.get('title'))}\n"
        f"{esc(d.get('description'))}\n"
        f"{e.url}"
    )


def _fmt_odesa_commission(e: Event) -> str:
    d = e.data
    lines = [
        f"🧩 <b>Засідання комісії</b>",
        f"{esc(d.get('commission'))}",
        f"{esc(d.get('date'))} {esc(d.get('time'))}" + (f", {esc(d.get('location'))}" if d.get("location") else ""),
    ]
    if d.get("commission_url"):
        lines.append(f"Комісія: {d['commission_url']}")
    if d.get("agenda_url"):
        lines.append(f"Порядок денний: {d['agenda_url']}")
    if d.get("stream_url"):
        lines.append(f"Трансляція: {d['stream_url']}")
    return "\n".join(lines)


# --- Mykolaiv ---

def _fmt_mk_session(e: Event) -> str:
    d = e.data
    return (
        f"🗓 <b>Миколаїв: скликання сесії</b>\n"
        f"№{esc(d.get('number'))} від {esc(d.get('date'))}\n"
        f"{esc(d.get('description'))}\n"
        f"{e.url}"
    )


def _fmt_mk_vykonkom(e: Event) -> str:
    d = e.data
    lines = [
        f"📋 <b>Миколаїв: засідання виконкому</b>",
        f"{esc(d.get('date'))}" + (f", {esc(d.get('time'))}" if d.get("time") else ""),
        f"Порядок денний: {d.get('agenda_url', '')}",
    ]
    if d.get("stream_url"):
        lines.append(f"Трансляція: {d['stream_url']}")
    return "\n".join(lines)


def _fmt_mk_commission(e: Event) -> str:
    d = e.data
    lines = [
        f"🧩 <b>Миколаїв: засідання комісії</b>",
        f"{esc(d.get('commission'))}",
        f"{esc(d.get('date'))}" + (f", {esc(d.get('time'))}" if d.get("time") else ""),
    ]
    if d.get("agenda_url"):
        lines.append(f"Порядок денний: {d['agenda_url']}")
    return "\n".join(lines)


# --- NAZK ---

def _fmt_declaration(e: Event) -> str:
    d = e.data
    lines = [
        f"🆕 <b>Нова декларація</b>",
        f"👤 {esc(d.get('name'))}",
        f"💼 {esc(d.get('workpost'))}" if d.get("workpost") else None,
        f"📌 {esc(d.get('workplace'))}" if d.get("workplace") else None,
        f"📄 {esc(d.get('declaration_type'))}, {esc(str(d.get('declaration_year')))}",
        f"🔗 {e.url}",
        f"🔎 {esc(d.get('matched_label'))}" if d.get("matched_label") else None,
    ]
    return "\n".join(ln for ln in lines if ln)


def _fmt_nazk_check(e: Event) -> str:
    d = e.data
    lines = [
        f"🔍 <b>Перевірка НАЗК</b>",
        f"👤 {esc(d.get('name'))}",
        f"💼 {esc(d.get('post'))}" if d.get("post") else None,
        f"📋 Категорія: {esc(d.get('category'))}" if d.get("category") else None,
        f"📅 Звітний період: {esc(d.get('period'))}" if d.get("period") else None,
        f"📊 Статус: {esc(d.get('status'))}" if d.get("status") else None,
        f"📝 Результат: {esc(d.get('result'))}" if d.get("result") else None,
        f"🔗 {e.url}",
    ]
    return "\n".join(ln for ln in lines if ln)


_FORMATTERS = {
    "odesa.session": _fmt_odesa_session,
    "odesa.personnel": _fmt_odesa_personnel,
    "odesa.trip": _fmt_odesa_trip,
    "odesa.omva": _fmt_odesa_omva,
    "odesa.vykonkom": _fmt_odesa_vykonkom,
    "odesa.commission": _fmt_odesa_commission,
    "mykolaiv.session": _fmt_mk_session,
    "mykolaiv.vykonkom": _fmt_mk_vykonkom,
    "mykolaiv.commission": _fmt_mk_commission,
    "declaration": _fmt_declaration,
    "nazk_check": _fmt_nazk_check,
}
