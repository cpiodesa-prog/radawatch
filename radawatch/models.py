"""Unified data models for the RadaWatch pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class FileRef:
    path: str
    mime_type: str = ""
    size: int = 0


@dataclass
class Event:
    id: str
    source: str
    city: str
    category: str
    title: str
    url: str
    detected_at: datetime
    event_date: Optional[date] = None
    data: dict = field(default_factory=dict)
    files: list[FileRef] = field(default_factory=list)
    raw_text: Optional[str] = None


@dataclass
class Finding:
    keyword: str
    context: str = ""
    amount_uah: Optional[float] = None
    detail: str = ""


@dataclass
class Analysis:
    event_id: str
    analyzer: str
    risk_level: str  # "none" | "low" | "medium" | "high"
    findings: list[Finding] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@dataclass
class VerificationResult:
    event_id: str
    verifier: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    related_event_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    details: str = ""


@dataclass
class EditorialIssue:
    severity: str  # "critical" | "major" | "minor"
    category: str
    quote: str = ""
    problem: str = ""
    fix: str = ""


@dataclass
class Draft:
    content_type: str  # "news" | "analytics" | "investigation"
    title: str
    lede: str
    body_html: str
    city: str
    event_ids: list[str] = field(default_factory=list)
    editorial_score: int = 0
    editorial_issues: list[EditorialIssue] = field(default_factory=list)
    status: str = "auto_draft"  # auto_draft → review → approved → published
    tags: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


@dataclass
class Infoprivid:
    event_id: str
    topic: str
    risk_level: str
    newsworthiness: float  # 0.0–1.0
    angle: str
    suggested_type: str  # "news" | "analytics"
    source_urls: list[str] = field(default_factory=list)
    city: str = ""
    title: str = ""
    event_date: Optional[date] = None


@dataclass
class DocumentVersion:
    doc_id: str
    version: int
    source: str
    captured_at: datetime
    title: str
    text: str
    data: dict = field(default_factory=dict)


@dataclass
class DocumentDiff:
    doc_id: str
    from_version: int
    to_version: int
    changes: list[dict] = field(default_factory=list)
    is_significant: bool = False
    summary: str = ""
