"""Institutional quality gates — reject weak scalping setups with reasons."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    MarketRegimeLabel,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.ai_scalping.pa_confluence import (
    PaConfluenceResult,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    SessionAssessment,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
)
from app.domain.institutional_trading.ai_scalping.volatility_gate_v2 import (
    VolatilityDecision,
    evaluate_volatility_gate_v2,
)


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    passed: bool
    rejects: tuple[str, ...]
    checks: dict[str, bool]
    volatility_decision: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "rejects": list(self.rejects),
            "checks": dict(self.checks),
            "volatility_decision": dict(self.volatility_decision or {}),
        }


def evaluate_quality_gates(
    *,
    direction: DirectionDecision,
    momentum: int,
    liquidity: int,
    structure_score: int,
    session: SessionAssessment,
    spread: SpreadAssessment,
    thresholds: ResolvedThresholds,
    confidence: int,
    trade_quality: int,
    expected_rr: Decimal | None,
    atr_pct: Decimal | None,
    config: AiScalpingConfig | None = None,
    pa_confluence: PaConfluenceResult | None = None,
    min_expected_rr_override: Decimal | None = None,
    mtf_alignment: int = 0,
    market_regime: MarketRegimeLabel | str | None = None,
    symbol: str | None = None,
) -> QualityGateResult:
    """Trade only when structure, liquidity, momentum, spread, vol, session align."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    rejects: list[str] = []
    checks: dict[str, bool] = {}

    strong_structure = structure_score >= cfg.min_structure_score
    checks["strong_structure"] = strong_structure
    if cfg.require_strong_structure and not strong_structure:
        rejects.append(
            f"Weak structure score {structure_score} < {cfg.min_structure_score}"
        )

    liq_ok = liquidity >= cfg.min_liquidity_score
    checks["high_liquidity"] = liq_ok
    if cfg.require_liquidity_event and not liq_ok:
        rejects.append(
            f"Insufficient liquidity score {liquidity} < {cfg.min_liquidity_score}"
        )

    mom_ok = momentum >= cfg.min_momentum_score
    checks["momentum_confirmation"] = mom_ok
    if cfg.require_momentum_confirm and not mom_ok:
        rejects.append(
            f"Momentum {momentum} < {cfg.min_momentum_score} — no confirmation"
        )

    spread_ok = not spread.reject
    checks["tight_spread"] = spread_ok
    if cfg.require_tight_spread and not spread_ok:
        rejects.append(spread.reason or "Spread reject")

    direction_clear = direction.direction.value in {"BUY", "SELL"}
    pa_passed = True
    if pa_confluence is not None:
        pa_passed = pa_confluence.passed

    vol_decision: VolatilityDecision = evaluate_volatility_gate_v2(
        atr_pct=atr_pct,
        thresholds=thresholds,
        trade_quality=trade_quality,
        confidence=confidence,
        structure_score=structure_score,
        liquidity=liquidity,
        momentum=momentum,
        mtf_alignment=mtf_alignment,
        session=session,
        spread=spread,
        market_regime=market_regime,
        config=cfg,
        pa_passed=pa_passed,
        direction_clear=direction_clear,
        symbol=symbol,
    )
    vol_ok = vol_decision.passed
    checks["valid_volatility"] = vol_ok
    if cfg.require_valid_volatility and not vol_ok:
        rejects.append(vol_decision.reason)

    session_ok = session.stars >= cfg.min_session_stars
    checks["session_quality"] = session_ok
    if cfg.require_session_quality and not session_ok:
        rejects.append(f"Session quality {session.stars}★ < {cfg.min_session_stars}★")

    checks["clear_direction"] = direction_clear
    if not checks["clear_direction"]:
        rejects.append("No clear BUY/SELL edge (balanced scores → reject)")

    checks["adaptive_confidence"] = confidence >= thresholds.confidence
    if not checks["adaptive_confidence"]:
        rejects.append(
            f"Confidence {confidence} < adaptive {thresholds.confidence} ({thresholds.band})"  # noqa: E501
        )

    checks["adaptive_quality"] = trade_quality >= thresholds.quality
    if not checks["adaptive_quality"]:
        rejects.append(
            f"Trade quality {trade_quality} < adaptive {thresholds.quality} ({thresholds.band})"  # noqa: E501
        )

    min_rr = (
        min_expected_rr_override
        if min_expected_rr_override is not None
        else cfg.min_expected_rr
    )
    # Never allow override below configured floor
    if min_rr < cfg.min_expected_rr:
        min_rr = cfg.min_expected_rr
    rr_ok = expected_rr is not None and expected_rr >= min_rr
    checks["min_rr"] = bool(rr_ok)
    if not rr_ok:
        rejects.append(f"Expected RR {expected_rr} below minimum {min_rr}")

    pa_ok = True
    if pa_confluence is not None:
        pa_ok = pa_confluence.passed
        checks["pa_confluence"] = pa_ok
        if cfg.require_pa_confluence and not pa_ok:
            rejects.append(
                f"PA confluence {pa_confluence.score} < {cfg.min_pa_confluence_score}"
            )
    else:
        checks["pa_confluence"] = True

    return QualityGateResult(
        passed=len(rejects) == 0,
        rejects=tuple(rejects),
        checks=checks,
        volatility_decision=vol_decision.to_dict(),
    )
