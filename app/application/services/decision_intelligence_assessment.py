"""Decision Center Risk/Safety handoff — assess when runnable; never order_send.

Decision Intelligence Center used to consume caller-supplied booleans only.
When those were omitted, waterfall stayed NOT_ASSESSED even after signal /
strategy / regime / confidence had already passed.

This module is the authoritative advisory handoff:

MARKET/STRATEGY/DECISION evidence
  → RiskEngine.evaluate (same engine as ITE pipeline)
  → ExecutionPolicy safety (same desk policy as Execution Safety)
  → Decision Center waterfall

It never calls OMS, never force-executes, never bypasses a FAIL, and never
turns NOT_ASSESSED into PASS. Gold-only. Stale/non-Gold live artefacts are
ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import RiskDecision
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    display_autonomous_symbol,
    is_gold_symbol,
)

AssessmentState = Literal["PASS", "FAIL", "NOT_ASSESSED"]
LIVE_FACTS_MAX_AGE_SECONDS = 180.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class EngineGate:
    """One engine assessment. ``passed`` is None only when NOT_ASSESSED."""

    state: AssessmentState
    passed: bool | None
    reason: str
    source: str
    missing: tuple[str, ...] = ()
    evaluated_at: str = ""
    symbol: str = CANONICAL_GOLD_BROKER_DISPLAY

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "passed": self.passed,
            "reason": self.reason,
            "source": self.source,
            "missing": list(self.missing),
            "evaluated_at": self.evaluated_at,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class GoldAssessmentFacts:
    """Inputs required to *run* Risk/Safety. Missing fields → NOT_ASSESSED."""

    symbol: str = CANONICAL_GOLD_BROKER_DISPLAY
    side: str = "buy"
    equity: Decimal | None = None
    free_margin: Decimal | None = None
    leverage: Decimal | None = None
    spread: Decimal | None = None
    entry_price: Decimal | None = None
    stop_distance: Decimal | None = None
    atr: Decimal | None = None
    consecutive_losses: int = 0
    daily_pnl: Decimal | None = None
    peak_equity: Decimal | None = None
    kill_switch: bool | None = None
    market_open: bool | None = None
    as_of: datetime | None = None


def facts_from_payload(payload: dict[str, Any]) -> GoldAssessmentFacts:
    """Map evaluate payload fields. Does not invent equity/leverage/price."""
    side = str(payload.get("side") or "buy").strip().lower()
    if side not in {"buy", "sell"}:
        side = "buy"
    raw_symbol = str(payload.get("symbol") or CANONICAL_GOLD_BROKER_DISPLAY)
    equity = _as_decimal(payload.get("equity"))
    peak = _as_decimal(payload.get("peak_equity")) or equity
    price = _as_decimal(payload.get("entry_price"))
    if price is None:
        price = _as_decimal(payload.get("price"))
    return GoldAssessmentFacts(
        symbol=raw_symbol,
        side=side,
        equity=equity,
        free_margin=_as_decimal(payload.get("free_margin")) or equity,
        leverage=_as_decimal(payload.get("leverage")),
        spread=_as_decimal(payload.get("spread")),
        entry_price=price,
        stop_distance=_as_decimal(payload.get("stop_distance")),
        atr=_as_decimal(payload.get("atr")),
        consecutive_losses=int(payload.get("consecutive_losses") or 0),
        daily_pnl=_as_decimal(payload.get("daily_pnl")),
        peak_equity=peak,
        kill_switch=(
            bool(payload["kill_switch"])
            if payload.get("kill_switch") is not None
            else None
        ),
        market_open=(
            bool(payload["market_open"])
            if payload.get("market_open") is not None
            else None
        ),
        as_of=_utc_now(),
    )


def _age_seconds(as_of: datetime | None) -> float | None:
    if as_of is None:
        return None
    stamp = as_of
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0.0, (_utc_now() - stamp.astimezone(UTC)).total_seconds())


def collect_live_gold_facts() -> GoldAssessmentFacts | None:
    """Read-only Gold context from ITE last cycle / control plane. Never OMS."""
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
    except Exception:
        return None

    runtime = None
    try:
        runtime = get_ite_runtime()
    except Exception:
        runtime = None

    kill: bool | None = None
    try:
        plane = get_control_plane()
        kill = bool(getattr(plane, "kill_switch_armed", False))
    except Exception:
        kill = None

    decision = getattr(runtime, "_last_decision", None) if runtime is not None else None
    account = (
        getattr(runtime, "_last_account_risk", None) if runtime is not None else None
    )
    symbol = str(getattr(decision, "symbol", "") or "")
    if account is not None and not symbol:
        symbol = CANONICAL_GOLD_BROKER_DISPLAY
    if symbol and not is_gold_symbol(symbol):
        return None
    as_of = getattr(decision, "as_of", None)
    age = _age_seconds(as_of if isinstance(as_of, datetime) else None)
    if age is not None and age > LIVE_FACTS_MAX_AGE_SECONDS:
        return None

    bid = _as_decimal(getattr(account, "bid", None)) if account is not None else None
    ask = _as_decimal(getattr(account, "ask", None)) if account is not None else None
    mid = None
    if account is not None:
        mid = _as_decimal(getattr(account, "mid_price", None))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / Decimal("2")
    spread = None
    if bid is not None and ask is not None and ask >= bid:
        spread = ask - bid

    return GoldAssessmentFacts(
        symbol=symbol or CANONICAL_GOLD_BROKER_DISPLAY,
        side="buy",
        equity=(
            _as_decimal(getattr(account, "equity", None))
            if account is not None
            else None
        ),
        free_margin=(
            _as_decimal(getattr(account, "free_margin", None))
            if account is not None
            else None
        ),
        leverage=(
            _as_decimal(getattr(account, "leverage", None))
            if account is not None
            else None
        ),
        spread=spread,
        entry_price=mid,
        stop_distance=None,
        atr=(
            _as_decimal(getattr(account, "atr", None))
            if account is not None
            else None
        ),
        consecutive_losses=(
            int(getattr(account, "consecutive_losses", 0) or 0)
            if account is not None
            else 0
        ),
        daily_pnl=(
            _as_decimal(getattr(account, "daily_pnl", None))
            if account is not None
            else None
        ),
        peak_equity=(
            _as_decimal(getattr(account, "peak_equity", None))
            if account is not None
            else None
        ),
        kill_switch=kill,
        market_open=(
            bool(getattr(account, "market_open", True)) if account is not None else None
        ),
        as_of=as_of if isinstance(as_of, datetime) else _utc_now(),
    )


def merge_facts(
    payload_facts: GoldAssessmentFacts, live: GoldAssessmentFacts | None
) -> GoldAssessmentFacts:
    """Payload wins when set; live Gold fills gaps. Non-Gold live is ignored."""
    if live is None:
        return payload_facts
    if live.symbol and not is_gold_symbol(live.symbol):
        return payload_facts
    return GoldAssessmentFacts(
        symbol=payload_facts.symbol or live.symbol,
        side=payload_facts.side,
        equity=(
            payload_facts.equity if payload_facts.equity is not None else live.equity
        ),
        free_margin=(
            payload_facts.free_margin
            if payload_facts.free_margin is not None
            else live.free_margin
        ),
        leverage=(
            payload_facts.leverage
            if payload_facts.leverage is not None
            else live.leverage
        ),
        spread=(
            payload_facts.spread if payload_facts.spread is not None else live.spread
        ),
        entry_price=(
            payload_facts.entry_price
            if payload_facts.entry_price is not None
            else live.entry_price
        ),
        stop_distance=(
            payload_facts.stop_distance
            if payload_facts.stop_distance is not None
            else live.stop_distance
        ),
        atr=payload_facts.atr if payload_facts.atr is not None else live.atr,
        consecutive_losses=payload_facts.consecutive_losses,
        daily_pnl=(
            payload_facts.daily_pnl
            if payload_facts.daily_pnl is not None
            else live.daily_pnl
        ),
        peak_equity=(
            payload_facts.peak_equity
            if payload_facts.peak_equity is not None
            else live.peak_equity
        ),
        kill_switch=(
            payload_facts.kill_switch
            if payload_facts.kill_switch is not None
            else live.kill_switch
        ),
        market_open=(
            payload_facts.market_open
            if payload_facts.market_open is not None
            else live.market_open
        ),
        as_of=payload_facts.as_of or live.as_of,
    )


def _stamp(facts: GoldAssessmentFacts) -> str:
    as_of = facts.as_of or _utc_now()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    return as_of.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _gold_gate(facts: GoldAssessmentFacts) -> EngineGate | None:
    symbol = facts.symbol or CANONICAL_GOLD_BROKER_DISPLAY
    if not is_gold_symbol(symbol):
        return EngineGate(
            state="NOT_ASSESSED",
            passed=None,
            reason=(
                f"Decision Center is gold-only — refusing non-Gold symbol {symbol}"
            ),
            source="gold_only_filter",
            missing=("gold_symbol",),
            evaluated_at=_stamp(facts),
            symbol=display_autonomous_symbol(symbol),
        )
    return None


def assess_risk_engine(facts: GoldAssessmentFacts) -> EngineGate:
    """Invoke the production RiskEngine when prerequisites exist."""
    refused = _gold_gate(facts)
    if refused is not None:
        return refused

    missing: list[str] = []
    if facts.equity is None or facts.equity <= 0:
        missing.append("equity")
    if facts.entry_price is None or facts.entry_price <= 0:
        missing.append("entry_price")
    symbol = display_autonomous_symbol(facts.symbol)
    if missing:
        return EngineGate(
            state="NOT_ASSESSED",
            passed=None,
            reason=(
                "Risk Engine not assessed — missing "
                + ", ".join(missing)
                + " (fail closed, never bypassed)"
            ),
            source="prerequisites",
            missing=tuple(missing),
            evaluated_at=_stamp(facts),
            symbol=symbol,
        )

    from app.application.services.institutional_decision_pipeline import (
        risk_config_from_ite,
    )
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    equity = facts.equity
    assert equity is not None
    entry = facts.entry_price
    assert entry is not None
    leverage_int = 100
    if facts.leverage is not None and facts.leverage > 0:
        leverage_int = int(facts.leverage)

    engine = RiskEngine(config=risk_config_from_ite(DEFAULT_ITE_CONFIG))
    check = RiskCheckInput(
        user_id=uuid4(),
        request_id=f"di-risk-{uuid4().hex[:12]}",
        symbol=CANONICAL_GOLD_BROKER_DISPLAY,
        side=facts.side,
        stop_loss_distance=facts.stop_distance,
        atr=facts.atr,
        entry_price=entry,
        spread=facts.spread,
        consecutive_losses=facts.consecutive_losses,
        session_allowed=None,
    )
    free_margin = facts.free_margin if facts.free_margin is not None else equity
    account = AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=free_margin,
        margin_level=Decimal("0"),
        profit=facts.daily_pnl or Decimal("0"),
        leverage=leverage_int,
        currency="USD",
        server="decision-intelligence",
    )
    peak = facts.peak_equity if facts.peak_equity is not None else equity
    daily = facts.daily_pnl if facts.daily_pnl is not None else Decimal("0")
    try:
        assessment = engine.evaluate(
            check,
            account=account,
            positions=[],
            peak_equity=peak,
            daily_pnl=daily,
        )
    except Exception as exc:
        return EngineGate(
            state="FAIL",
            passed=False,
            reason=f"Risk Engine failed before completion: {exc}",
            source="risk_engine.evaluate",
            evaluated_at=_stamp(facts),
            symbol=symbol,
        )
    allowed = assessment.decision is not RiskDecision.REJECT
    reason = (
        "Risk Engine ALLOW"
        if allowed
        else ("; ".join(assessment.reasons) or "Risk Engine did not ALLOW")
    )
    return EngineGate(
        state="PASS" if allowed else "FAIL",
        passed=allowed,
        reason=reason,
        source="risk_engine.evaluate",
        evaluated_at=_stamp(facts),
        symbol=symbol,
    )


def assess_safety_engine(facts: GoldAssessmentFacts) -> EngineGate:
    """Invoke ExecutionPolicy (Safety Engine) when prerequisites exist."""
    refused = _gold_gate(facts)
    if refused is not None:
        return refused

    missing: list[str] = []
    if facts.spread is None:
        missing.append("spread")
    if facts.leverage is None:
        missing.append("leverage")
    symbol = display_autonomous_symbol(facts.symbol)
    if missing:
        return EngineGate(
            state="NOT_ASSESSED",
            passed=None,
            reason=(
                "Safety Engine not assessed — missing "
                + ", ".join(missing)
                + " (fail closed, never bypassed)"
            ),
            source="prerequisites",
            missing=tuple(missing),
            evaluated_at=_stamp(facts),
            symbol=symbol,
        )

    policy = ExecutionPolicy()
    spread = facts.spread
    leverage = facts.leverage
    assert spread is not None
    assert leverage is not None
    reasons: list[str] = []
    if not policy.allows_symbol(CANONICAL_GOLD_BROKER_DISPLAY):
        reasons.append(f"symbol {CANONICAL_GOLD_BROKER_DISPLAY} not on whitelist")
    if not policy.within_trading_hours():
        reasons.append("outside configured trading hours")
    if spread > policy.max_spread:
        reasons.append(f"spread {spread} exceeds max_spread {policy.max_spread}")
    if leverage > policy.max_leverage:
        reasons.append(
            f"leverage {leverage} exceeds max_leverage {policy.max_leverage}"
        )
    if facts.kill_switch is True:
        reasons.append("kill switch armed")
    if facts.market_open is False:
        reasons.append("market closed")

    allowed = len(reasons) == 0
    return EngineGate(
        state="PASS" if allowed else "FAIL",
        passed=allowed,
        reason=("Safety Engine ALLOW" if allowed else "; ".join(reasons)),
        source="execution_policy.evaluate",
        evaluated_at=_stamp(facts),
        symbol=symbol,
    )


def resolve_claimed_bool(
    *,
    engine: EngineGate,
    claimed: bool | None,
) -> bool | None:
    """Engine result wins when assessed. Claimed True cannot bypass FAIL.

    When the engine is NOT_ASSESSED, a caller-supplied bool is treated as a
    pre-computed assessment from another producer (ITE tests / replay). It is
    never invented: None stays None.
    """
    if engine.state == "PASS":
        return True
    if engine.state == "FAIL":
        return False
    return claimed


def assess_decision_center_engines(
    payload: dict[str, Any],
    *,
    live: GoldAssessmentFacts | None = None,
    use_live: bool = True,
) -> tuple[GoldAssessmentFacts, EngineGate, EngineGate]:
    """Run Risk + Safety for Decision Center evaluate (advisory, no OMS)."""
    payload_facts = facts_from_payload(payload)
    live_facts = live
    if use_live and live_facts is None:
        try:
            live_facts = collect_live_gold_facts()
        except Exception:
            live_facts = None
    facts = merge_facts(payload_facts, live_facts)
    risk = assess_risk_engine(facts)
    safety = assess_safety_engine(facts)
    return facts, risk, safety
