"""HTML parser for omr.gov.ua table rows.

Ported from telegram-bot/scrape.py. Extracts rows from the standard OMR
document listing table (rішення, розпорядження etc).
"""

from __future__ import annotations

import html
import re

BASE = "https://omr.gov.ua"

ROW_RE = re.compile(
    r'<td class="col-1">\s*(?P<number>[^<]*?)\s*</td>\s*'
    r'<td class="col-2">\s*(?:<time[^>]*>)?\s*(?P<date>[\d.]+)\s*(?:</time>)?\s*</td>\s*'
    r'<td class="col-3">\s*<a href="(?P<url>[^"]+)"[^>]*>\s*(?:<p>)?(?P<desc>.*?)(?:</p>)?\s*</a>',
    re.S,
)


def clean(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def parse_rows(html_text: str) -> list[dict]:
    out = []
    for m in ROW_RE.finditer(html_text):
        link = m.group("url")
        if link.startswith("/"):
            link = BASE + link
        out.append({
            "number": clean(m.group("number")),
            "date": clean(m.group("date")),
            "description": clean(m.group("desc")),
            "url": link,
        })
    return out
