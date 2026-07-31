"""Institutional Volatility Gate v2 — adaptive ATR floor (evidence-calibrated).

Replaces the single fixed compression floor (atr_low_pct/2 = 0.20%) with an
adaptive model:

* Standard setups → keep 0.20% floor (never looser than v1 for weak tape).
* Exceptional institutional strength → floor may ease to 0.15% (calibration
  evidence: profitable fills clustered 0.15–0.20; median ATR% ≈ 0.178).
* Absolute hard minimum → 0.15% (never trade dead tape below evidence band).

Does not touch Quality/Confidence baselines (80), Risk Engine, PRE, or sizing.
"""

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
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    SessionAssessment,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
)

# Evidence floors from docs/trading/VOLATILITY_GATE_CALIBRATION_REPORT.md
V1_FIXED_FLOOR_PCT = Decimal("0.20")
EVIDENCE_EXCEPTIONAL_FLOOR_PCT = Decimal("0.15")


@dataclass(frozen=True, slots=True)
class VolatilityDecision:
    """Full audit trail for one volatility-gate evaluation."""

    passed: bool
    atr_pct: Decimal | None
    applied_floor_pct: Decimal
    standard_floor_pct: Decimal
    exceptional_floor_pct: Decimal
    hard_min_pct: Decimal
    band: str
    model: str
    exceptional_eligible: bool
    exceptional_used: bool
    strength_checks: dict[str, bool]
    strength_failures: tuple[str, ...]
    reason: str
    legacy_would_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "atr_pct": str(self.atr_pct) if self.atr_pct is not None else None,
            "applied_floor_pct": str(self.applied_floor_pct),
            "standard_floor_pct": str(self.standard_floor_pct),
            "exceptional_floor_pct": str(self.exceptional_floor_pct),
            "hard_min_pct": str(self.hard_min_pct),
            "band": self.band,
            "model": self.model,
            "exceptional_eligible": self.exceptional_eligible,
            "exceptional_used": self.exceptional_used,
            "strength_checks": dict(self.strength_checks),
            "strength_failures": list(self.strength_failures),
            "reason": self.reason,
            "legacy_would_pass": self.legacy_would_pass,
        }


def _legacy_floor(cfg: AiScalpingConfig) -> Decimal:
    return (cfg.atr_low_pct / Decimal("2")).quantize(Decimal("0.0001"))


def assess_exceptional_strength(
    *,
    trade_quality: int,
    confidence: int,
    structure_score: int,
    liquidity: int,
    momentum: int,
    mtf_alignment: int,
    session: SessionAssessment,
    spread: SpreadAssessment,
    thresholds: ResolvedThresholds,
    market_regime: MarketRegimeLabel | str | None,
    config: AiScalpingConfig | None = None,
    pa_passed: bool = True,
    direction_clear: bool = True,
) -> tuple[bool, dict[str, bool], tuple[str, ...]]:
    """Every institutional pillar must be strong for the exceptional ATR path."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    # Never below institutional 80 floors; honor adaptive (often 88 in low vol).
    min_q = max(80, int(thresholds.quality), int(cfg.vol_exceptional_min_quality))
    min_c = max(80, int(thresholds.confidence), int(cfg.vol_exceptional_min_confidence))

    allowed_regimes = set(cfg.vol_exceptional_regimes)
    regime = str(market_regime or "")

    checks: dict[str, bool] = {
        "quality": trade_quality >= min_q,
        "confidence": confidence >= min_c,
        "structure": structure_score >= int(cfg.vol_exceptional_min_structure),
        "liquidity": liquidity >= int(cfg.vol_exceptional_min_liquidity),
        "momentum": momentum >= int(cfg.vol_exceptional_min_momentum),
        "mtf_alignment": mtf_alignment >= int(cfg.vol_exceptional_min_mtf),
        "session": session.stars >= int(cfg.vol_exceptional_min_session_stars),
        "spread": (not spread.reject)
        and spread.score >= int(cfg.vol_exceptional_min_spread_score),
        "regime": regime in allowed_regimes,
        "pa_confluence": pa_passed,
        "direction": direction_clear,
    }
    failures = tuple(name for name, ok in checks.items() if not ok)
    return (len(failures) == 0), checks, failures


def evaluate_volatility_gate_v2(
    *,
    atr_pct: Decimal | None,
    thresholds: ResolvedThresholds,
    trade_quality: int,
    confidence: int,
    structure_score: int,
    liquidity: int,
    momentum: int,
    mtf_alignment: int,
    session: SessionAssessment,
    spread: SpreadAssessment,
    market_regime: MarketRegimeLabel | str | None = None,
    config: AiScalpingConfig | None = None,
    pa_passed: bool = True,
    direction_clear: bool = True,
) -> VolatilityDecision:
    """Resolve adaptive ATR floor and PASS/FAIL with full evidence."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    standard = Decimal(str(cfg.atr_compression_floor_pct))
    exceptional = Decimal(str(cfg.atr_exceptional_floor_pct))
    hard_min = Decimal(str(cfg.atr_hard_min_pct))
    # Safety: exceptional never below hard min; standard never below exceptional.
    if exceptional < hard_min:
        exceptional = hard_min
    if standard < exceptional:
        standard = exceptional
    legacy = _legacy_floor(cfg)
    band = str(thresholds.band)

    if atr_pct is None:
        # Fail-closed when volatility unknown and gate required.
        return VolatilityDecision(
            passed=False,
            atr_pct=None,
            applied_floor_pct=standard,
            standard_floor_pct=standard,
            exceptional_floor_pct=exceptional,
            hard_min_pct=hard_min,
            band=band,
            model="volatility_gate_v2",
            exceptional_eligible=False,
            exceptional_used=False,
            strength_checks={},
            strength_failures=("atr_pct_missing",),
            reason="Volatility unavailable — fail closed",
            legacy_would_pass=False,
        )

    if atr_pct <= 0:
        return VolatilityDecision(
            passed=False,
            atr_pct=atr_pct,
            applied_floor_pct=hard_min,
            standard_floor_pct=standard,
            exceptional_floor_pct=exceptional,
            hard_min_pct=hard_min,
            band=band,
            model="volatility_gate_v2",
            exceptional_eligible=False,
            exceptional_used=False,
            strength_checks={},
            strength_failures=("atr_pct_non_positive",),
            reason=f"Invalid volatility (ATR% ≤ 0) ATR%={atr_pct}",
            legacy_would_pass=False,
        )

    legacy_would_pass = not (band == "low" and atr_pct < legacy)

    # Outside low band: v1 never compressed-rejected; keep that behavior.
    if band != "low":
        return VolatilityDecision(
            passed=True,
            atr_pct=atr_pct,
            applied_floor_pct=Decimal("0"),
            standard_floor_pct=standard,
            exceptional_floor_pct=exceptional,
            hard_min_pct=hard_min,
            band=band,
            model="volatility_gate_v2",
            exceptional_eligible=False,
            exceptional_used=False,
            strength_checks={},
            strength_failures=(),
            reason=f"Volatility band={band} — compression floor not applicable",
            legacy_would_pass=True,
        )

    eligible, strength_checks, failures = assess_exceptional_strength(
        trade_quality=trade_quality,
        confidence=confidence,
        structure_score=structure_score,
        liquidity=liquidity,
        momentum=momentum,
        mtf_alignment=mtf_alignment,
        session=session,
        spread=spread,
        thresholds=thresholds,
        market_regime=market_regime,
        config=cfg,
        pa_passed=pa_passed,
        direction_clear=direction_clear,
    )

    applied = exceptional if eligible else standard
    exceptional_used = bool(eligible and atr_pct < standard)
    passed = atr_pct >= applied

    if atr_pct < hard_min:
        passed = False
        applied = hard_min
        exceptional_used = False
        reason = (
            f"Volatility below hard minimum ATR%={atr_pct} < {hard_min} "
            f"(evidence dead-tape floor)"
        )
    elif passed and exceptional_used:
        reason = (
            f"Volatility v2 PASS exceptional floor={applied} "
            f"ATR%={atr_pct} (standard={standard}; all strength gates clear)"
        )
    elif passed:
        reason = (
            f"Volatility v2 PASS standard floor={applied} ATR%={atr_pct}"
        )
    elif eligible:
        reason = (
            f"Volatility too compressed ATR%={atr_pct} < exceptional floor {applied}"
        )
    else:
        fail_txt = ",".join(failures) if failures else "strength"
        reason = (
            f"Volatility too compressed ATR%={atr_pct} < standard floor {applied} "
            f"(exceptional path blocked: {fail_txt})"
        )

    return VolatilityDecision(
        passed=passed,
        atr_pct=atr_pct,
        applied_floor_pct=applied,
        standard_floor_pct=standard,
        exceptional_floor_pct=exceptional,
        hard_min_pct=hard_min,
        band=band,
        model="volatility_gate_v2",
        exceptional_eligible=eligible,
        exceptional_used=exceptional_used,
        strength_checks=strength_checks,
        strength_failures=failures,
        reason=reason,
        legacy_would_pass=legacy_would_pass,
    )


def evaluate_volatility_gate_v1_compat(
    *,
    atr_pct: Decimal | None,
    band: str,
    config: AiScalpingConfig | None = None,
) -> bool:
    """Exact v1 compression check — used for before/after replay only."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if atr_pct is None or atr_pct <= 0:
        return False
    if band != "low":
        return True
    return atr_pct >= _legacy_floor(cfg)
