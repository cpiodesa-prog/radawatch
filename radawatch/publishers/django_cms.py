"""Django CMS publisher — POST drafts to cpi.org.ua admin API.

Disabled by default; requires CPI_CMS_URL and CPI_CMS_TOKEN env vars.
Submits drafts with status "на перевірку" for editorial review.
"""

from __future__ import annotations

import json
import logging
import os

import requests

from ..models import Analysis, Draft, Event

log = logging.getLogger("radawatch.publishers.django_cms")

DEFAULT_CMS_URL = "https://cpi.org.ua/api/v1/drafts/"


class DjangoCmsPublisher:
    @property
    def publisher_id(self) -> str:
        return "django_cms"

    def publish(self, draft: Draft, events: list[Event], analyses: list[Analysis]) -> bool:
        cms_url = os.environ.get("CPI_CMS_URL", DEFAULT_CMS_URL)
        cms_token = os.environ.get("CPI_CMS_TOKEN")
        if not cms_token:
            log.debug("CPI_CMS_TOKEN not set — skipping CMS publish")
            return False

        payload = {
            "title": draft.title,
            "lede": draft.lede,
            "body_html": draft.body_html,
            "content_type": draft.content_type,
            "city": draft.city,
            "status": "review",
            "editorial_score": draft.editorial_score,
            "tags": draft.tags,
            "source_urls": draft.source_urls,
            "event_ids": draft.event_ids,
        }

        try:
            resp = requests.post(
                cms_url,
                json=payload,
                headers={
                    "Authorization": f"Token {cms_token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            log.info("Published to CMS: %s (id=%s)", draft.title, data.get("id"))
            return True
        except Exception as exc:
            log.error("CMS publish failed: %s", exc)
            return False
