"""Authoritative Gold autonomous entry contract — pre-OMS, never order_send.

QuantForg may forward XAUUSD_i to the EXISTING OMS only when this contract
returns EXECUTION_READY. It does not create a second strategy, OMS, or
Gateway path. It does not lower SCALPING_V1 floors or bypass Safety/Risk.

Execute Now is not required and is not consulted here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.profiles import SCALPING_V1
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
)
from app.domain.institutional_trading.operations.gold_execution_readiness import (
    READINESS_STAGES,
    StageStatus,
)
from app.domain.institutional_trading.operations.opportunity_starvation import (
    record_opportunity_cycle,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    evaluate_from_facts,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    evaluate_market_data_firewall,
)
from app.domain.trading.gold_only import (
    DISABLED_AUTONOMOUS_SYMBOL,
    gold_only_enabled,
    is_gold_symbol,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE, MAX_SPREAD

CANONICAL_GOLD = "XAUUSD_i"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _reasons_indicate_daily_loss(
    reasons: tuple[str, ...] | list[str] | None,
) -> bool:
    hay = " ".join(str(r).lower() for r in (reasons or ()) if str(r).strip())
    return any(
        token in hay
        for token in (
            "daily_loss_block",
            "daily_loss_exceeded",
            "daily loss",
            "max_daily_loss",
        )
    )


def _reasons_indicate_max_positions(
    reasons: tuple[str, ...] | list[str] | None,
) -> bool:
    hay = " ".join(str(r).lower() for r in (reasons or ()) if str(r).strip())
    return any(
        token in hay
        for token in (
            "max_positions_reached",
            "max positions per symbol",
            "max positions reached",
            "positions per symbol",
        )
    )


def _reasons_indicate_min_lot_exceeds_budget(
    reasons: tuple[str, ...] | list[str] | None,
) -> bool:
    hay = " ".join(str(r).lower() for r in (reasons or ()) if str(r).strip())
    return "min_lot_exceeds_risk_budget" in hay or "min lot exceeds risk" in hay


def _reasons_indicate_min_lot(reasons: tuple[str, ...] | list[str] | None) -> bool:
    hay = " ".join(str(r).lower() for r in (reasons or ()) if str(r).strip())
    return any(
        token in hay
        for token in (
            "min_lot_constraint",
            "min_lot_infeasible",
            "min_lot_exceeds_risk_budget",
            "min lot constraint",
            "min lot exceeds risk",
            "below_min_lot",
            "below broker volume_min",
            "below broker minimum",
            "minimum lot",
            "min lot",
            "below broker min",
        )
    )


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def scalping_v1_floors() -> dict[str, int]:
    """Live SCALPING_V1 floors — never invent new thresholds."""
    cfg = SCALPING_V1
    return {
        "structure": int(cfg.min_structure_score),
        "momentum": int(cfg.min_momentum_score),
        "quality": int(cfg.normal_vol.quality),
        "confidence": int(cfg.normal_vol.confidence),
        "pa_confluence": int(cfg.min_pa_confluence_score),
    }


@dataclass(frozen=True, slots=True)
class GoldExecutionFacts:
    """Already-computed cycle artefacts. This module does not fetch MT5."""

    symbol: str = ""
    direction: str = "NONE"
    action: str = "NO_TRADE"
    market_open: bool = False
    tradable: bool = False
    candles_ok: bool = True
    bid: Decimal | None = None
    ask: Decimal | None = None
    quote_age_seconds: float | None = None
    spread: Decimal | None = None
    structure_score: int | None = None
    momentum_score: int | None = None
    quality: int | None = None
    confidence: int | None = None
    pa_confluence: int | None = None
    risk_reward: Decimal | None = None
    market_regime: str | None = None
    volatility_ok: bool = True
    session_quality_ok: bool = True
    safety_allowed: bool = False
    safety_reasons: tuple[str, ...] = ()
    kill_switch: bool = False
    execution_enabled: bool = False
    auto_running: bool = False
    account_leverage: Decimal | None = None
    risk_eligible: bool = False
    risk_reasons: tuple[str, ...] = ()
    approved_lots: Decimal | None = None
    min_lot_infeasible: bool = False
    portfolio_allow: bool = True
    portfolio_reasons: tuple[str, ...] = ()
    optimizer_state: str = "NOT_RUN"
    oms_orders_allowed: bool = False
    gateway_connected: bool = False
    broker_connected: bool = False
    force_shadow: bool = False
    gold_only: bool | None = None
    opportunity_score: int | None = None
    opportunity_threshold: int | None = None
    score_breakdown: dict[str, int] | None = None
    liquidity_score: int | None = None
    spread_score: int | None = None
    mtf_alignment: int | None = None
    cycle_id: str | None = None
    snapshot_id: str | None = None
    daily_loss_exceeded: bool = False


@dataclass(frozen=True, slots=True)
class GoldExecutionContract:
    """Structured AI/decision authorization. Prose is not sufficient."""

    symbol: str
    direction: str
    signal_strength: int | None
    confidence: int | None
    quality: int | None
    structure_score: int | None
    momentum_score: int | None
    pa_confluence: int | None
    market_regime: str | None
    volatility: str
    spread: str | None
    session_quality: str
    risk_reward: str | None
    setup_state: str
    decision_state: str
    execution_readiness: str
    blocking_stage: str | None
    fault_class: str
    fault_code: str
    fault_reason: str
    next_action: str
    stages: dict[str, str]
    first_authoritative_blocker: str | None
    all_failed_conditions: tuple[str, ...]
    current_value: str | None
    required_value: str | None
    may_submit_oms: bool
    execute_now_required: bool = False
    timestamps: dict[str, str] = field(default_factory=dict)
    opportunity_score: int | None = None
    opportunity_threshold: int | None = None
    score_band: str | None = None
    score_breakdown: dict[str, int] | None = None
    trade_class: str | None = None
    trade_class_reason: str | None = None
    cycle_id: str | None = None
    snapshot_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "signal_strength": self.signal_strength,
            "confidence": self.confidence,
            "quality": self.quality,
            "structure_score": self.structure_score,
            "momentum_score": self.momentum_score,
            "pa_confluence": self.pa_confluence,
            "market_regime": self.market_regime,
            "volatility": self.volatility,
            "spread": self.spread,
            "session_quality": self.session_quality,
            "risk_reward": self.risk_reward,
            "setup_state": self.setup_state,
            "decision_state": self.decision_state,
            "execution_readiness": self.execution_readiness,
            "blocking_stage": self.blocking_stage,
            "fault_class": self.fault_class,
            "fault_code": self.fault_code,
            "fault_reason": self.fault_reason,
            "next_action": self.next_action,
            "stages": dict(self.stages),
            "first_authoritative_blocker": self.first_authoritative_blocker,
            "all_failed_conditions": list(self.all_failed_conditions),
            "current_value": self.current_value,
            "required_value": self.required_value,
            "may_submit_oms": self.may_submit_oms,
            "execute_now_required": self.execute_now_required,
            "timestamps": dict(self.timestamps),
            "opportunity_score": self.opportunity_score,
            "trade_class": self.trade_class,
            "trade_class_reason": self.trade_class_reason,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "opportunity_threshold": self.opportunity_threshold,
            "score_band": self.score_band,
            "score_breakdown": dict(self.score_breakdown or {}),
        }


def _stage_fail(
    *,
    stage: str,
    code: str,
    reason: str,
    fault_class: str,
    next_action: str,
    current: Any = None,
    required: Any = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "code": code,
        "reason": reason,
        "fault_class": fault_class,
        "next_action": next_action,
        "current": None if current is None else str(current),
        "required": None if required is None else str(required),
    }


def evaluate_gold_execution_contract(
    facts: GoldExecutionFacts,
) -> GoldExecutionContract:
    """Return EXECUTION_READY only when every authoritative stage PASSES."""
    gold_only = (
        bool(gold_only_enabled()) if facts.gold_only is None else bool(facts.gold_only)
    )
    raw_symbol = str(facts.symbol or "").strip()
    symbol = raw_symbol.upper()
    direction = str(facts.direction or "NONE").strip().upper() or "NONE"
    action = str(facts.action or "NO_TRADE").strip().upper() or "NO_TRADE"
    stages: dict[str, str] = {name: StageStatus.NOT_REACHED.value for name in READINESS_STAGES}
    failures: list[dict[str, Any]] = []
    stamps: dict[str, str] = {"signal_detected": _utc_now()}

    def mark(name: str, status: str) -> None:
        stages[name] = status

    # --- MARKET ---
    market_fail: dict[str, Any] | None = None
    apply_gold_specs = bool(gold_only or is_gold_symbol(symbol))
    if gold_only and symbol and not is_gold_symbol(symbol):
        market_fail = _stage_fail(
            stage="MARKET",
            code=DISABLED_AUTONOMOUS_SYMBOL,
            reason=f"Autonomous universe is [{CANONICAL_GOLD}] — rejected {raw_symbol or symbol}",
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
            current=raw_symbol or symbol,
            required=CANONICAL_GOLD,
        )
    elif not symbol:
        market_fail = _stage_fail(
            stage="MARKET",
            code="NOT_EXECUTABLE",
            reason=(
                "canonical symbol must be XAUUSD_i"
                if gold_only
                else "executable symbol required — missing instrument identity"
            ),
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.MARKET_CONTEXT_NOT_READY.value,
            current=raw_symbol or "NONE",
            required=CANONICAL_GOLD if gold_only else "BROKER_SYMBOL",
        )
    elif gold_only and not is_gold_symbol(symbol):
        market_fail = _stage_fail(
            stage="MARKET",
            code="MARKET_CONTEXT_NOT_READY",
            reason="canonical symbol must be XAUUSD_i",
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.MARKET_CONTEXT_NOT_READY.value,
            current=raw_symbol or "NONE",
            required=CANONICAL_GOLD,
        )
    else:
        firewall = evaluate_market_data_firewall(
            symbol=symbol,
            bid=float(facts.bid) if facts.bid is not None else None,
            ask=float(facts.ask) if facts.ask is not None else None,
            quote_age_seconds=facts.quote_age_seconds,
            market_open=bool(facts.market_open),
            symbol_valid=True,
            candles_ok=bool(facts.candles_ok),
        )
        if not firewall.allow_new_entry:
            code = str(firewall.first_blocking_gate or "STALE_QUOTE")
            if code in {"QUOTE_STALE", "MARKET_DATA_STALE"} or "STALE" in code:
                code = "STALE_QUOTE"
            market_fail = _stage_fail(
                stage="MARKET",
                code=code if code != "MARKET_CLOSED" else "MARKET_CLOSED",
                reason=firewall.detail or code,
                fault_class=(
                    FaultClass.WAIT.value
                    if code == "MARKET_CLOSED"
                    else FaultClass.HARD_BLOCK.value
                ),
                next_action=(
                    CandidateAction.MARKET_CONTEXT_NOT_READY.value
                    if code != "STALE_QUOTE"
                    else CandidateAction.FAIL_CLOSED.value
                ),
                current=firewall.quote_age_ms,
                required=firewall.required_max_age_ms,
            )
        elif not facts.tradable:
            market_fail = _stage_fail(
                stage="MARKET",
                code="SYMBOL_NOT_TRADEABLE",
                reason="broker must confirm symbol is tradable",
                fault_class=FaultClass.CANDIDATE_BLOCK.value,
                next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
            )
        elif not apply_gold_specs and (
            facts.spread is None or facts.bid is None or facts.ask is None
        ):
            market_fail = _stage_fail(
                stage="MARKET",
                code="NOT_EXECUTABLE",
                reason="non-gold instrument missing required metadata (spread/bid/ask)",
                fault_class=FaultClass.CANDIDATE_BLOCK.value,
                next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
            )
        elif (
            apply_gold_specs
            and facts.spread is not None
            and facts.spread > MAX_SPREAD
        ):
            market_fail = _stage_fail(
                stage="MARKET",
                code="SPREAD_UNACCEPTABLE",
                reason=f"spread {facts.spread} exceeds max_spread {MAX_SPREAD}",
                fault_class=FaultClass.WAIT.value,
                next_action=CandidateAction.WAIT_SAME_FOCUS.value,
                current=facts.spread,
                required=MAX_SPREAD,
            )
    if market_fail:
        mark("MARKET", StageStatus.BLOCK.value if market_fail["fault_class"] != FaultClass.WAIT.value else StageStatus.WAIT.value)
        failures.append(market_fail)
    else:
        mark("MARKET", StageStatus.PASS.value)
        stamps["setup_ready"] = _utc_now()

    # --- STRATEGY (Probability Center is the opportunity selector) ---
    verdict = evaluate_from_facts(facts)
    strategy_fail: dict[str, Any] | None = None
    if not facts.volatility_ok:
        strategy_fail = _stage_fail(
            stage="STRATEGY",
            code="VOLATILITY_REJECT",
            reason="Gold volatility policy rejected (hard market validity)",
            fault_class=FaultClass.CANDIDATE_BLOCK.value,
            next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
        )
    elif verdict.fault_code == "OPPORTUNITY_SCORE_BELOW_THRESHOLD":
        strategy_fail = _stage_fail(
            stage="STRATEGY",
            code="OPPORTUNITY_SCORE_BELOW_THRESHOLD",
            reason=verdict.fault_reason or "opportunity score below threshold",
            fault_class=FaultClass.CANDIDATE_BLOCK.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
            current=verdict.opportunity_score,
            required=verdict.threshold,
        )
    if strategy_fail:
        mark("STRATEGY", StageStatus.BLOCK.value)
        failures.append(strategy_fail)
    elif not market_fail:
        mark("STRATEGY", StageStatus.PASS.value)

    # --- DECISION ---
    # DIRECTION_NONE only when the decision engine itself produced no side.
    # action=NO_TRADE with a proven BUY/SELL is a downstream Risk/Safety hold.
    decision_fail: dict[str, Any] | None = None
    if direction not in {"BUY", "SELL"}:
        decision_fail = _stage_fail(
            stage="DECISION",
            code="DIRECTION_NONE",
            reason="direction MUST be BUY or SELL — never send when direction=NONE",
            fault_class=FaultClass.CANDIDATE_BLOCK.value,
            next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
            current=direction,
            required="BUY|SELL",
        )
    elif action in {"BUY", "SELL"} and action != direction:
        decision_fail = _stage_fail(
            stage="DECISION",
            code="ACTION_DIRECTION_MISMATCH",
            reason=f"action {action} does not match direction {direction}",
            fault_class=FaultClass.CANDIDATE_BLOCK.value,
            next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
            current=action,
            required=direction,
        )
    if decision_fail:
        mark("DECISION", StageStatus.BLOCK.value)
        failures.append(decision_fail)
    elif not market_fail and not strategy_fail:
        mark("DECISION", StageStatus.PASS.value)
        stamps["decision_ready"] = _utc_now()

    # --- SAFETY (includes leverage desk policy) ---
    safety_fail: dict[str, Any] | None = None
    lev = facts.account_leverage
    if facts.kill_switch:
        safety_fail = _stage_fail(
            stage="SAFETY",
            code="SAFETY_BLOCKED",
            reason="kill switch armed",
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
    elif not facts.execution_enabled:
        safety_fail = _stage_fail(
            stage="SAFETY",
            code="EXECUTION_DISABLED",
            reason="EXECUTION_ENABLED=false",
            fault_class=FaultClass.SYSTEM_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
    elif not facts.auto_running:
        safety_fail = _stage_fail(
            stage="SAFETY",
            code="AUTO_TRADING_NOT_RUNNING",
            reason="Auto Trading must be RUNNING for autonomous entry",
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        )
    elif not facts.safety_allowed:
        reason = "; ".join(facts.safety_reasons) or "SAFETY_BLOCKED"
        safety_fail = _stage_fail(
            stage="SAFETY",
            code="SAFETY_BLOCKED",
            reason=reason,
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
    elif apply_gold_specs and lev is not None and lev > MAX_LEVERAGE:
        safety_fail = _stage_fail(
            stage="SAFETY",
            code="LEVERAGE_POLICY_EXCEEDED",
            reason=(
                f"Account leverage exceeds desk policy "
                f"(leverage {lev} exceeds max_leverage {MAX_LEVERAGE})"
            ),
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
            current=lev,
            required=MAX_LEVERAGE,
        )
    if safety_fail:
        mark("SAFETY", StageStatus.BLOCK.value if safety_fail["fault_class"] != FaultClass.WAIT.value else StageStatus.WAIT.value)
        failures.append(safety_fail)
    elif not any((market_fail, strategy_fail, decision_fail)):
        mark("SAFETY", StageStatus.PASS.value)
        stamps["safety_pass"] = _utc_now()

    # --- RISK ---
    # Daily-loss is the session circuit-breaker. It outranks min-lot / capacity
    # so a genuine lock cannot be mislabeled MIN_LOT_CONSTRAINT. WAIT / score
    # below threshold still remain first — only TAKE proceeds toward Risk as
    # the terminal reason (promotion below).
    risk_fail: dict[str, Any] | None = None
    min_lot_blocked = bool(facts.min_lot_infeasible) or _reasons_indicate_min_lot(
        facts.risk_reasons
    )
    max_pos_blocked = _reasons_indicate_max_positions(facts.risk_reasons)
    daily_loss_blocked = _reasons_indicate_daily_loss(
        facts.risk_reasons
    ) or bool(facts.daily_loss_exceeded)
    if daily_loss_blocked:
        risk_fail = _stage_fail(
            stage="RISK",
            code="DAILY_LOSS_BLOCK",
            reason=(
                "; ".join(facts.risk_reasons)
                or "UTC daily loss exceeds hard circuit-breaker "
                f"({MAX_DAILY_LOSS_PCT}%) — wait for session reset"
            ),
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        )
        mark("RISK", StageStatus.BLOCK.value)
        failures.append(risk_fail)
    elif max_pos_blocked:
        risk_fail = _stage_fail(
            stage="RISK",
            code="MAX_POSITIONS_REACHED",
            reason=(
                "; ".join(facts.risk_reasons)
                or "Max positions per symbol — wait for close or capacity"
            ),
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        )
        mark("RISK", StageStatus.BLOCK.value)
        failures.append(risk_fail)
    elif min_lot_blocked:
        exceeds = _reasons_indicate_min_lot_exceeds_budget(facts.risk_reasons)
        lot_code = (
            "MIN_LOT_EXCEEDS_RISK_BUDGET" if exceeds else "MIN_LOT_CONSTRAINT"
        )
        risk_fail = _stage_fail(
            stage="RISK",
            code=lot_code,
            reason=(
                "; ".join(facts.risk_reasons)
                or (
                    "minimum lot exceeds configured risk budget — do not upsize"
                    if exceeds
                    else "minimum lot would violate hard max risk — do not upsize"
                )
            ),
            fault_class=FaultClass.CANDIDATE_BLOCK.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        )
        mark("RISK", StageStatus.BLOCK.value)
        mark("SIZING", StageStatus.BLOCK.value)
        failures.append(risk_fail)
    elif not facts.risk_eligible:
        from app.domain.institutional_trading.phase_a.execution_reject import (
            reasons_indicate_execution_reject_burst,
        )

        if reasons_indicate_execution_reject_burst(facts.risk_reasons):
            risk_fail = _stage_fail(
                stage="EXECUTION_REJECT_BURST",
                code="EXECUTION_REJECT_BURST",
                reason=(
                    "; ".join(facts.risk_reasons)
                    or "execution reject-burst latch is active"
                ),
                fault_class=FaultClass.HARD_BLOCK.value,
                next_action=CandidateAction.FAIL_CLOSED.value,
            )
        else:
            risk_fail = _stage_fail(
                stage="RISK",
                code="RISK_REJECTED",
                reason="; ".join(facts.risk_reasons) or "Risk must PASS",
                fault_class=FaultClass.HARD_BLOCK.value,
                next_action=CandidateAction.FAIL_CLOSED.value,
            )
        mark("RISK", StageStatus.BLOCK.value)
        failures.append(risk_fail)
    elif not any((market_fail, strategy_fail, decision_fail, safety_fail)):
        mark("RISK", StageStatus.PASS.value)
        stamps["risk_pass"] = _utc_now()

    # --- SIZING ---
    sizing_fail: dict[str, Any] | None = None
    if not min_lot_blocked and not max_pos_blocked and not daily_loss_blocked:
        lots = facts.approved_lots
        if lots is None or lots <= 0:
            sizing_fail = _stage_fail(
                stage="SIZING",
                code="SIZING_NOT_READY",
                reason="risk-approved volume is missing or zero",
                fault_class=FaultClass.CANDIDATE_BLOCK.value,
                next_action=CandidateAction.NO_EXECUTABLE_FOCUS.value,
                current=lots,
                required="> 0",
            )
            mark("SIZING", StageStatus.BLOCK.value)
            failures.append(sizing_fail)
        elif not any((market_fail, strategy_fail, decision_fail, safety_fail, risk_fail)):
            mark("SIZING", StageStatus.PASS.value)
            stamps["sizing_pass"] = _utc_now()

    # --- PORTFOLIO ---
    portfolio_fail: dict[str, Any] | None = None
    if not facts.portfolio_allow:
        portfolio_fail = _stage_fail(
            stage="PORTFOLIO",
            code="PORTFOLIO_REJECTED",
            reason="; ".join(facts.portfolio_reasons) or "portfolio rejected new XAUUSD_i exposure",
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
        mark("PORTFOLIO", StageStatus.BLOCK.value)
        failures.append(portfolio_fail)
    elif not any((market_fail, strategy_fail, decision_fail, safety_fail, risk_fail, sizing_fail)):
        mark("PORTFOLIO", StageStatus.PASS.value)
        stamps["portfolio_pass"] = _utc_now()

    # --- OPTIMIZER ---
    opt = str(facts.optimizer_state or "NOT_RUN").strip().upper()
    optimizer_fail: dict[str, Any] | None = None
    if opt in {"WAIT_BOUNDED", "WAIT_SAME_FOCUS", "WAIT"}:
        optimizer_fail = _stage_fail(
            stage="OPTIMIZER",
            code="OPTIMIZER_WAIT",
            reason="optimizer WAIT_SAME_FOCUS — do not trade",
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
            current=opt,
            required="EXECUTE_NOW",
        )
        mark("OPTIMIZER", StageStatus.WAIT.value)
        failures.append(optimizer_fail)
    elif opt == "BLOCK":
        optimizer_fail = _stage_fail(
            stage="OPTIMIZER",
            code="OPTIMIZER_BLOCK",
            reason="optimizer BLOCK — do not trade",
            fault_class=FaultClass.HARD_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
            current=opt,
            required="EXECUTE_NOW",
        )
        mark("OPTIMIZER", StageStatus.BLOCK.value)
        failures.append(optimizer_fail)
    elif opt not in {"EXECUTE_NOW", "PROCEED", "PROCEED_DEGRADED"}:
        optimizer_fail = _stage_fail(
            stage="OPTIMIZER",
            code="OPTIMIZER_NOT_READY",
            reason="optimizer must return EXECUTE_NOW before OMS",
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
            current=opt,
            required="EXECUTE_NOW",
        )
        mark("OPTIMIZER", StageStatus.WAIT.value)
        failures.append(optimizer_fail)
    elif not any(
        (
            market_fail,
            strategy_fail,
            decision_fail,
            safety_fail,
            risk_fail,
            sizing_fail,
            portfolio_fail,
        )
    ):
        mark("OPTIMIZER", StageStatus.PASS.value)
        stamps["optimizer_execute_now"] = _utc_now()

    # --- OMS / BROKER readiness (authority still the existing OMS/Gateway) ---
    oms_fail: dict[str, Any] | None = None
    if facts.force_shadow:
        oms_fail = _stage_fail(
            stage="OMS",
            code="SHADOW_NO_SUBMIT",
            reason="SHADOW mode journals only — no OMS submit",
            fault_class=FaultClass.WAIT.value,
            next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        )
        mark("OMS", StageStatus.WAIT.value)
        failures.append(oms_fail)
    elif not facts.oms_orders_allowed:
        oms_fail = _stage_fail(
            stage="OMS",
            code="OMS_NOT_READY",
            reason="OMS authorization is required",
            fault_class=FaultClass.SYSTEM_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
        mark("OMS", StageStatus.BLOCK.value)
        failures.append(oms_fail)
    elif stages.get("OPTIMIZER") == StageStatus.PASS.value:
        mark("OMS", StageStatus.PASS.value)
        stamps["oms_authorized"] = _utc_now()

    broker_fail: dict[str, Any] | None = None
    if not facts.gateway_connected:
        broker_fail = _stage_fail(
            stage="BROKER",
            code="GATEWAY_UNAVAILABLE",
            reason="Gateway unavailable",
            fault_class=FaultClass.SYSTEM_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
        mark("BROKER", StageStatus.BLOCK.value)
        failures.append(broker_fail)
    elif not facts.broker_connected:
        broker_fail = _stage_fail(
            stage="BROKER",
            code="MT5_UNAVAILABLE",
            reason="MT5 is not connected",
            fault_class=FaultClass.SYSTEM_BLOCK.value,
            next_action=CandidateAction.FAIL_CLOSED.value,
        )
        mark("BROKER", StageStatus.BLOCK.value)
        failures.append(broker_fail)
    elif stages.get("OMS") == StageStatus.PASS.value:
        mark("BROKER", StageStatus.PASS.value)

    first = failures[0] if failures else None
    if failures:
        kill = next(
            (
                f
                for f in failures
                if str(f.get("code") or "") == "SAFETY_BLOCKED"
                and "kill" in str(f.get("reason") or "").lower()
            ),
            None,
        )
        daily = next(
            (f for f in failures if str(f.get("code") or "") == "DAILY_LOSS_BLOCK"),
            None,
        )
        burst = next(
            (
                f
                for f in failures
                if str(f.get("code") or "") in {
                    "EXECUTION_REJECT_BURST",
                    "REJECT_BURST",
                }
            ),
            None,
        )
        if kill is not None:
            first = kill
        elif burst is not None:
            # Burst is the execution circuit breaker. Do not hide it behind
            # DIRECTION_NONE from a pause demotion.
            first = burst
        elif daily is not None and not facts.kill_switch:
            # Daily loss is authoritative for TAKE → Risk. It must not steal
            # WAIT / opportunity-below-threshold / DIRECTION_NONE, and must not
            # relabel independent Safety (MT5 AutoTrading, EXECUTION_ENABLED).
            prior_stage = str((first or {}).get("stage") or "").upper()
            prior_reason = str((first or {}).get("reason") or "")
            if prior_stage in {"", "RISK", "SIZING", "OMS", "BROKER"}:
                first = daily
            elif prior_stage == "SAFETY" and _reasons_indicate_daily_loss(
                (prior_reason,)
            ):
                first = daily
    all_pass = first is None
    may_submit = all_pass and not facts.force_shadow
    if may_submit:
        decision_state = DecisionState.EXECUTION_READY.value
        readiness = DecisionState.EXECUTION_READY.value
        setup_state = DecisionState.EXECUTION_READY.value
        fault_class = FaultClass.NONE.value
        fault_code = "NONE"
        fault_reason = "EXECUTION_READY"
        next_action = CandidateAction.CONTINUE.value
        blocking = None
    else:
        decision_state = (
            DecisionState.MARKET_CONTEXT_NOT_READY.value
            if first and first["code"] in {"MARKET_CONTEXT_NOT_READY", "MARKET_CLOSED"}
            else (
                DecisionState.SETUP_NOT_READY.value
                if first and first["code"] in {
                    "SETUP_NOT_READY",
                    "OPPORTUNITY_SCORE_BELOW_THRESHOLD",
                }
                else (
                    DecisionState.NO_EXECUTABLE_FOCUS.value
                    if first and first["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
                    else (
                        DecisionState.HARD_BLOCK.value
                        if first and first["fault_class"] == FaultClass.HARD_BLOCK.value
                        else (
                            DecisionState.SYSTEM_BLOCK.value
                            if first and first["fault_class"] == FaultClass.SYSTEM_BLOCK.value
                            else DecisionState.WAITING.value
                        )
                    )
                )
            )
        )
        if first and first["code"] == "STALE_QUOTE":
            decision_state = DecisionState.HARD_BLOCK.value
        if first and first["code"] == "LEVERAGE_POLICY_EXCEEDED":
            decision_state = DecisionState.HARD_BLOCK.value
        if first and first["code"] in {
            "MIN_LOT_CONSTRAINT",
            "MIN_LOT_INFEASIBLE",
            "MIN_LOT_RISK_INFEASIBLE",
            "MIN_LOT_EXCEEDS_RISK_BUDGET",
        }:
            decision_state = DecisionState.CANDIDATE_BLOCK.value
        readiness = "NOT_READY"
        setup_state = decision_state
        fault_class = str(first["fault_class"] if first else FaultClass.WAIT.value)
        fault_code = str(first["code"] if first else "NOT_READY")
        fault_reason = str(first["reason"] if first else "not ready")
        next_action = str(first["next_action"] if first else CandidateAction.WAIT_SAME_FOCUS.value)
        blocking = str(first["stage"] if first else "MARKET")

    display_symbol = CANONICAL_GOLD if (gold_only or is_gold_symbol(symbol)) else (raw_symbol or symbol)
    from app.domain.institutional_trading.operations.trade_classifier import (
        classify_trade,
    )

    classified = classify_trade(
        opportunity_score=int(verdict.opportunity_score),
        direction=direction,
        confidence=facts.confidence,
        structure=facts.structure_score,
        risk_reward=facts.risk_reward,
        regime=facts.market_regime,
        mtf_alignment=facts.mtf_alignment,
        execution_quality=facts.spread_score,
        hard_market_invalid=bool(
            market_fail
            and market_fail.get("fault_class") == FaultClass.HARD_BLOCK.value
        ),
        hard_invalid_reason=(
            str(market_fail["reason"]) if market_fail else None
        ),
        cycle_id=facts.cycle_id,
        snapshot_id=facts.snapshot_id,
    )
    contract = GoldExecutionContract(
        symbol=display_symbol if gold_only else (raw_symbol or symbol),
        direction=direction,
        signal_strength=facts.quality,
        confidence=facts.confidence,
        quality=facts.quality,
        structure_score=facts.structure_score,
        momentum_score=facts.momentum_score,
        pa_confluence=facts.pa_confluence,
        market_regime=facts.market_regime,
        volatility="PASS" if facts.volatility_ok else "BLOCK",
        spread=str(facts.spread) if facts.spread is not None else None,
        session_quality="PASS" if facts.session_quality_ok else "WAIT",
        risk_reward=str(facts.risk_reward) if facts.risk_reward is not None else None,
        setup_state=setup_state,
        decision_state=decision_state,
        execution_readiness=readiness,
        blocking_stage=blocking,
        fault_class=fault_class,
        fault_code=fault_code,
        fault_reason=fault_reason,
        next_action=next_action,
        stages=stages,
        first_authoritative_blocker=fault_reason if not may_submit else None,
        all_failed_conditions=tuple(str(f["reason"]) for f in failures),
        current_value=None if first is None else first.get("current"),
        required_value=None if first is None else first.get("required"),
        may_submit_oms=may_submit,
        execute_now_required=False,
        timestamps=stamps,
        opportunity_score=verdict.opportunity_score,
        opportunity_threshold=verdict.threshold,
        score_band=verdict.score_band,
        score_breakdown=dict(verdict.score_breakdown),
        trade_class=classified.trade_class.value,
        trade_class_reason=classified.reason,
        cycle_id=facts.cycle_id,
        snapshot_id=facts.snapshot_id,
    )
    record_opportunity_cycle(
        opportunity_score=verdict.opportunity_score,
        threshold=int(verdict.threshold or OPPORTUNITY_SCORE_THRESHOLD),
        score_breakdown=dict(verdict.score_breakdown),
        direction=direction,
        first_blocking_gate=None if may_submit else contract.fault_code,
        fault_code=contract.fault_code,
        fault_reason=contract.fault_reason,
        eligible=bool(verdict.eligible),
        hard_block=contract.fault_class == FaultClass.HARD_BLOCK.value,
        execution_ready=bool(may_submit),
    )
    return contract


def facts_from_cycle(
    *,
    snapshot: Any,
    account: Any,
    decision: Any,
    optimizer: dict[str, Any] | None,
    execution_enabled: bool,
    force_shadow: bool,
    gateway_connected: bool,
    broker_connected: bool,
    symbol_tradable: bool,
    auto_running: bool,
    kill_switch: bool,
    oms_orders_allowed: bool,
    safety_allowed: bool,
    safety_reasons: tuple[str, ...] = (),
    portfolio_allow: bool = True,
    portfolio_reasons: tuple[str, ...] = (),
    last_ai_score: dict[str, Any] | None = None,
    daily_loss_exceeded: bool = False,
) -> GoldExecutionFacts:
    """Map existing ITE artefacts into the contract facts object."""
    factors = {}
    confluence = getattr(decision, "confluence", None)
    if confluence is not None:
        factors = dict(getattr(confluence, "factors", None) or {})
    elig = getattr(decision, "eligibility", None)
    reasons = tuple(getattr(decision, "risk_reasons", ()) or ())
    elig_reasons = tuple(getattr(elig, "rejection_reasons", ()) or ()) if elig else ()
    min_lot = _reasons_indicate_min_lot(elig_reasons + reasons)
    opt_state = "NOT_RUN"
    if isinstance(optimizer, dict):
        opt_state = str(
            optimizer.get("final_state") or optimizer.get("recommendation") or "NOT_RUN"
        )
    spread = getattr(snapshot, "spread", None)
    bid = getattr(account, "bid", None)
    ask = getattr(account, "ask", None)
    if bid is None:
        bid = getattr(snapshot, "bid", None)
    if ask is None:
        ask = getattr(snapshot, "ask", None)
    ai = last_ai_score if isinstance(last_ai_score, dict) else {}
    breakdown = ai.get("score_breakdown") if isinstance(ai.get("score_breakdown"), dict) else None
    return GoldExecutionFacts(
        symbol=str(getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "") or ""),
        direction=str(
            getattr(getattr(decision, "direction", None), "value", None)
            or getattr(decision, "direction", None)
            or "NONE"
        ),
        action=str(
            getattr(getattr(decision, "action", None), "value", None)
            or getattr(decision, "action", None)
            or "NO_TRADE"
        ),
        market_open=bool(getattr(account, "market_open", False)),
        tradable=bool(symbol_tradable),
        candles_ok=True,
        bid=_as_decimal(bid),
        ask=_as_decimal(ask),
        quote_age_seconds=getattr(account, "quote_age_seconds", None),
        spread=_as_decimal(spread),
        structure_score=_as_int(
            factors.get("structure_score")
            or getattr(snapshot, "structure_score", None)
        ),
        momentum_score=_as_int(
            factors.get("momentum_score")
            or getattr(snapshot, "momentum_score", None)
        ),
        quality=_as_int(getattr(decision, "quality", None)),
        confidence=_as_int(getattr(decision, "confidence", None)),
        pa_confluence=_as_int(
            factors.get("pa_confluence") or getattr(snapshot, "pa_confluence", None)
        ),
        risk_reward=_as_decimal(getattr(decision, "estimated_rr", None)),
        market_regime=str(getattr(snapshot, "market_regime", "") or "") or None,
        volatility_ok=True,
        session_quality_ok=True,
        safety_allowed=bool(safety_allowed),
        safety_reasons=tuple(str(r) for r in safety_reasons if r),
        kill_switch=bool(kill_switch),
        execution_enabled=bool(execution_enabled),
        auto_running=bool(auto_running),
        account_leverage=_as_decimal(getattr(account, "leverage", None)),
        risk_eligible=bool(getattr(elig, "eligible", False)) if elig is not None else False,
        risk_reasons=tuple(dict.fromkeys((*reasons, *elig_reasons))),
        approved_lots=_as_decimal(getattr(decision, "approved_lots", None)),
        min_lot_infeasible=min_lot,
        portfolio_allow=bool(portfolio_allow),
        portfolio_reasons=tuple(str(r) for r in portfolio_reasons if r),
        optimizer_state=opt_state,
        oms_orders_allowed=bool(oms_orders_allowed),
        gateway_connected=bool(gateway_connected),
        broker_connected=bool(broker_connected),
        force_shadow=bool(force_shadow),
        opportunity_score=_as_int(
            ai.get("opportunity_score")
            or getattr(decision, "opportunity_score", None)
        ),
        opportunity_threshold=_as_int(
            ai.get("opportunity_threshold")
        ) or OPPORTUNITY_SCORE_THRESHOLD,
        score_breakdown=breakdown,
        liquidity_score=_as_int(ai.get("liquidity")),
        spread_score=_as_int(ai.get("spread_score")),
        mtf_alignment=_as_int(
            (ai.get("factors") or {}).get("mtf")
            if isinstance(ai.get("factors"), dict)
            else None
        ),
        cycle_id=(
            str(ai.get("cycle_id") or "") or None
        ),
        snapshot_id=(
            str(ai.get("snapshot_id") or "") or None
        ),
        daily_loss_exceeded=bool(daily_loss_exceeded),
    )
