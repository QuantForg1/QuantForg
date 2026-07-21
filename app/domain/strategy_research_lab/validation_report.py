"""Explainable Validation Reports — lab advisory only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.strategy_research_lab.scorecards import StrategyScorecard


@dataclass(frozen=True, slots=True)
class ValidationReport:
    strategy_key: str
    generated_at: datetime
    passed: bool
    summary: str
    why_valid: tuple[str, ...]
    why_invalid: tuple[str, ...]
    improvements: tuple[str, ...]
    scorecard: dict[str, object]
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "generated_at": self.generated_at.isoformat(),
            "passed": self.passed,
            "summary": self.summary,
            "why_valid": list(self.why_valid),
            "why_invalid": list(self.why_invalid),
            "improvements": list(self.improvements),
            "scorecard": dict(self.scorecard),
            "disclaimer": self.disclaimer,
            "lab_only": True,
        }


def build_validation_report(
    *,
    strategy_key: str,
    scorecard: StrategyScorecard,
    notes: tuple[str, ...] = (),
) -> ValidationReport:
    why_valid = list(scorecard.strengths)
    why_invalid = list(scorecard.weaknesses) if not scorecard.passed else []
    improvements = [
        "Re-run validation with walk-forward before promotion.",
        "Keep parameter experiments in sandbox — never mutate production defaults.",
        "Require operator approval before Decision Engine eligibility.",
    ]
    if notes:
        improvements = list(notes) + improvements

    summary = (
        f"Strategy {strategy_key} validation "
        f"{'PASSED' if scorecard.passed else 'FAILED'} "
        f"(scorecard {scorecard.score})."
    )
    return ValidationReport(
        strategy_key=strategy_key,
        generated_at=datetime.now(UTC),
        passed=scorecard.passed,
        summary=summary,
        why_valid=tuple(why_valid),
        why_invalid=tuple(why_invalid),
        improvements=tuple(improvements[:6]),
        scorecard=scorecard.to_dict(),
        disclaimer=(
            "Explainable Validation Report is lab-only. "
            "It never submits broker orders and never promises profitability. "
            "Promotion remains advisory until Decision Engine / operator gates."
        ),
    )
