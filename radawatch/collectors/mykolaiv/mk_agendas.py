"""Vykonkom agenda URLs from mkrada.gov.ua.

Ported from telegram-bot/mk_agendas.py.
Maps session dates to their agenda document URLs.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://mkrada.gov.ua"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; radawatch/2.0)"}
AGENDA_LIST_URL = f"{BASE}/content/poryadki-denni-zasidan-vikonkomu.html"
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def fetch_vykonkom_agendas() -> dict[str, str]:
    resp = requests.get(AGENDA_LIST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    out: dict[str, str] = {}
    for a in soup.select("a[href*='/files/']"):
        title = a.get_text(" ", strip=True)
        if "ПОРЯДОК ДЕННИЙ" not in title.upper():
            continue
        m = DATE_RE.search(title)
        if not m:
            continue
        key = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        href = a.get("href")
        url = href if href.startswith("http") else BASE + href
        out.setdefault(key, url)
    return out
