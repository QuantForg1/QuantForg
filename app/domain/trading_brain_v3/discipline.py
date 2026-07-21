"""Institutional Discipline Score — composite capital-preservation score."""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def compute_discipline_score(
    inp: BrainInput,
    config: TradingBrainConfig,
    *,
    env_score: Decimal | None,
    challenge_score: Decimal | None,
    readiness_score: Decimal | None,
    post_trade_score: Decimal | None,
    quality_score: Decimal | None,
) -> ModuleResult:
    reasons: list[str] = []
    weights: list[tuple[str, Decimal, Decimal | None]] = [
        ("environment", Decimal("0.20"), env_score),
        ("challenge", Decimal("0.25"), challenge_score),
        ("readiness", Decimal("0.25"), readiness_score),
        ("post_trade", Decimal("0.15"), post_trade_score),
        ("quality", Decimal("0.15"), quality_score),
    ]

    total_w = Decimal("0")
    weighted = Decimal("0")
    for name, w, s in weights:
        if s is None:
            reasons.append(f"{name} unavailable — excluded from discipline")
            continue
        total_w += w
        weighted += s * w
        reasons.append(f"{name}={s} weight={w}")

    if total_w <= 0:
        return ModuleResult(
            module="institutional_discipline_score",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "Insufficient scored modules for discipline score",
                "Never fabricates discipline metrics",
            ),
            details={},
        )

    # Penalties for authority failures.
    score = (weighted / total_w).quantize(Decimal("0.01"))
    if inp.risk_engine_passed is not True:
        score = min(score, Decimal("40"))
        reasons.append("Risk Engine not passed — discipline capped")
    if inp.safety_engine_passed is not True:
        score = min(score, Decimal("40"))
        reasons.append("Safety Engine not passed — discipline capped")
    if inp.kill_switch is True:
        score = Decimal("0")
        reasons.append("Kill switch — discipline zeroed")

    passed = score >= config.min_discipline_score
    rec = "Proceed" if passed else "No Trade"
    reasons.append(
        f"Discipline {score} vs min {config.min_discipline_score}"
    )
    reasons.append("Score measures process discipline — not expected profit")
    return ModuleResult(
        module="institutional_discipline_score",
        status="available",
        score=score,
        passed=passed,
        recommendation=rec,
        reasons=tuple(reasons),
        details={
            "min_discipline_score": str(config.min_discipline_score),
            "components_weighted": total_w,
            "promise_profitability": False,
        },
    )
