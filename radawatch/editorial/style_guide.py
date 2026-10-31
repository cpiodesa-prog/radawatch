"""Editorial style guide — vocabulary, typography, spelling rules.

Rules ported from cpr-redaktor/cpr_core.py editorial standards.
"""

from __future__ import annotations

import re

REPLACEMENTS = {
    "ТГ": "громада",
    "ОТГ": "громада",
    "мешканці": "жителі",
    "мешканець": "житель",
    "мешканка": "жителька",
    "кримчанин": "кримець",
    "кримчанка": "кримка",
    "кримчани": "кримці",
    "білорус": "білорус",
}

LOWERCASE_WORDS = {"росія", "путін", "рф", "кремль"}

FEMINITIVES = {
    "авторка", "дослідниця", "журналістка", "експертка",
    "аналітикиня", "депутатка", "міністерка", "речниця",
    "керівниця", "директорка", "координаторка", "головуюча",
}

NEW_SPELLING = {
    "проект": "проєкт",
    "проекту": "проєкту",
    "проектів": "проєктів",
    "проектом": "проєктом",
    "проекти": "проєкти",
    "ефір": "етер",
    "ефіру": "етеру",
    "ефірі": "етері",
}

BANNED_PHRASES = [
    "Нагадаємо",
    "Як ми раніше писали",
    "Варто зазначити",
    "Зазначимо",
    "Слід зауважити",
    "Нагадуємо",
    "Як відомо",
]

EM_DASH = "—"
CORRECT_QUOTES = ('"', '"')
WRONG_DASHES = ["–", "-"]
WRONG_QUOTES_RE = re.compile(r'[«»„"‟]')


def check_dashes(text: str) -> list[str]:
    issues = []
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        if " - " in line and " — " not in line:
            issues.append(f"Рядок {i}: дефіс замість тире «—»")
    return issues


def check_quotes(text: str) -> list[str]:
    issues = []
    if WRONG_QUOTES_RE.search(text):
        issues.append("Використано ялинкові/німецькі лапки замість прямих \"\"")
    return issues


def check_banned_phrases(text: str) -> list[str]:
    found = []
    text_lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in text_lower:
            found.append(f"Заборонена формула: «{phrase}»")
    return found


def check_old_spelling(text: str) -> list[str]:
    issues = []
    for old, new in NEW_SPELLING.items():
        pattern = re.compile(rf"\b{re.escape(old)}\b", re.IGNORECASE)
        if pattern.search(text):
            issues.append(f"Старий правопис «{old}» → «{new}»")
    return issues


def check_lowercase(text: str) -> list[str]:
    issues = []
    for word in LOWERCASE_WORDS:
        pattern = re.compile(rf"\b{word[0].upper()}{word[1:]}\b")
        if pattern.search(text):
            issues.append(f"«{word}» пишеться з малої літери")
    return issues


def check_replacements(text: str) -> list[str]:
    issues = []
    for old, new in REPLACEMENTS.items():
        pattern = re.compile(rf"\b{re.escape(old)}\b")
        if pattern.search(text):
            issues.append(f"Словник: «{old}» → «{new}»")
    return issues
