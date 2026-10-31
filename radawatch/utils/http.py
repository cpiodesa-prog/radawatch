"""Shared HTTP client with retry and rate limiting."""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger("radawatch.http")

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


def get(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict | None = None, **kwargs) -> requests.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers or {}, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", RETRY_BACKOFF * attempt))
                log.warning("429 Too Many Requests for %s, sleeping %ds", url, retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("Request to %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
            time.sleep(RETRY_BACKOFF * attempt)
    raise requests.RequestException(f"Failed after {MAX_RETRIES} retries: {url}")


def post(url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, timeout=timeout, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", RETRY_BACKOFF * attempt))
                log.warning("429 Too Many Requests, sleeping %ds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("POST to %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
            time.sleep(RETRY_BACKOFF * attempt)
    raise requests.RequestException(f"Failed after {MAX_RETRIES} retries: {url}")
