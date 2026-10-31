"""Text utilities: HTML escaping, Ukrainian date parsing, text cleanup."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Optional

MONTHS_UK = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}


def esc(s: str | None) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"[ \t ]+", " ", s).strip()


def parse_ua_date(s: str) -> Optional[datetime]:
    m = re.search(r"(\d{1,2})\s+([а-яії]+)\s+(\d{4})\D*(\d{1,2}):(\d{2})", str(s), re.I)
    if not m or m.group(2).lower() not in MONTHS_UK:
        return None
    return datetime(
        int(m.group(3)), MONTHS_UK[m.group(2).lower()], int(m.group(1)),
        int(m.group(4)), int(m.group(5)),
    )


def parse_uah_amount(text: str) -> Optional[float]:
    """Parse Ukrainian monetary amounts: '15,2 мільйона', '300 тис. грн', '1 870 291 грн'."""
    multipliers = {"тис": 1_000, "мільйон": 1_000_000, "мільярд": 1_000_000_000,
                   "млн": 1_000_000, "млрд": 1_000_000_000}
    m = re.search(r"([\d\s,]+)\s*(тис|мільйон\w*|мільярд\w*|млн|млрд)\.?\s*(грн|гривень)?", text, re.I)
    if m:
        num_str = m.group(1).replace(" ", "").replace(",", ".")
        try:
            num = float(num_str)
        except ValueError:
            return None
        mult_key = re.sub(r"\w*$", "", m.group(2).lower())
        for k, v in multipliers.items():
            if k in m.group(2).lower():
                return num * v
        return num
    m = re.search(r"([\d\s]+)\s*(?:грн|гривень)", text)
    if m:
        try:
            return float(m.group(1).replace(" ", ""))
        except ValueError:
            return None
    return None
