"""Headline rules for maximum readability and engagement.

Guidelines from CPI editorial policy:
- Person with position, not institution
- Concrete subject or amount (car, apartment, hectares)
- Recognizable name or case (NABU, Trukhanov)
- Tender — via recipient or consequence for people
- Consequence instead of procedure
- War/mobilization/TCC/treason — directly in headline if in text
"""

from __future__ import annotations

import re

from .scoring import Issue


def check_headline(headline: str, content_type: str = "news") -> list[Issue]:
    issues = []
    limit = 100 if content_type == "news" else 120

    if len(headline) > limit:
        issues.append(Issue(
            severity="major",
            rule="headline_length",
            message=f"Заголовок {len(headline)} символів (ліміт {limit})",
            context=headline,
        ))

    if len(headline) < 20:
        issues.append(Issue(
            severity="minor",
            rule="headline_too_short",
            message="Заголовок занадто короткий — може бути неінформативним",
            context=headline,
        ))

    abbr_pattern = re.compile(r"\b(млн|грн|тис|%|га|км)\b", re.IGNORECASE)
    if abbr_pattern.search(headline):
        issues.append(Issue(
            severity="minor",
            rule="headline_abbreviations",
            message="В заголовку скорочення (млн, грн, тис, %) — краще повне слово",
            context=headline,
        ))

    if headline and not headline[0].isupper():
        issues.append(Issue(
            severity="minor",
            rule="headline_capitalization",
            message="Заголовок починається з малої літери",
            context=headline,
        ))

    if headline.endswith("."):
        issues.append(Issue(
            severity="minor",
            rule="headline_period",
            message="Заголовок не повинен закінчуватись крапкою",
            context=headline,
        ))

    return issues
