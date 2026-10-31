"""Automated editorial checks — main entry point.

Runs all editorial checks on a Draft and returns a ScoreResult.
"""

from __future__ import annotations

import re

from ..models import Draft
from .scoring import Issue, ScoreResult, calculate_score
from .headline_rules import check_headline
from .style_guide import (
    check_banned_phrases,
    check_dashes,
    check_lowercase,
    check_old_spelling,
    check_quotes,
    check_replacements,
)


CPI_ATTRIBUTION_RE = re.compile(
    r"Центр.{0,20}публічних.{0,20}розслідувань.{0,20}(дослідив|проаналізував|з.ясував|встановив)",
    re.IGNORECASE,
)

LINK_RE = re.compile(r'https?://\S+', re.IGNORECASE)
SENTENCE_RE = re.compile(r'[^.!?]+[.!?]')


def check_draft(draft: Draft, alert_below: float = 8.0) -> ScoreResult:
    issues: list[Issue] = []

    issues.extend(check_headline(draft.title, draft.content_type))
    issues.extend(_check_lede(draft.lede, draft.content_type))
    issues.extend(_check_body(draft.body_html, draft.content_type))

    full_text = f"{draft.title}\n{draft.lede}\n{draft.body_html}"
    issues.extend(_check_style(full_text))

    return calculate_score(issues, alert_below)


def _check_lede(lede: str, content_type: str) -> list[Issue]:
    issues = []
    if not lede:
        issues.append(Issue(
            severity="critical",
            rule="lede_missing",
            message="Лід відсутній",
        ))
        return issues

    if len(lede) > 200:
        issues.append(Issue(
            severity="major",
            rule="lede_too_long",
            message=f"Лід {len(lede)} символів (критично >200)",
            context=lede[:200],
        ))
    elif len(lede) > 160:
        issues.append(Issue(
            severity="minor",
            rule="lede_long",
            message=f"Лід {len(lede)} символів (бажано ≤160)",
            context=lede[:200],
        ))

    sentences = SENTENCE_RE.findall(lede)
    if len(sentences) > 1:
        issues.append(Issue(
            severity="major",
            rule="lede_multi_sentence",
            message=f"Лід містить {len(sentences)} речень (має бути одне)",
            context=lede[:200],
        ))

    if LINK_RE.search(lede):
        issues.append(Issue(
            severity="minor",
            rule="lede_has_link",
            message="Лід не повинен містити посилань",
            context=lede[:200],
        ))

    return issues


def _check_body(body: str, content_type: str) -> list[Issue]:
    issues = []
    plain = re.sub(r"<[^>]+>", "", body or "")

    if content_type == "news" and len(plain) < 1200:
        issues.append(Issue(
            severity="minor",
            rule="body_too_short",
            message=f"Текст {len(plain)} символів (мінімум 1200 для новини)",
        ))

    if content_type == "analytics":
        links = LINK_RE.findall(body or "")
        expected = max(1, len(plain) // 1000 * 2) if plain else 2
        if len(links) < expected:
            issues.append(Issue(
                severity="major",
                rule="analytics_few_links",
                message=f"Аналітика: {len(links)} посилань, потрібно ≥{expected} (2 на 1000 символів)",
            ))

    if not CPI_ATTRIBUTION_RE.search(body or ""):
        issues.append(Issue(
            severity="major",
            rule="no_cpi_attribution",
            message="Відсутня фраза «Центр публічних розслідувань дослідив/проаналізував»",
        ))

    return issues


def _check_style(text: str) -> list[Issue]:
    issues = []

    for msg in check_banned_phrases(text):
        issues.append(Issue(severity="minor", rule="banned_phrase", message=msg))

    for msg in check_dashes(text):
        issues.append(Issue(severity="minor", rule="typography_dash", message=msg))

    for msg in check_quotes(text):
        issues.append(Issue(severity="minor", rule="typography_quotes", message=msg))

    for msg in check_old_spelling(text):
        issues.append(Issue(severity="minor", rule="old_spelling", message=msg))

    for msg in check_lowercase(text):
        issues.append(Issue(severity="minor", rule="lowercase_rule", message=msg))

    for msg in check_replacements(text):
        issues.append(Issue(severity="minor", rule="vocabulary", message=msg))

    numbers = re.findall(r"\b(\d+)\b", text)
    for num_str in numbers:
        n = int(num_str)
        if 1 < n <= 10:
            issues.append(Issue(
                severity="minor",
                rule="number_spelling",
                message=f"Число {n} — до 10 пишеться словами",
                context=num_str,
            ))

    return issues
