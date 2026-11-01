"""NAZK public API v2 client.

Ported from declaration-watcher/scripts/watch.py.
Provides session creation, list/get endpoints with retry logic.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

log = logging.getLogger("radawatch.nazk.api")

DEFAULT_BASE_URL = "https://public-api.nazk.gov.ua/v2"
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_PAGES = 5
DEFAULT_PAGE_SIZE = 20


class RateLimitError(Exception):
    pass


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "application/json",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
        "Referer": "https://public.nazk.gov.ua/",
        "Origin": "https://public.nazk.gov.ua",
    })
    return s


def api_list(session: requests.Session, params: dict,
             base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT,
             tries: int = 3) -> list[dict]:
    url = f"{base_url}/documents/list"
    last_err = None
    for attempt in range(tries):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 403:
                raise RateLimitError(f"403 for {params}")
            resp.raise_for_status()
            return resp.json().get("data", [])
        except RateLimitError:
            raise
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    log.warning("api_list failed: %s -> %s", params, last_err)
    return []


def api_get_full(session: requests.Session, doc_id: str,
                 base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT,
                 tries: int = 3) -> Optional[dict]:
    url = f"{base_url}/documents/{doc_id}"
    last_err = None
    for attempt in range(tries):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    log.warning("api_get_full failed: %s -> %s", doc_id, last_err)
    return None


def fetch_list_since(session: requests.Session, extra_params: dict, since_ts: float,
                     base_url: str = DEFAULT_BASE_URL,
                     max_pages: int = DEFAULT_MAX_PAGES,
                     page_size: int = DEFAULT_PAGE_SIZE) -> list[dict]:
    all_items = []
    page = 1
    while page <= max_pages:
        params = dict(extra_params)
        params["start_date"] = int(since_ts)
        params["page"] = page
        params["limit"] = page_size
        items = api_list(session, params, base_url=base_url)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page += 1
    return all_items
