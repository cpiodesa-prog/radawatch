"""PoW (Proof-of-Work) solver for omr.gov.ua anti-bot protection.

Ported from telegram-bot/fetch.py. The site requires solving a SHA-256
puzzle before granting access (2waf protection). Each request needs:
1. GET the URL → receive a PoW challenge via Set-Cookie (notbot=...)
2. Brute-force a SHA-256 hash starting with required leading zeros
3. Re-request with the solution cookie (pow-result=...)
"""

from __future__ import annotations

import hashlib
import logging
import re
import string
import time
from base64 import b64encode

import requests

log = logging.getLogger("radawatch.odesa.pow")

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; radawatch/2.0)"

CHARSET = b"01"
POW_DELAY = 6


def _solve_pow(challenge: str, difficulty: int) -> str:
    prefix = "0" * difficulty
    nonce = 0
    while True:
        candidate = f"{challenge}{nonce}".encode()
        h = hashlib.sha256(candidate).hexdigest()
        if h.startswith(prefix):
            return str(nonce)
        nonce += 1


def get(url: str, retries: int = 4) -> str:
    for attempt in range(retries):
        resp = _SESSION.get(url, timeout=30)
        if resp.status_code == 200 and "notbot" not in resp.cookies:
            return resp.text

        notbot = resp.cookies.get("notbot", "")
        if not notbot:
            m = re.search(r'notbot=([^;\s]+)', resp.headers.get("Set-Cookie", ""))
            notbot = m.group(1) if m else ""

        if notbot:
            parts = notbot.split(".")
            if len(parts) >= 2:
                challenge = parts[0]
                difficulty = int(parts[1]) if parts[1].isdigit() else 5
                log.debug("PoW challenge: difficulty=%d, attempt %d/%d", difficulty, attempt + 1, retries)
                solution = _solve_pow(challenge, difficulty)
                _SESSION.cookies.set("pow-result", solution)
                _SESSION.cookies.set("notbot", notbot)
                time.sleep(POW_DELAY)
                resp2 = _SESSION.get(url, timeout=30)
                if resp2.status_code == 200:
                    return resp2.text
        else:
            time.sleep(POW_DELAY)

    raise RuntimeError(f"PoW solver failed after {retries} retries: {url}")
