"""Editorial scoring system.

Start: 10 points.
Penalties: critical −2, major −0.75 (cap −3), minor −0.25 (cap −1.5).
Minimum: 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Issue:
    severity: str  # "critical" | "major" | "minor"
    rule: str
    message: str
    context: str = ""


@dataclass
class ScoreResult:
    score: float
    issues: list[Issue] = field(default_factory=list)
    passed: bool = True

    @property
    def grade(self) -> str:
        if self.score >= 9:
            return "A"
        if self.score >= 8:
            return "B"
        if self.score >= 6:
            return "C"
        return "D"


PENALTY = {
    "critical": 2.0,
    "major": 0.75,
    "minor": 0.25,
}

PENALTY_CAP = {
    "critical": None,
    "major": 3.0,
    "minor": 1.5,
}


def calculate_score(issues: list[Issue], alert_below: float = 8.0) -> ScoreResult:
    score = 10.0
    totals = {"critical": 0.0, "major": 0.0, "minor": 0.0}

    for issue in issues:
        sev = issue.severity
        pen = PENALTY.get(sev, 0.25)
        cap = PENALTY_CAP.get(sev)
        if cap is not None and totals[sev] + pen > cap:
            continue
        totals[sev] += pen
        score -= pen

    score = max(score, 1.0)
    has_critical = any(i.severity == "critical" for i in issues)
    has_major = any(i.severity == "major" for i in issues)
    passed = score >= alert_below and not has_critical

    return ScoreResult(score=round(score, 2), issues=issues, passed=passed)
