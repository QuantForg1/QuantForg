"""Phase 7 decision / validation / sizing / authorization builders.

Never invent equity, confidence, fills, or trade_allowed.
Never order_send. AUTHORIZED ≠ LIVE submit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.domain.autonomous_trading_control import (
    AUTH_RESULTS,
    DECISION_OUTCOMES,
    MODEL_VERSION,
    VALIDATION_STAGES,
    data_quality,
    isolation_payload,
)
from app.domain.autonomous_trading_control.store import get_autonomy_store


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def evaluate_decision(
    *,
    symbol: str = "XAUUSD",
    direction: str | None = None,
    strategy: str | None = None,
    market_regime: str | None = None,
    signal_timestamp: str | None = None,
    entry_conditions: list[str] | None = None,
    proposed_stop_loss: float | None = None,
    proposed_take_profit: float | None = None,
    risk_reward_estimate: float | None = None,
    confidence: float | None = None,
    supporting_evidence: list[str] | None = None,
    risk_assessment: str | None = None,
    market_data_stale: bool = False,
    market_data_missing: bool = False,
    strategy_approved: bool | None = None,
    require_approval: bool = True,
) -> dict[str, Any]:
    """Build a structured decision. Incomplete/stale → NO_TRADE / BLOCKED."""
    store = get_autonomy_store()
    mode = store.get_mode()["mode"]
    missing: list[str] = []
    evidence = [str(x) for x in (supporting_evidence or [])][:40]
    conditions = [str(x) for x in (entry_conditions or [])][:40]

    sym = (symbol or "").strip().upper() or "XAUUSD"
    if market_data_missing:
        missing.append("market_data")
    if market_data_stale:
        missing.append("freshness")
    if not market_regime:
        missing.append("market_regime")
    if confidence is None:
        missing.append("confidence_calibration")
    elif not evidence:
        # Confidence without evidence is not calibrated — refuse inventing.
        missing.append("confidence_evidence")
        confidence = None

    outcome = "NO_TRADE"
    execution_eligibility = "not_eligible"
    required_approval = bool(require_approval)
    reasons: list[str] = []

    if market_data_missing or market_data_stale:
        outcome = "NO_TRADE"
        reasons.append("incomplete_or_stale_market_data")
    elif strategy_approved is False:
        outcome = "REJECTED"
        reasons.append("strategy_not_approved")
    elif mode == "RESTRICTED_OR_DISABLED":
        outcome = "EXECUTION_BLOCKED"
        reasons.append("autonomy_mode_restricted")
    elif mode == "OBSERVE_ONLY":
        # Observe may still produce advisory candidates without execution path.
        if (
            direction
            and str(direction).upper() in {"BUY", "SELL"}
            and confidence is not None
        ):
            outcome = str(direction).upper()
            reasons.append("observe_only_advisory_candidate")
            execution_eligibility = "observe_only_blocked"
        else:
            outcome = "HOLD" if direction is None else "NO_TRADE"
            reasons.append("insufficient_advisory_evidence")
    elif mode == "ASSISTED":
        if (
            direction
            and str(direction).upper() in {"BUY", "SELL"}
            and confidence is not None
        ):
            outcome = "WAITING_FOR_APPROVAL"
            execution_eligibility = "requires_human_approval"
            required_approval = True
            reasons.append("assisted_mode_requires_approval")
        else:
            outcome = "NO_TRADE"
            reasons.append("assisted_no_tradeable_candidate")
    elif mode == "CONTROLLED_AUTOMATION":
        # Intent only — phase7_live_dispatch remains false.
        if (
            direction
            and str(direction).upper() in {"BUY", "SELL"}
            and confidence is not None
        ):
            if strategy_approved is True:
                outcome = str(direction).upper()
                execution_eligibility = "eligible_for_existing_oms_preview_only"
                reasons.append("controlled_automation_intent_no_phase7_dispatch")
            else:
                outcome = "WAITING_FOR_APPROVAL"
                execution_eligibility = "requires_strategy_approval"
                reasons.append("strategy_approval_required")
        else:
            outcome = "NO_TRADE"
            reasons.append("controlled_no_tradeable_candidate")

    if outcome not in DECISION_OUTCOMES:
        outcome = "NO_TRADE"

    expiry = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
    decision = {
        "decision_id": f"dec-{uuid4().hex[:12]}",
        "symbol": sym,
        "direction": (str(direction).upper() if direction else None),
        "strategy": strategy,
        "market_regime": market_regime,
        "signal_timestamp": signal_timestamp or _now(),
        "entry_conditions": conditions,
        "proposed_stop_loss": proposed_stop_loss,
        "proposed_take_profit": proposed_take_profit,
        "risk_reward_estimate": risk_reward_estimate,
        "confidence": confidence,
        "supporting_evidence": evidence,
        "risk_assessment": risk_assessment
        or ("blocked_incomplete_data" if missing else "advisory"),
        "execution_eligibility": execution_eligibility,
        "required_approval": required_approval,
        "decision_expiry": expiry,
        "model_version": MODEL_VERSION,
        "outcome": outcome,
        "reasons": reasons,
        "autonomy_mode": mode,
        "phase7_live_dispatch": False,
        "never_order_send": True,
        "signal_key": f"{sym}:{direction}:{strategy}:{signal_timestamp}",
        "data_quality": data_quality(
            source="phase7.decision_engine",
            as_of=_now(),
            stale=market_data_stale,
            missing_fields=missing,
        ),
        **isolation_payload(),
    }
    return store.put_decision(decision)


def select_strategies(
    *,
    candidates: list[dict[str, Any]] | None = None,
    regime: str | None = None,
) -> dict[str, Any]:
    rows = [r for r in (candidates or []) if isinstance(r, dict)]
    recommended: dict[str, Any] | None = None
    alternatives: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for row in rows:
        status = str(row.get("status") or row.get("lifecycle_status") or "").lower()
        stage = str(row.get("stage") or row.get("phase5_stage") or "")
        approved = bool(
            row.get("approved")
            or status in {"approved", "production", "monitoring"}
            or stage in {"Deployment", "Monitoring", "Approval"}
        )
        draft = status in {"draft", "research"} or stage == "Draft"
        suspended = status in {"suspended", "failed", "retired"} or stage in {
            "Paused",
            "Archived",
            "Rollback",
        }
        backtest_only = bool(row.get("backtest_only")) or stage in {
            "Backtesting",
            "Validation",
        }

        # Suitability only when historical metrics exist — never invent.
        raw_metrics = row.get("metrics")
        metrics_dict: dict[str, Any] = (
            raw_metrics if isinstance(raw_metrics, dict) else {}
        )
        hist_score = metrics_dict.get("suitability_score")
        if hist_score is None:
            hist_score = metrics_dict.get("win_rate")
        score: float | None = (
            float(hist_score) if isinstance(hist_score, (int, float)) else None
        )

        reasoning: list[str] = []
        item: dict[str, Any] = {
            "strategy_id": row.get("strategy_id") or row.get("id"),
            "name": row.get("name"),
            "version": row.get("version"),
            "status": status or stage or "unknown",
            "approved": approved,
            "suitability_score": score,
            "regime": regime,
            "regime_compatible": (
                None
                if regime is None
                else (
                    str(row.get("preferred_regime") or "").lower() == regime.lower()
                    if row.get("preferred_regime")
                    else None
                )
            ),
            "health": row.get("health"),
            "degradation": row.get("degradation"),
            "performance_evidence": {
                k: metrics_dict[k]
                for k in (
                    "win_rate",
                    "profit_factor",
                    "max_drawdown",
                    "trade_count",
                )
                if k in metrics_dict and isinstance(metrics_dict[k], (int, float))
            },
            "selection_confidence": score,
            "reasoning": reasoning,
        }

        if draft or suspended or (not approved):
            reasoning.append("excluded_not_approved_or_unhealthy")
            if backtest_only:
                reasoning.append("backtest_success_not_live_authorization")
            excluded.append(item)
            continue
        if backtest_only and not approved:
            reasoning.append("backtest_success_not_live_authorization")
            excluded.append(item)
            continue
        if score is None:
            reasoning.append("no_historical_suitability_evidence")
        else:
            reasoning.append("historical_metrics_present")
        if recommended is None:
            recommended = item
        else:
            alternatives.append(item)

    return {
        "ok": True,
        "recommended": recommended,
        "alternatives": alternatives,
        "excluded": excluded,
        "rules": {
            "only_approved_for_execution_consideration": True,
            "draft_cannot_execute": True,
            "suspended_cannot_execute": True,
            "backtest_alone_not_live": True,
            "ai_cannot_silently_modify_deployed_strategy": True,
        },
        "data_quality": data_quality(
            source="phase7.strategy_selection",
            as_of=_now(),
            missing_fields=([] if rows else ["strategies"]),
        ),
        **isolation_payload(),
    }


def validate_signal(payload: dict[str, Any]) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    hard_fail = False

    def _stage(name: str, status: str, reason: str = "") -> None:
        nonlocal hard_fail
        stages.append({"stage": name, "status": status, "reason": reason})
        if status == "FAIL":
            hard_fail = True

    # 1 freshness
    ts = _parse_ts(
        payload.get("market_data_timestamp") or payload.get("signal_timestamp")
    )
    if ts is None:
        _stage("market_data_freshness", "FAIL", "missing_timestamp")
    else:
        age = (datetime.now(UTC) - ts).total_seconds()
        if age > 300:
            _stage("market_data_freshness", "FAIL", f"stale_age_sec={int(age)}")
        elif age > 120:
            _stage("market_data_freshness", "WARNING", f"aging_sec={int(age)}")
        else:
            _stage("market_data_freshness", "PASS")

    # 2 symbol
    sym = str(payload.get("symbol") or "").strip().upper()
    if not sym:
        _stage("symbol_validity", "FAIL", "missing_symbol")
    elif "XAU" in sym or sym.endswith("USD"):
        _stage("symbol_validity", "PASS")
    else:
        _stage("symbol_validity", "WARNING", "non_standard_symbol")

    # 3 strategy auth
    if payload.get("strategy_approved") is True:
        _stage("strategy_authorization", "PASS")
    elif payload.get("strategy_approved") is False:
        _stage("strategy_authorization", "FAIL", "strategy_not_approved")
    else:
        _stage("strategy_authorization", "NOT_AVAILABLE", "approval_unknown")

    # 4 integrity
    if payload.get("signal_integrity") is False:
        _stage("signal_integrity", "FAIL", "integrity_check_failed")
    elif payload.get("direction") in {"BUY", "SELL", "buy", "sell"}:
        _stage("signal_integrity", "PASS")
    else:
        _stage("signal_integrity", "NOT_AVAILABLE", "direction_missing")

    # 5 regime
    if payload.get("regime_compatible") is True:
        _stage("market_regime_compatibility", "PASS")
    elif payload.get("regime_compatible") is False:
        _stage("market_regime_compatibility", "FAIL", "regime_mismatch")
    else:
        _stage("market_regime_compatibility", "NOT_AVAILABLE")

    # 6 spread
    spread = payload.get("spread")
    max_spread = payload.get("max_spread")
    if isinstance(spread, (int, float)) and isinstance(max_spread, (int, float)):
        if float(spread) > float(max_spread):
            _stage("spread_validation", "FAIL", "spread_exceeds_max")
        else:
            _stage("spread_validation", "PASS")
    else:
        _stage("spread_validation", "NOT_AVAILABLE", "spread_facts_missing")

    # 7 volatility
    if payload.get("volatility_ok") is True:
        _stage("volatility_validation", "PASS")
    elif payload.get("volatility_ok") is False:
        _stage("volatility_validation", "FAIL", "volatility_out_of_band")
    else:
        _stage("volatility_validation", "NOT_AVAILABLE")

    # 8 RR
    rr = payload.get("risk_reward")
    if isinstance(rr, (int, float)):
        if float(rr) < 1.0:
            _stage("risk_reward_validation", "FAIL", "rr_below_1")
        else:
            _stage("risk_reward_validation", "PASS")
    else:
        _stage("risk_reward_validation", "NOT_AVAILABLE")

    # 9 SL
    if payload.get("stop_loss") is None:
        _stage("stop_loss_validation", "FAIL", "stop_loss_required")
    else:
        _stage("stop_loss_validation", "PASS")

    # 10 sizing
    if payload.get("volume") is None and payload.get("lot_size") is None:
        _stage("position_sizing_validation", "NOT_AVAILABLE", "size_not_provided")
    elif payload.get("sizing_valid") is False:
        _stage("position_sizing_validation", "FAIL", "sizing_invalid")
    else:
        _stage("position_sizing_validation", "PASS")

    # 11 account
    if payload.get("account_eligible") is True:
        _stage("account_eligibility", "PASS")
    elif payload.get("account_eligible") is False:
        _stage("account_eligibility", "FAIL", "account_ineligible")
    else:
        _stage("account_eligibility", "NOT_AVAILABLE")

    # 12 broker
    if payload.get("broker_connected") is True:
        _stage("broker_connectivity", "PASS")
    elif payload.get("broker_connected") is False:
        _stage("broker_connectivity", "FAIL", "broker_disconnected")
    else:
        _stage("broker_connectivity", "NOT_AVAILABLE")

    # 13 execution eligibility
    if payload.get("trade_allowed") is True:
        _stage("execution_eligibility", "PASS", "mt5_trade_allowed_reported")
    elif payload.get("trade_allowed") is False:
        _stage("execution_eligibility", "FAIL", "trade_allowed_false")
    else:
        _stage(
            "execution_eligibility",
            "NOT_AVAILABLE",
            "verified_live_not_proof_of_trade_allowed",
        )

    # 14 duplicate
    store = get_autonomy_store()
    sig_key = str(payload.get("signal_key") or "")
    if sig_key and store.has_signal_key(sig_key):
        _stage("duplicate_signal_detection", "FAIL", "duplicate_signal_key")
    elif sig_key:
        _stage("duplicate_signal_detection", "PASS")
    else:
        _stage("duplicate_signal_detection", "NOT_AVAILABLE", "no_signal_key")

    # 15 expiry
    exp = _parse_ts(payload.get("expires_at"))
    if exp is None:
        _stage("expiry_validation", "NOT_AVAILABLE", "no_expiry")
    elif exp < datetime.now(UTC):
        _stage("expiry_validation", "FAIL", "signal_expired")
    else:
        _stage("expiry_validation", "PASS")

    # Ensure all 15 stages present
    present = {s["stage"] for s in stages}
    for name in VALIDATION_STAGES:
        if name not in present:
            _stage(name, "NOT_AVAILABLE", "not_evaluated")

    return {
        "ok": True,
        "blocked": hard_fail,
        "stages": stages,
        "hard_constraint_failed": hard_fail,
        "never_bypassed_by_frontend": True,
        "data_quality": data_quality(
            source="phase7.signal_validation",
            as_of=_now(),
        ),
        **isolation_payload(),
    }


def propose_sizing(payload: dict[str, Any]) -> dict[str, Any]:
    """Propose lot size from supplied facts only — never invent equity."""
    missing: list[str] = []
    equity = payload.get("equity")
    stop_distance = payload.get("stop_distance")
    tick_value = payload.get("tick_value")
    volume_step = payload.get("volume_step")
    min_lot = payload.get("min_lot")
    max_lot = payload.get("max_lot")
    risk_pct = payload.get("risk_pct")
    authorized_max = payload.get("authorized_max_lot")

    for field, val in (
        ("equity", equity),
        ("stop_distance", stop_distance),
        ("tick_value", tick_value),
        ("volume_step", volume_step),
        ("min_lot", min_lot),
        ("max_lot", max_lot),
        ("risk_pct", risk_pct),
    ):
        if not isinstance(val, (int, float)):
            missing.append(field)

    if missing:
        return {
            "ok": False,
            "blocked": True,
            "reason": "missing_account_or_symbol_data",
            "proposed_lot_size": None,
            "maximum_permitted_lot_size": None,
            "estimated_monetary_risk": None,
            "estimated_percentage_risk": None,
            "margin_requirement": None,
            "risk_validation": "BLOCKED",
            "calculation_evidence": ["refused_to_invent_missing_facts"],
            "missing_fields": missing,
            "never_increases_risk_limits": True,
            "data_quality": data_quality(
                source="phase7.sizing",
                as_of=_now(),
                missing_fields=missing,
            ),
            **isolation_payload(),
        }

    eq = float(equity)  # type: ignore[arg-type]
    sd = float(stop_distance)  # type: ignore[arg-type]
    tv = float(tick_value)  # type: ignore[arg-type]
    step = float(volume_step)  # type: ignore[arg-type]
    mn = float(min_lot)  # type: ignore[arg-type]
    mx = float(max_lot)  # type: ignore[arg-type]
    rp = float(risk_pct)  # type: ignore[arg-type]

    if eq <= 0 or sd <= 0 or tv <= 0 or step <= 0:
        return {
            "ok": False,
            "blocked": True,
            "reason": "non_positive_inputs",
            "proposed_lot_size": None,
            "risk_validation": "BLOCKED",
            "calculation_evidence": ["invalid_numeric_inputs"],
            **isolation_payload(),
        }

    risk_money = eq * (rp / 100.0)
    # lots ≈ risk_money / (stop_distance * tick_value) — simplified; evidence recorded
    raw_lots = risk_money / (sd * tv)
    # Round DOWN to step — never round up above permitted risk
    steps = int(raw_lots / step)
    proposed = max(mn, steps * step)
    if proposed > mx:
        proposed = mx
    if isinstance(authorized_max, (int, float)) and proposed > float(authorized_max):
        proposed = float(authorized_max)

    if proposed < mn:
        return {
            "ok": False,
            "blocked": True,
            "reason": "below_min_lot_after_risk_cap",
            "proposed_lot_size": None,
            "maximum_permitted_lot_size": mx,
            "estimated_monetary_risk": risk_money,
            "estimated_percentage_risk": rp,
            "risk_validation": "BLOCKED",
            "calculation_evidence": [
                f"raw_lots={raw_lots}",
                f"step={step}",
                "rounded_down_to_step",
            ],
            **isolation_payload(),
        }

    return {
        "ok": True,
        "blocked": False,
        "proposed_lot_size": proposed,
        "maximum_permitted_lot_size": (
            min(mx, float(authorized_max))
            if isinstance(authorized_max, (int, float))
            else mx
        ),
        "estimated_monetary_risk": risk_money,
        "estimated_percentage_risk": rp,
        "margin_requirement": payload.get("margin_requirement"),
        "risk_validation": "PASS",
        "calculation_evidence": [
            f"equity={eq}",
            f"risk_pct={rp}",
            f"stop_distance={sd}",
            f"tick_value={tv}",
            f"raw_lots={raw_lots}",
            "rounded_down_to_volume_step",
            "hard_limits_take_priority",
        ],
        "never_increases_risk_limits": True,
        "data_quality": data_quality(source="phase7.sizing", as_of=_now()),
        **isolation_payload(),
    }


def authorize_execution(payload: dict[str, Any]) -> dict[str, Any]:
    """Centralized authorization gateway — never order_send."""
    reasons: list[str] = []
    result = "BLOCKED"
    store = get_autonomy_store()
    mode = store.get_mode()["mode"]

    if not payload.get("authenticated"):
        reasons.append("unauthenticated")
        result = "BLOCKED"
    elif not payload.get("account_ownership_verified"):
        reasons.append("account_ownership_unverified")
        result = "BLOCKED"
    elif payload.get("kill_switch_armed") is True:
        reasons.append("kill_switch_armed")
        result = "BLOCKED"
    elif mode in {"OBSERVE_ONLY", "RESTRICTED_OR_DISABLED"}:
        reasons.append(f"mode_{mode.lower()}")
        result = "BLOCKED"
    elif payload.get("decision_expired") is True:
        reasons.append("decision_expired")
        result = "EXPIRED"
    elif payload.get("duplicate") is True:
        reasons.append("duplicate_order_protection")
        result = "DUPLICATE"
    elif payload.get("validation_blocked") is True:
        reasons.append("signal_validation_failed")
        result = "BLOCKED"
    elif payload.get("trade_allowed") is not True:
        # VERIFIED_LIVE is not proof — require explicit trade_allowed fact
        if payload.get("trade_allowed") is False:
            reasons.append("mt5_trade_allowed_false")
            result = "BLOCKED"
        else:
            reasons.append("trade_allowed_not_available")
            result = "NOT_AVAILABLE"
    elif mode == "ASSISTED" and payload.get("approval_status") != "Approved":
        reasons.append("assisted_requires_approval")
        result = "REQUIRES_APPROVAL"
    elif mode == "CONTROLLED_AUTOMATION" and not payload.get(
        "explicit_automation_authorization"
    ):
        reasons.append("missing_explicit_automation_authorization")
        result = "REQUIRES_APPROVAL"
    elif payload.get("strategy_approved") is not True:
        reasons.append("strategy_not_approved")
        result = "BLOCKED"
    else:
        # Eligible for existing OMS pathway preview only
        result = "AUTHORIZED"
        reasons.append("all_gates_passed_phase7_dispatch_still_false")

    if result not in AUTH_RESULTS:
        result = "BLOCKED"

    return {
        "ok": True,
        "result": result,
        "reason_codes": reasons,
        "evidence": {
            "autonomy_mode": mode,
            "trade_allowed": payload.get("trade_allowed"),
            "verified_live_display": payload.get("verified_live_display"),
            "verified_live_is_not_trade_permission": True,
            "kill_switch_armed": payload.get("kill_switch_armed"),
            "approval_status": payload.get("approval_status"),
        },
        "order_send": False,
        "phase7_live_dispatch": False,
        "authorized_is_not_live_submit": True,
        "never_force_trade_allowed": True,
        "data_quality": data_quality(
            source="phase7.execution_authorization",
            as_of=_now(),
        ),
        **isolation_payload(),
    }
