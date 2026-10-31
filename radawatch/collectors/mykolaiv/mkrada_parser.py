"""HTML parser for mkrada.gov.ua document listings.

Ported from telegram-bot/mk_scrape.py. No anti-bot protection needed.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://mkrada.gov.ua"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; radawatch/2.0)"}

NUM_DATE_RE = re.compile(r"№\s*([^\s(]+)\s*\(([^)]+)\)")
DOC_ID_RE = re.compile(r"/documents/(\d+)\.html")

CATEGORY_COUNCIL = 1
CATEGORY_MAYOR = 4
CATEGORY_VYKONKOM = 5
CATEGORY_PROGRAMS = 6


def fetch_latest(category: int, n_pages: int = 1) -> list[dict]:
    results = []
    for page in range(n_pages):
        start = page * 10
        url = f"{BASE}/documents/?c={category}&start={start}"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.news_line_item")
        if not items:
            break
        for div in items:
            a = div.select_one('a[href*="/documents/"]')
            if not a:
                continue
            id_match = DOC_ID_RE.search(a.get("href", ""))
            doc_id = id_match.group(1) if id_match else None
            title = a.get_text(strip=True)
            href = a.get("href", "")
            url_full = href if href.startswith("http") else BASE + href

            full_text = div.get_text(" ", strip=True)
            nd_match = NUM_DATE_RE.search(full_text)
            num = nd_match.group(1) if nd_match else None
            date_raw = nd_match.group(2) if nd_match else None

            results.append({
                "id": doc_id,
                "number": num,
                "date": date_raw,
                "description": title,
                "url": url_full,
            })
    return results
