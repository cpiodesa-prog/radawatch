"""Telegram publisher: sends messages via Bot API with retry on 429.

Ported from telegram-bot/telegram_notify.py.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from ..models import Event, Analysis, Draft
from .base import BasePublisher

log = logging.getLogger("radawatch.telegram")

API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramPublisher(BasePublisher):
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self._token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    def publish(self, draft: Draft, events: list[Event], analyses: list[Analysis]) -> bool:
        return self.send(draft.body_html)

    def send(self, text: str, chat_id: str | None = None, disable_preview: bool = False, max_retries: int = 5) -> bool:
        token = self._token
        target = chat_id or self._chat_id
        if not token or not target:
            log.warning("Telegram credentials not configured, skipping send")
            return False

        for attempt in range(max_retries):
            resp = requests.post(
                API.format(token=token),
                json={
                    "chat_id": target,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": disable_preview,
                },
                timeout=30,
            )
            if resp.ok:
                return True
            if resp.status_code == 429:
                try:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                except Exception:
                    retry_after = 5
                log.warning("Telegram 429, waiting %ds", retry_after + 1)
                time.sleep(retry_after + 1)
                continue
            log.error("Telegram API error %d: %s", resp.status_code, resp.text)
            return False
        log.error("Telegram API: %d retries exhausted", max_retries)
        return False

    def send_many(self, messages: list[str], delay: float = 1.5, **kw) -> int:
        sent = 0
        for i, text in enumerate(messages):
            if self.send(text, **kw):
                sent += 1
            if i < len(messages) - 1:
                time.sleep(delay)
        return sent
