"""Execution quality review from supplied metrics only — never invented."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_intelligence.config import MarketIntelligenceConfig


@dataclass(frozen=True, slots=True)
class ExecutionQualityInput:
    """Scores 0-100 when known; None means unavailable (not fabricated)."""

    entry_quality: Decimal | None = None
    exit_quality: Decimal | None = None
    timing_quality: Decimal | None = None
    sample_note: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionQualityReview:
    entry_quality: Decimal | None
    exit_quality: Decimal | None
    timing_quality: Decimal | None
    overall: Decimal | None
    passed: bool
    status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_quality": (
                str(self.entry_quality) if self.entry_quality is not None else None
            ),
            "exit_quality": (
                str(self.exit_quality) if self.exit_quality is not None else None
            ),
            "timing_quality": (
                str(self.timing_quality) if self.timing_quality is not None else None
            ),
            "overall": str(self.overall) if self.overall is not None else None,
            "passed": self.passed,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def review_execution_quality(
    config: MarketIntelligenceConfig, inp: ExecutionQualityInput
) -> ExecutionQualityReview:
    reasons: list[str] = []
    present = [
        v
        for v in (inp.entry_quality, inp.exit_quality, inp.timing_quality)
        if v is not None
    ]
    if not present:
        return ExecutionQualityReview(
            entry_quality=None,
            exit_quality=None,
            timing_quality=None,
            overall=None,
            passed=False,
            status="unavailable",
            reasons=(
                "No execution quality metrics supplied — "
                "fail closed; never invent scores.",
            ),
        )

    if inp.sample_note:
        reasons.append(inp.sample_note)

    overall = (
        sum(present, Decimal("0")) / Decimal(len(present))
    ).quantize(Decimal("0.01"))

    checks = [
        ("entry", inp.entry_quality, config.min_entry_quality),
        ("exit", inp.exit_quality, config.min_exit_quality),
        ("timing", inp.timing_quality, config.min_timing_quality),
    ]
    passed = overall >= config.min_overall_execution_quality
    for name, value, minimum in checks:
        if value is None:
            reasons.append(f"{name} quality unavailable.")
            continue
        if value < minimum:
            passed = False
            reasons.append(f"{name} quality {value} below min {minimum}.")
        else:
            reasons.append(f"{name} quality {value} ok.")

    if overall < config.min_overall_execution_quality:
        passed = False
        reasons.append(
            f"Overall {overall} below min {config.min_overall_execution_quality}."
        )
    else:
        reasons.append(f"Overall execution quality {overall}.")

    return ExecutionQualityReview(
        entry_quality=inp.entry_quality,
        exit_quality=inp.exit_quality,
        timing_quality=inp.timing_quality,
        overall=overall,
        passed=passed,
        status="available",
        reasons=tuple(reasons),
    )
