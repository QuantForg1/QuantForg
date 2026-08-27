"""Scalp handoff eligibility — named predicates after Opportunity + sniper TAKE.

Observability + scanner handoff only. Does not call OMS, lower Opportunity 70,
convert WAIT→TAKE, or bypass Risk / Safety / Optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.ai_scalping.profiles import SCALPING_V1
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    is_gold_symbol,
    same_gold_identity,
    symbol_in_scan_universe,
)

SCALPING_PROFILE = "SCALPING_V1"
SWING_PROFILE = "SWING_ITE"
CONFIG_NOT_APPLICABLE = "N/A"

ELIGIBILITY_PASS = "PASS"
ELIGIBILITY_FAIL = "FAIL"
OPTIMIZER_NOT_REACHED = "NOT_REACHED"
OPTIMIZER_SKIPPED = "SKIPPED"

QUALITY_80_SWING = 80
CONFLUENCE_80_SWING = 80


def _i(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sniper_payload(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    raw = row.get("sniper_entry")
    return dict(raw) if isinstance(raw, dict) else {}


def sniper_is_take(row: dict[str, Any] | None) -> bool:
    """Authoritative sniper TAKE — passed plus BUY/SELL or setup_state TAKE."""
    if not isinstance(row, dict):
        return False
    sniper = _sniper_payload(row)
    if not bool(sniper.get("passed")):
        return False
    action = _text(
        row.get("signal_action") or sniper.get("action") or row.get("direction")
    ).upper()
    setup = _text(row.get("setup_state") or sniper.get("setup_state")).upper()
    return action in {"BUY", "SELL"} or setup == "TAKE"


def _direction(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return "NONE"
    sniper = _sniper_payload(row)
    raw = _text(
        row.get("direction") or row.get("signal_action") or sniper.get("action")
    ).upper()
    return raw if raw in {"BUY", "SELL"} else "NONE"


def _reject_code(reason: str | None) -> str | None:
    hay = _text(reason).lower()
    if not hay:
        return None
    if "cooldown" in hay:
        return "SYMBOL_COOLDOWN_ACTIVE"
    if "execution health" in hay or "health degraded" in hay:
        return "EXECUTION_HEALTH_DEGRADED"
    if "spread" in hay:
        return "SPREAD_REJECTED"
    if "min lot" in hay or "min_lot" in hay:
        return "MIN_LOT_REJECTED"
    if "stale" in hay:
        return "STALE_REJECTED"
    if "duplicate" in hay:
        return "DUPLICATE_REJECTED"
    if "capacity" in hay or "max open" in hay or "max_open" in hay:
        return "CAPACITY_REJECTED"
    if "portfolio" in hay:
        return "PORTFOLIO_REJECTED"
    if "rr" in hay or "risk/reward" in hay or "risk-reward" in hay:
        return "RR_REJECTED"
    if "invalidation" in hay or "stop" in hay:
        return "INVALID_STOP"
    if "universe" in hay or "disabled_autonomous" in hay:
        return "SYMBOL_UNIVERSE_MISMATCH"
    return None


def _predicate(
    *,
    name: str,
    passed: bool,
    actual: Any,
    required: Any,
    source: str,
    timeframe: str | None,
    hard: bool,
    authoritative: bool,
    config: str,
    can_incorrectly_reject_valid_take: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "actual": actual,
        "required": required,
        "source": source,
        "timeframe": timeframe,
        "hard": bool(hard),
        "authoritative": bool(authoritative),
        "config": config,
        "can_incorrectly_reject_valid_take": bool(can_incorrectly_reject_valid_take),
    }


@dataclass(frozen=True, slots=True)
class ScalpEligibilityTrace:
    """Named TAKE → handoff explanation. Never fabricates OMS execution."""

    eligibility_status: str
    eligibility_reason: str
    failed_predicates: tuple[dict[str, Any], ...]
    passed_predicates: tuple[dict[str, Any], ...]
    candidate_symbol: str | None
    candidate_direction: str
    candidate_signal_id: str | None
    candidate_setup_id: str | None
    candidate_confluence: str | None
    candidate_score: int | None
    candidate_rr: str | None
    candidate_stop_distance: str | None
    candidate_lots: str | None
    candidate_risk: str | None
    optimizer_status: str
    optimizer_reason: str
    should_hand_off: bool
    config_profile: str
    first_failed_code: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligibility_status": self.eligibility_status,
            "eligibility_reason": self.eligibility_reason,
            "failed_predicates": list(self.failed_predicates),
            "passed_predicates": list(self.passed_predicates),
            "candidate_symbol": self.candidate_symbol,
            "candidate_direction": self.candidate_direction,
            "candidate_signal_id": self.candidate_signal_id,
            "candidate_setup_id": self.candidate_setup_id,
            "candidate_confluence": self.candidate_confluence,
            "candidate_score": self.candidate_score,
            "candidate_rr": self.candidate_rr,
            "candidate_stop_distance": self.candidate_stop_distance,
            "candidate_lots": self.candidate_lots,
            "candidate_risk": self.candidate_risk,
            "optimizer_status": self.optimizer_status,
            "optimizer_reason": self.optimizer_reason,
            "should_hand_off": self.should_hand_off,
            "config_profile": self.config_profile,
            "first_failed_code": self.first_failed_code,
            "config_source": self.config_profile,
            **dict(self.extra),
        }


def explain_scalp_handoff(
    row: dict[str, Any] | None,
    *,
    portfolio_row: dict[str, Any] | None = None,
    universe: tuple[str, ...] | list[str] | None = None,
    blocked_by_portfolio: bool = False,
    portfolio_block_reason: str | None = None,
    in_portfolio_eligible: bool = False,
    ite_trading_mode: str | None = None,
    opportunity_threshold: int = OPPORTUNITY_SCORE_THRESHOLD,
) -> ScalpEligibilityTrace:
    """Explain why a scored scalp may or may not enter eligible_symbols."""
    score = dict(row or {})
    port = dict(portfolio_row or {})
    sniper = _sniper_payload(score)
    symbol = _text(score.get("symbol") or port.get("symbol")).upper() or None
    direction = _direction(score)
    opp = _i(score.get("opportunity_score"), 0) or 0
    threshold = _i(
        score.get("opportunity_threshold"), opportunity_threshold
    ) or opportunity_threshold
    score_reject = bool(score.get("reject"))
    port_reject = bool(port.get("reject")) if port else False
    extra_reason = ""
    if port_reject and not score_reject:
        extra_reason = _text(port.get("reject_reason") or port.get("blocking_gate"))
    elif port_reject and score_reject:
        score_reasons = _text(score.get("reject_reason"))
        port_reasons = _text(port.get("reject_reason"))
        if port_reasons and port_reasons not in score_reasons:
            extra_reason = port_reasons
    take = sniper_is_take(score)
    opp_pass = opp >= int(threshold)
    gold_ok = bool(symbol) and is_gold_symbol(symbol)
    universe_ok = symbol_in_scan_universe(symbol, universe)
    mode = _text(ite_trading_mode).lower() or SCALPING_PROFILE.lower()
    scalp_config = mode in {"scalping", "alpha"} or True
    config_profile = SCALPING_PROFILE if scalp_config else SWING_PROFILE
    quality = _i(score.get("trade_quality") or score.get("quality"))
    confluence = _i(
        score.get("ai_confidence") or score.get("confidence") or score.get("confluence")
    )
    swing_quality_applied = (
        score_reject
        and "below 80" in _text(score.get("reject_reason")).lower()
        and "quality" in _text(score.get("reject_reason")).lower()
    )
    swing_confluence_applied = (
        score_reject
        and "below 80" in _text(score.get("reject_reason")).lower()
        and "confluence" in _text(score.get("reject_reason")).lower()
    )

    predicates = [
        _predicate(
            name="symbol_xauusd_i",
            passed=gold_ok,
            actual=symbol or "NONE",
            required=CANONICAL_GOLD_BROKER_DISPLAY,
            source="gold_only.autonomous_execution_symbols",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=not gold_ok,
        ),
        _predicate(
            name="universe_membership",
            passed=universe_ok or gold_ok,
            actual=symbol or "NONE",
            required="scan universe (gold identity allowed)",
            source="resolve_scan_universe",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=not universe_ok and gold_ok,
        ),
        _predicate(
            name="opportunity_pass",
            passed=opp_pass,
            actual=opp,
            required=int(threshold),
            source="probability_selector.evaluate_from_score_dict",
            timeframe="M1/M5/M15",
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=False,
        ),
        _predicate(
            name="sniper_take",
            passed=take,
            actual=(
                "TAKE"
                if take
                else _text(sniper.get("setup_state") or sniper.get("primary_reason") or "WAIT")
            ),
            required="TAKE",
            source="sniper_entry.evaluate_sniper_entry",
            timeframe=_text(sniper.get("atr_timeframe") or sniper.get("zone_timeframe"))
            or "M5",
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=False,
        ),
        _predicate(
            name="direction",
            passed=direction in {"BUY", "SELL"},
            actual=direction,
            required="BUY|SELL",
            source="direction.decide_scalping_direction",
            timeframe="M1/M5",
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=direction not in {"BUY", "SELL"},
        ),
        _predicate(
            name="score_not_rejected",
            passed=not score_reject,
            actual=score.get("reject_reason") if score_reject else "clear",
            required="reject=false",
            source="ai_scalping.scoring.score_scalping_setup",
            timeframe="M1/M5",
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=False,
        ),
        _predicate(
            name="no_swing_quality_80",
            passed=not swing_quality_applied,
            actual=quality,
            required=f"scalp quality floor {int(SCALPING_V1.normal_vol.quality)} — not swing {QUALITY_80_SWING}",
            source="ITEConfig.is_scalping / PositionEligibilityEngine",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=True,
        ),
        _predicate(
            name="no_swing_confluence_80",
            passed=not swing_confluence_applied,
            actual=confluence,
            required=f"scalp confidence floor {int(SCALPING_V1.normal_vol.confidence)} — not swing {CONFLUENCE_80_SWING}",
            source="ITEConfig.is_scalping / PositionEligibilityEngine",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=True,
        ),
        _predicate(
            name="portfolio_capacity",
            passed=not blocked_by_portfolio,
            actual=portfolio_block_reason or "clear",
            required="not blocked_by_portfolio",
            source="portfolio_scanner.check_portfolio_limits",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=False,
        ),
        _predicate(
            name="portfolio_extra_reject",
            passed=not bool(extra_reason),
            actual=extra_reason or "none",
            required="no extra portfolio reject after score PASS",
            source="portfolio_scanner._row_from_score",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=bool(extra_reason),
        ),
        _predicate(
            name="portfolio_eligible_membership",
            passed=in_portfolio_eligible or (
                opp_pass
                and take
                and not score_reject
                and not extra_reason
                and not blocked_by_portfolio
                and direction in {"BUY", "SELL"}
                and (universe_ok or gold_ok)
            ),
            actual="in_ranked" if in_portfolio_eligible else "missing_from_ranked",
            required="portfolio ranked OR gold-identity scalp PASS",
            source="rank_scalping_opportunities ∩ opportunity_eligible",
            timeframe=None,
            hard=True,
            authoritative=True,
            config=SCALPING_PROFILE,
            can_incorrectly_reject_valid_take=not in_portfolio_eligible,
        ),
    ]

    failed = tuple(p for p in predicates if not p["passed"] and p["hard"])
    passed = tuple(p for p in predicates if p["passed"])
    should = len(failed) == 0 and take and opp_pass and not score_reject
    first_code: str | None = None
    if extra_reason:
        first_code = _reject_code(extra_reason) or "PORTFOLIO_EXTRA_REJECT"
    elif score_reject:
        first_code = (
            _reject_code(str(score.get("reject_reason") or ""))
            or str(score.get("reject_reason") or "SCORE_REJECTED")
        )
    elif blocked_by_portfolio:
        first_code = "CAPACITY_REJECTED"
    elif not gold_ok:
        first_code = "SYMBOL_UNIVERSE_MISMATCH"
    elif not opp_pass:
        first_code = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    elif not take:
        first_code = str(sniper.get("primary_reason") or "WAIT_NO_SNIPER_TRIGGER")
    elif direction not in {"BUY", "SELL"}:
        first_code = "DIRECTION_NONE"
    elif not should:
        first_code = "NO_ELIGIBLE_SETUP"

    if should:
        status = ELIGIBILITY_PASS
        reason = "SCALP_ELIGIBLE"
        first_code = None
    else:
        status = ELIGIBILITY_FAIL
        reason = first_code or "NO_ELIGIBLE_SETUP"

    signal_id = _text(score.get("signal_id") or sniper.get("signal_id")) or None
    setup_id = _text(
        score.get("setup_id")
        or sniper.get("setup_id")
        or score.get("setup_family")
        or sniper.get("setup_family")
    ) or None
    audit = (
        score.get("opportunity_audit")
        if isinstance(score.get("opportunity_audit"), dict)
        else {}
    )
    diagnostics = (
        sniper.get("diagnostics") if isinstance(sniper.get("diagnostics"), dict) else {}
    )
    confluence_class = _text(
        audit.get("confluence")
        or sniper.get("confluence_class")
        or diagnostics.get("confluence_class")
    ) or None
    indicators = score.get("indicators") if isinstance(score.get("indicators"), dict) else {}
    return ScalpEligibilityTrace(
        eligibility_status=status,
        eligibility_reason=reason,
        failed_predicates=failed,
        passed_predicates=passed,
        candidate_symbol=symbol,
        candidate_direction=direction,
        candidate_signal_id=signal_id,
        candidate_setup_id=setup_id,
        candidate_confluence=confluence_class,
        candidate_score=opp,
        candidate_rr=_text(score.get("expected_rr") or sniper.get("expected_rr")) or None,
        candidate_stop_distance=_text(indicators.get("stop_distance")) or None,
        candidate_lots=_text(score.get("approved_lots") or score.get("lots")) or None,
        candidate_risk=_text(score.get("risk_pct") or score.get("risk")) or None,
        optimizer_status=OPTIMIZER_NOT_REACHED,
        optimizer_reason="SCANNER_HANDOFF — optimizer runs only after eligibility PASS",
        should_hand_off=should,
        config_profile=config_profile,
        first_failed_code=first_code,
        extra={
            "same_gold_identity": same_gold_identity(
                symbol, CANONICAL_GOLD_BROKER_DISPLAY
            ),
            "in_portfolio_eligible": bool(in_portfolio_eligible),
            "quality": quality,
            "confidence": confluence,
            "scalp_quality_floor": int(SCALPING_V1.normal_vol.quality),
            "scalp_confidence_floor": int(SCALPING_V1.normal_vol.confidence),
            "swing_quality_floor": QUALITY_80_SWING,
            "swing_confluence_floor": CONFLUENCE_80_SWING,
        },
    )


def match_portfolio_row(
    symbol: str | None,
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any] | None:
    code = _text(symbol).upper()
    if not code:
        return None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        other = _text(row.get("symbol")).upper()
        if other == code or same_gold_identity(code, other):
            return row
    return None
