"""YouTube compliance analyzer: checks council YouTube channels for session recordings.

Ported from omr-monitor/analyzers/youtube.py.
Verifies: captions, descriptions, duration, date matching with known sessions.
Requires YOUTUBE_API_KEY environment variable.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from ..config import Config
from ..models import Analysis, Event, Finding
from .base import BaseAnalyzer

log = logging.getLogger("radawatch.analyzers.youtube")

SESSION_KEYWORDS = ("сесія", "комісія", "засідання")
MIN_DURATION_MINUTES = 10
LOOKBACK_DAYS = 14

ISO_DURATION_RE = re.compile(
    r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def _parse_duration_minutes(duration: str) -> float:
    match = ISO_DURATION_RE.match(duration or "")
    if not match:
        return 0.0
    parts = match.groupdict()
    return int(parts["hours"] or 0) * 60 + int(parts["minutes"] or 0) + int(parts["seconds"] or 0) / 60


class YoutubeComplianceAnalyzer(BaseAnalyzer):
    @property
    def analyzer_id(self) -> str:
        return "youtube_compliance"

    def analyze(self, events: list[Event]) -> list[Analysis]:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            log.info("YOUTUBE_API_KEY not set, skipping YouTube compliance check")
            return []

        try:
            from googleapiclient.discovery import build
        except ImportError:
            log.warning("google-api-python-client not installed, skipping YouTube check")
            return []

        results = []
        cities_checked = set()

        for event in events:
            city = event.city
            if city in cities_checked:
                continue
            cities_checked.add(city)

            city_cfg = self.config.cities.get(city, {})
            youtube_cfg = city_cfg.get("youtube", {})
            channel_id = youtube_cfg.get("channel_id")
            if not channel_id:
                continue

            session_dates = {e.event_date for e in events if e.city == city and e.event_date}
            findings = self._check_channel(api_key, channel_id, city, session_dates)

            for video_id, video_findings in findings.items():
                risk_level = "medium" if video_findings else "none"
                results.append(Analysis(
                    event_id=f"youtube.{city}|{video_id}",
                    analyzer=self.analyzer_id,
                    risk_level=risk_level,
                    findings=video_findings,
                ))

        return results

    @staticmethod
    def _check_channel(api_key: str, channel_id: str, city: str, session_dates: set) -> dict:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError

        try:
            youtube = build("youtube", "v3", developerKey=api_key)
            published_after = (
                datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
            ).isoformat().replace("+00:00", "Z")

            search_resp = youtube.search().list(
                part="snippet", channelId=channel_id,
                publishedAfter=published_after, order="date",
                type="video", maxResults=25,
            ).execute()
        except HttpError as exc:
            log.warning("[%s] YouTube API error: %s", city, exc)
            return {}

        video_ids = []
        for item in search_resp.get("items", []):
            title = item["snippet"]["title"]
            if any(kw in title.lower() for kw in SESSION_KEYWORDS):
                video_ids.append(item["id"]["videoId"])

        if not video_ids:
            return {}

        try:
            videos_resp = youtube.videos().list(
                part="contentDetails,snippet", id=",".join(video_ids),
            ).execute()
        except HttpError as exc:
            log.warning("[%s] YouTube videos.list error: %s", city, exc)
            return {}

        results = {}
        for video in videos_resp.get("items", []):
            vid = video["id"]
            snippet = video["snippet"]
            details = video["contentDetails"]
            findings = []

            duration = _parse_duration_minutes(details.get("duration", ""))
            if duration < MIN_DURATION_MINUTES:
                findings.append(Finding(
                    keyword="short_video",
                    context=f"Duration {duration:.0f}min < {MIN_DURATION_MINUTES}min",
                ))

            if details.get("caption") != "true":
                findings.append(Finding(keyword="no_captions", context=snippet["title"]))

            if not snippet.get("description", "").strip():
                findings.append(Finding(keyword="no_description", context=snippet["title"]))

            published_at = datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            ).date()
            if session_dates and published_at not in session_dates:
                findings.append(Finding(
                    keyword="date_mismatch",
                    context=f"Video date {published_at} not in known session dates",
                ))

            results[vid] = findings

        return results
