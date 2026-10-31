"""PoW (Proof-of-Work) solver for omr.gov.ua anti-bot protection.

Ported from telegram-bot/fetch.py. The site serves a 2waf JS challenge page
(status 503) containing:
  - const prefix = "..."
  - const suffixLen = N
  - const hash4find = "..."
  - setCookie('notbot','...')
We brute-force a suffix so sha256(prefix+suffix) == hash4find, then set
cookies notbot + pow-result (base64 of prefix+suffix) and re-request.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import logging
import re
import time

import requests

log = logging.getLogger("radawatch.odesa.pow")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CHARS = "01"
POW_DELAY = 6

_session = requests.Session()
_session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "uk,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
})


def _is_challenge(html: str) -> bool:
    return "pow-result" in html and "hash4find" in html


def _solve(html: str) -> tuple[str, str]:
    """Parse JS challenge and brute-force the solution."""
    prefix = re.search(r'const prefix\s*=\s*"([^"]+)"', html).group(1)
    suffix_len = int(re.search(r'const suffixLen\s*=\s*(\d+)', html).group(1))
    target = re.search(r'const hash4find\s*=\s*"([^"]+)"', html).group(1)
    notbot = re.search(r"setCookie\('notbot','([^']+)'\)", html).group(1)

    for combo in itertools.product(CHARS, repeat=suffix_len):
        s = prefix + "".join(combo)
        if hashlib.sha256(s.encode()).hexdigest() == target:
            pow_result = base64.b64encode(s.encode()).decode()
            return notbot, pow_result

    raise RuntimeError("PoW solution not found")


def get(url: str, retries: int = 4) -> str:
    for attempt in range(retries):
        resp = _session.get(url, timeout=60)
        html = resp.text
        if not _is_challenge(html):
            return html

        log.debug("PoW challenge on %s, attempt %d/%d", url, attempt + 1, retries)
        notbot, pow_result = _solve(html)
        _session.cookies.set("notbot", notbot, domain="omr.gov.ua", path="/")
        _session.cookies.set("pow-result", pow_result, domain="omr.gov.ua", path="/")
        time.sleep(POW_DELAY)

    resp = _session.get(url, timeout=60)
    html = resp.text
    if _is_challenge(html):
        raise RuntimeError(f"Still blocked after {retries} attempts: {url}")
    return html
