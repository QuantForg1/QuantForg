"""Live Auto Trading certification — fail-closed; never fabricates broker fills.

Certification is NOT claimed unless a real OMS/broker trade evidence record
is supplied. Mode transitions (SHADOW→CANARY→LIVE) remain operator-only via
the ops control plane — this module never changes execution mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    AutoTradeSafetyResult,
    evaluate_auto_trade_safety,
)
from app.domain.trading.gold_only import GOLD_SYMBOL

# Demo certification hard limits (Step 2)
DEMO_CERT_VOLUME = Decimal("0.01")
DEMO_CERT_MAX_POSITIONS = 1


@dataclass(frozen=True, slots=True)
class LiveCertCondition:
    key: str
    label: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class LiveCertChecklistResult:
    """Step 1 — verify all live conditions. Any fail → STOP."""

    ready: bool
    conditions: tuple[LiveCertCondition, ...]
    failed_reasons: tuple[str, ...]
    account_type_required: str = "demo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "failed_reasons": list(self.failed_reasons),
            "conditions": [c.to_dict() for c in self.conditions],
            "account_type_required": self.account_type_required,
            "demo_volume": str(DEMO_CERT_VOLUME),
            "demo_max_positions": DEMO_CERT_MAX_POSITIONS,
        }


@dataclass(frozen=True, slots=True)
class LiveTradeEvidence:
    """Real broker trade facts only — never invent these fields."""

    broker: str
    account_type: str  # Demo | Live
    symbol: str
    volume: Decimal
    ticket: int
    deal: int
    entry: Decimal
    exit: Decimal | None
    profit_loss: Decimal | None
    execution_latency_ms: float
    margin_used: Decimal | None
    risk_pct: Decimal
    audit_id: str
    position_closed: bool
    history_recorded: bool
    analytics_recorded: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "account_type": self.account_type,
            "symbol": self.symbol,
            "volume": str(self.volume),
            "ticket": self.ticket,
            "deal": self.deal,
            "entry": str(self.entry),
            "exit": str(self.exit) if self.exit is not None else None,
            "profit_loss": (
                str(self.profit_loss) if self.profit_loss is not None else None
            ),
            "execution_latency_ms": round(self.execution_latency_ms, 3),
            "margin_used": (
                str(self.margin_used) if self.margin_used is not None else None
            ),
            "risk_pct": str(self.risk_pct),
            "audit_id": self.audit_id,
            "position_closed": self.position_closed,
            "history_recorded": self.history_recorded,
            "analytics_recorded": self.analytics_recorded,
        }


@dataclass(frozen=True, slots=True)
class LiveTradeStageResult:
    stage: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class LiveCertificationReport:
    """Issued only when a complete real trade path is verified."""

    certified: bool
    status: str  # CERTIFIED | NOT_CERTIFIED | STOPPED
    checklist: LiveCertChecklistResult
    stages: tuple[LiveTradeStageResult, ...] = ()
    trade: LiveTradeEvidence | None = None
    failure_reason: str | None = None
    auto_trading_disabled_on_failure: bool = False
    mode_auto_switched: bool = False  # must always remain False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "certified": self.certified,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "auto_trading_disabled_on_failure": self.auto_trading_disabled_on_failure,
            "mode_auto_switched": self.mode_auto_switched,
            "created_at": self.created_at.isoformat(),
            "checklist": self.checklist.to_dict(),
            "stages": [s.to_dict() for s in self.stages],
            "trade": self.trade.to_dict() if self.trade is not None else None,
            "operator_controls": {
                "shadow_to_live": "operator_only",
                "auto_trading_enable": "operator_explicit",
                "execution_enabled": "operator_env_explicit",
                "never_automatic_mode_switch": True,
            },
        }


def evaluate_live_cert_checklist(
    *,
    facts: AutoTradeLiveFacts,
    policy: AutoTradePolicy | None = None,
    mt5_logged_in: bool = False,
    exposure_pass: bool = False,
    drawdown_pass: bool = False,
    account_is_demo: bool = False,
) -> LiveCertChecklistResult:
    """Step 1 checklist. Fail-closed — any miss → ready=False."""

    policy = policy or AutoTradePolicy(
        enabled=True,
        max_open_positions=DEMO_CERT_MAX_POSITIONS,
        allowed_symbols=(GOLD_SYMBOL,),
    )
    # Force demo cert policy limits into safety evaluation context
    constrained = AutoTradePolicy(
        enabled=policy.enabled,
        max_open_positions=min(policy.max_open_positions, DEMO_CERT_MAX_POSITIONS),
        risk_per_trade_pct=policy.risk_per_trade_pct,
        max_daily_loss_pct=policy.max_daily_loss_pct,
        allowed_sessions=policy.allowed_sessions,
        allowed_symbols=policy.allowed_symbols or (GOLD_SYMBOL,),
        max_spread=policy.max_spread,
        news_filter_enabled=policy.news_filter_enabled,
    )
    safety: AutoTradeSafetyResult = evaluate_auto_trade_safety(constrained, facts)

    by_key = {c.key: c for c in safety.conditions}
    conditions: list[LiveCertCondition] = []

    def map_cond(key: str, label: str, *, extra_pass: bool | None = None) -> None:
        base = by_key.get(key)
        passed = bool(base.passed) if base is not None else False
        detail = base.detail if base is not None else f"{label} not evaluated"
        if extra_pass is not None:
            passed = passed and extra_pass
            if not extra_pass and not detail:
                detail = f"{label} failed"
        conditions.append(
            LiveCertCondition(key=key, label=label, passed=passed, detail=detail)
        )

    map_cond("gateway_connected", "Gateway Connected")
    map_cond("broker_connected", "Broker Connected")
    conditions.append(
        LiveCertCondition(
            key="mt5_logged_in",
            label="MT5 Logged In",
            passed=mt5_logged_in and facts.broker_connected,
            detail=(
                ""
                if mt5_logged_in and facts.broker_connected
                else "MT5 terminal is not logged in"
            ),
        )
    )
    map_cond("market_data_live", "Market Data Live")
    map_cond("mt5_autotrading", "AutoTrading Enabled")
    map_cond("risk_engine", "Risk Engine PASS")
    map_cond("margin_available", "Margin Available")
    conditions.append(
        LiveCertCondition(
            key="exposure_pass",
            label="Exposure PASS",
            passed=exposure_pass,
            detail="" if exposure_pass else "Exposure check did not PASS",
        )
    )
    map_cond("daily_loss", "Daily Loss PASS")
    conditions.append(
        LiveCertCondition(
            key="drawdown_pass",
            label="Drawdown PASS",
            passed=drawdown_pass,
            detail="" if drawdown_pass else "Drawdown protection did not PASS",
        )
    )
    map_cond("max_spread", "Spread PASS")
    map_cond("trading_session", "Session PASS")
    map_cond("news_filter", "News Filter PASS")
    map_cond("execution_enabled", "Execution Enabled")
    conditions.append(
        LiveCertCondition(
            key="demo_account",
            label="Demo account required first",
            passed=account_is_demo,
            detail=(
                ""
                if account_is_demo
                else "Demo account required before LIVE certification"
            ),
        )
    )
    conditions.append(
        LiveCertCondition(
            key="demo_size",
            label="Demo size 0.01 lot / max 1 position",
            passed=constrained.max_open_positions <= DEMO_CERT_MAX_POSITIONS,
            detail=(
                ""
                if constrained.max_open_positions <= DEMO_CERT_MAX_POSITIONS
                else "Demo certification requires max 1 open position"
            ),
        )
    )

    failed = tuple(
        dict.fromkeys(
            (c.detail if c.detail else f"{c.label} failed")
            for c in conditions
            if not c.passed
        )
    )
    return LiveCertChecklistResult(
        ready=all(c.passed for c in conditions),
        conditions=tuple(conditions),
        failed_reasons=failed,
        account_type_required="demo",
    )


def validate_demo_trade_evidence(trade: LiveTradeEvidence) -> tuple[bool, str]:
    """Reject fabricated / incomplete trade evidence."""
    if trade.account_type.lower() != "demo":
        return False, f"Account type must be Demo first (got {trade.account_type})"
    if trade.volume != DEMO_CERT_VOLUME:
        return False, f"Demo volume must be {DEMO_CERT_VOLUME} (got {trade.volume})"
    if trade.ticket <= 0 or trade.deal <= 0:
        return False, "Ticket/deal must be real broker identifiers (>0)"
    if not trade.position_closed:
        return False, "Position close stage incomplete"
    if not trade.history_recorded:
        return False, "History stage incomplete"
    if not trade.analytics_recorded:
        return False, "Analytics stage incomplete"
    if not trade.audit_id.strip():
        return False, "Audit ID missing"
    if not trade.broker.strip():
        return False, "Broker missing"
    return True, ""


COMPLETE_TRADE_STAGES: tuple[str, ...] = (
    "signal",
    "risk_check",
    "order_check",
    "order_send",
    "broker_fill",
    "position_open",
    "position_close",
    "execution_audit",
    "history",
    "analytics",
)


def build_stage_results(
    *,
    completed: dict[str, bool],
    details: dict[str, str] | None = None,
) -> tuple[LiveTradeStageResult, ...]:
    details = details or {}
    rows: list[LiveTradeStageResult] = []
    for stage in COMPLETE_TRADE_STAGES:
        ok = bool(completed.get(stage, False))
        rows.append(
            LiveTradeStageResult(
                stage=stage,
                passed=ok,
                detail=details.get(stage, "" if ok else f"{stage} not completed"),
            )
        )
    return tuple(rows)


def certify_or_stop(
    *,
    checklist: LiveCertChecklistResult,
    stages: tuple[LiveTradeStageResult, ...] = (),
    trade: LiveTradeEvidence | None = None,
) -> LiveCertificationReport:
    """
    Produce a certification report.

    - If checklist not ready → STOPPED (no certification).
    - If trade evidence missing/invalid → NOT_CERTIFIED.
    - CERTIFIED only when checklist + all stages + valid demo evidence.
    Never sets mode_auto_switched=True.
    """
    if not checklist.ready:
        reason = "; ".join(checklist.failed_reasons) or "Live conditions failed"
        return LiveCertificationReport(
            certified=False,
            status="STOPPED",
            checklist=checklist,
            stages=stages,
            trade=None,
            failure_reason=reason,
            auto_trading_disabled_on_failure=True,
            mode_auto_switched=False,
        )

    if trade is None:
        return LiveCertificationReport(
            certified=False,
            status="NOT_CERTIFIED",
            checklist=checklist,
            stages=stages,
            trade=None,
            failure_reason=(
                "No real broker trade evidence — certification requires a "
                "completed Demo fill (ticket/deal). Trades are not simulated."
            ),
            auto_trading_disabled_on_failure=True,
            mode_auto_switched=False,
        )

    ok, why = validate_demo_trade_evidence(trade)
    if not ok:
        return LiveCertificationReport(
            certified=False,
            status="NOT_CERTIFIED",
            checklist=checklist,
            stages=stages,
            trade=trade,
            failure_reason=why,
            auto_trading_disabled_on_failure=True,
            mode_auto_switched=False,
        )

    if not stages:
        stages = build_stage_results(completed={})
    if not all(s.passed for s in stages):
        failed = [s.stage for s in stages if not s.passed]
        return LiveCertificationReport(
            certified=False,
            status="NOT_CERTIFIED",
            checklist=checklist,
            stages=stages,
            trade=trade,
            failure_reason=f"Incomplete trade path stages: {', '.join(failed)}",
            auto_trading_disabled_on_failure=True,
            mode_auto_switched=False,
        )

    return LiveCertificationReport(
        certified=True,
        status="CERTIFIED",
        checklist=checklist,
        stages=stages,
        trade=trade,
        failure_reason=None,
        auto_trading_disabled_on_failure=False,
        mode_auto_switched=False,
    )
