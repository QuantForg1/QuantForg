"""Auto Trading safety gate — fail-closed; never bypasses risk / broker / margin."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT

AutoTradeRunState = Literal["off", "running", "paused", "stopped"]


def allowlist_matches(symbol: str, allowed: set[str] | frozenset[str]) -> bool:
    """Desk-code aware: allowlist XAUUSD matches broker XAUUSD_I.

    Delegates to the canonical execution-universe identity matcher.
    """
    from app.domain.trading.execution_universe import execution_symbol_allowed

    if not allowed:
        return False
    return execution_symbol_allowed(symbol, allowed)


def prefer_allowlisted_handoff(
    symbols: Sequence[str] | Iterable[str],
    allowed: Sequence[str] | set[str] | frozenset[str] | None,
) -> list[str]:
    """Stable partition: desk-allowlisted symbols first, others retained after.

    Does not remove non-allowlisted symbols from analysis handoff — Safety still
    blocks them. Preferring allowlisted desks avoids burning cycles on known
    SAFETY_BLOCKED crosses before USD majors that can size on micro equity.
    """
    ordered = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not ordered:
        return []
    allowed_set = {
        str(a).strip().upper() for a in (allowed or ()) if str(a).strip()
    }
    if not allowed_set:
        return ordered
    primary: list[str] = []
    secondary: list[str] = []
    seen: set[str] = set()
    for sym in ordered:
        if sym in seen:
            continue
        seen.add(sym)
        if allowlist_matches(sym, allowed_set):
            primary.append(sym)
        else:
            secondary.append(sym)
    return primary + secondary

_VALID_RUN_STATES: frozenset[str] = frozenset({"off", "running", "paused", "stopped"})


def normalize_run_state(
    value: str | None, *, enabled: bool | None = None
) -> AutoTradeRunState:
    """Normalize operator run state. Unknown values fail closed to off."""
    raw = (value or "").strip().lower()
    if raw in _VALID_RUN_STATES:
        # Legacy callers set enabled=True without run_state (defaults to off).
        if enabled is True and raw == "off":
            return "running"
        if enabled is False and raw in {"running", "paused"}:
            return "off"
        return raw  # type: ignore[return-value]
    if enabled is True:
        return "running"
    return "off"


@dataclass(frozen=True, slots=True)
class AutoTradePolicy:
    """Operator-configurable auto-trade controls (persisted on ops plane)."""

    enabled: bool = False
    run_state: AutoTradeRunState = "off"
    max_open_positions: int = 1
    risk_per_trade_pct: Decimal = Decimal("1.0")
    max_daily_loss_pct: Decimal = MAX_DAILY_LOSS_PCT
    allowed_sessions: tuple[str, ...] = (
        "sydney",
        "tokyo",
        "london",
        "new_york",
        "london_ny_overlap",
    )
    allowed_symbols: tuple[str, ...] = ("XAUUSD",)
    max_spread: Decimal = Decimal("2.00")
    news_filter_enabled: bool = False
    trading_mode: str = "scalping"  # scalping | swing | alpha
    compounding_enabled: bool = False
    alpha_engine_enabled: bool = False

    def __post_init__(self) -> None:
        from app.domain.trading.gold_only import (
            autonomous_execution_symbols,
            gold_only_enabled,
        )
        from app.domain.trading.xauusd_specs import coerce_max_spread

        object.__setattr__(self, "max_spread", coerce_max_spread(self.max_spread))
        mode = (self.trading_mode or "scalping").strip().lower()
        if mode not in {"swing", "scalping", "alpha"}:
            mode = "scalping"
        object.__setattr__(self, "trading_mode", mode)
        from app.domain.trading.execution_universe import (
            broker_discovered_enabled,
            execution_universe_fail_closed,
        )

        if execution_universe_fail_closed():
            object.__setattr__(self, "allowed_symbols", ())
        elif gold_only_enabled() or broker_discovered_enabled():
            object.__setattr__(
                self, "allowed_symbols", autonomous_execution_symbols()
            )
        else:
            cleaned = tuple(
                s.strip().upper() for s in self.allowed_symbols if s and str(s).strip()
            )
            object.__setattr__(self, "allowed_symbols", cleaned)

    def to_dict(self) -> dict[str, Any]:
        from app.domain.trading.gold_only import gold_only_diagnostics

        state = normalize_run_state(self.run_state, enabled=self.enabled)
        payload = {
            "enabled": self.enabled,
            "run_state": state,
            "max_open_positions": self.max_open_positions,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "allowed_sessions": list(self.allowed_sessions),
            "allowed_symbols": list(self.allowed_symbols),
            "max_spread": str(self.max_spread),
            "news_filter_enabled": self.news_filter_enabled,
            "trading_mode": self.trading_mode,
            "compounding_enabled": self.compounding_enabled,
            "alpha_engine_enabled": self.alpha_engine_enabled
            or self.trading_mode == "alpha",
            "may_open_new_trades": state == "running",
            "may_manage_positions": state in {"running", "paused"},
        }
        payload.update(gold_only_diagnostics())
        return payload


@dataclass(frozen=True, slots=True)
class AutoTradeLiveFacts:
    """Live connectivity / account / market facts for the safety gate."""

    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: tuple[str, ...] = ()
    risk_engine_evaluated: bool = True
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    account_flags_evaluated: bool = True
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    margin_evaluated: bool = True
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    session_evaluated: bool = True
    # None = unknown (UTC classifier). True/False = broker symbol session truth.
    broker_session_open: bool | None = None
    session_source: str = "utc_classifier"
    spread: Decimal | None = None
    spread_evaluated: bool = True
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False
    daily_pnl_verified: bool = True
    emergency_stop: bool = False
    ops_mode: str = "SHADOW"
    execution_enabled: bool = False
    # Status polls: unknown trade-context must not invent FAIL.
    status_snapshot: bool = False
    # Phase 73 live-trading authorization. UNSET skips the overlay (unit tests
    # of the auto-trade gate). The control plane always injects the real state.
    live_trading_state: str = "UNSET"


@dataclass(frozen=True, slots=True)
class AutoTradeCondition:
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
class AutoTradeSafetyResult:
    """Verdict for whether the strategy engine may auto-submit."""

    allowed: bool
    status: str  # Enabled | Disabled
    conditions: tuple[AutoTradeCondition, ...] = ()
    failed_reasons: tuple[str, ...] = ()
    policy: AutoTradePolicy = field(default_factory=AutoTradePolicy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "failed_reasons": list(self.failed_reasons),
            "conditions": [c.to_dict() for c in self.conditions],
            "policy": self.policy.to_dict(),
        }


def evaluate_auto_trade_safety(
    policy: AutoTradePolicy,
    facts: AutoTradeLiveFacts,
) -> AutoTradeSafetyResult:
    """Fail-closed evaluation. Any failed condition → do not trade."""

    conditions: list[AutoTradeCondition] = []
    run_state = normalize_run_state(policy.run_state, enabled=policy.enabled)

    def add(key: str, label: str, passed: bool, detail: str = "") -> None:
        conditions.append(
            AutoTradeCondition(key=key, label=label, passed=passed, detail=detail)
        )

    add(
        "auto_trading_toggle",
        "Auto Trading ON",
        run_state in {"running", "paused"},
        (
            "Operator Auto Trading is OFF"
            if run_state == "off"
            else ("Auto Trading is STOPPED" if run_state == "stopped" else "")
        ),
    )
    add(
        "auto_trading_run_state",
        "Auto Trading RUNNING",
        run_state == "running",
        (
            (
                "Auto Trading is PAUSED — no new trades; existing positions still managed"  # noqa: E501
                if run_state == "paused"
                else (
                    "Auto Trading is STOPPED — automation fully disabled"
                    if run_state == "stopped"
                    else (
                        "Auto Trading is OFF — no automatic trades"
                        if run_state == "off"
                        else f"Auto Trading state is {run_state}"
                    )
                )
            )
            if run_state != "running"
            else ""
        ),
    )
    add(
        "emergency_stop",
        "Emergency STOP disarmed",
        not facts.emergency_stop,
        "Emergency STOP (kill switch) is armed" if facts.emergency_stop else "",
    )
    mode_ok = facts.ops_mode.upper() in {"CANARY", "LIVE"}
    add(
        "ops_mode",
        "Ops mode CANARY or LIVE",
        mode_ok,
        f"Ops mode is {facts.ops_mode} (SHADOW journals only)" if not mode_ok else "",
    )
    add(
        "execution_enabled",
        "Account execution enabled (EXECUTION_ENABLED)",
        facts.execution_enabled,
        (
            "EXECUTION_ENABLED=false — OMS not permitted"
            if not facts.execution_enabled
            else ""
        ),
    )
    add(
        "gateway_connected",
        "MT5 Gateway connected",
        facts.gateway_connected,
        "MT5 Gateway not connected" if not facts.gateway_connected else "",
    )
    add(
        "broker_connected",
        "Broker connected",
        facts.broker_connected,
        "Broker / MT5 not connected" if not facts.broker_connected else "",
    )
    add(
        "market_data_live",
        "Market data live",
        facts.market_data_live,
        "Market data is not live" if not facts.market_data_live else "",
    )
    add(
        "risk_engine",
        "Risk Engine PASS",
        (
            True
            if (facts.status_snapshot and not facts.risk_engine_evaluated)
            else facts.risk_engine_pass
        ),
        (
            (
                "; ".join(facts.risk_engine_reasons)
                if facts.risk_engine_reasons
                else (
                    "Risk Engine not evaluated — no pending auto-trade decision"
                    if facts.status_snapshot and not facts.risk_engine_evaluated
                    else "Risk Engine did not PASS"
                )
            )
            if not (
                facts.risk_engine_pass
                or (facts.status_snapshot and not facts.risk_engine_evaluated)
            )
            else (
                "; ".join(facts.risk_engine_reasons)
                if facts.status_snapshot and facts.risk_engine_reasons
                else ""
            )
        ),
    )
    account_ok = (
        True
        if (facts.status_snapshot and not facts.account_flags_evaluated)
        else facts.account_trading_enabled
    )
    add(
        "account_trading",
        "Account trading enabled",
        account_ok,
        (
            (
                "Account trading flags not reported by gateway — not blocking status"
                if facts.status_snapshot and not facts.account_flags_evaluated
                else (
                    "Account trading is disabled"
                    if not facts.account_trading_enabled
                    else ""
                )
            )
            if not account_ok
            or (facts.status_snapshot and not facts.account_flags_evaluated)
            else ""
        ),
    )
    mt5_at_ok = (
        True
        if (facts.status_snapshot and not facts.account_flags_evaluated)
        else facts.mt5_autotrading_enabled
    )
    add(
        "mt5_autotrading",
        "AutoTrading enabled in MT5 terminal",
        mt5_at_ok,
        (
            (
                "MT5 AutoTrading flag not reported by gateway — not blocking status"
                if facts.status_snapshot and not facts.account_flags_evaluated
                else (
                    "AutoTrading is disabled in MetaTrader 5"
                    if not facts.mt5_autotrading_enabled
                    else ""
                )
            )
            if not mt5_at_ok
            or (facts.status_snapshot and not facts.account_flags_evaluated)
            else ""
        ),
    )
    symbol_u = (facts.symbol or "").strip().upper()
    allowed_syms = {s.strip().upper() for s in policy.allowed_symbols if s.strip()}
    mode = (policy.trading_mode or "scalping").strip().lower()

    # Scalping/alpha multi-asset: dynamic scan universe owns membership.
    # Stale ops plane allowed_symbols must not reject post-strategy handoff
    # (same class of bug as portfolio_scanner universe gate). Broker
    # tradable check below remains mandatory. Gold-only still enforced.
    if mode in {"scalping", "alpha"}:
        from app.domain.trading.gold_only import (
            gold_only_enabled,
            is_gold_symbol,
        )

        if gold_only_enabled():
            symbol_allowed = is_gold_symbol(symbol_u)
        elif allowed_syms and len(allowed_syms) >= 2:
            # Operator Symbol Management / multi-symbol allowlist owns membership.
            # Desk-aware so configured XAUUSD authorizes catalogue XAUUSD_I.
            symbol_allowed = allowlist_matches(symbol_u, allowed_syms)
        else:
            # Dynamic discovery path when no operator-managed multi-symbol list.
            symbol_allowed = bool(symbol_u)
    else:
        symbol_allowed = (
            allowlist_matches(symbol_u, allowed_syms) if allowed_syms else False
        )
    add(
        "symbol_allowed",
        "Symbol allowed",
        symbol_allowed,
        (f"Symbol {symbol_u or '—'} not in allowed list" if not symbol_allowed else ""),
    )
    add(
        "symbol_tradable",
        "Symbol tradable",
        facts.symbol_tradable,
        (
            f"Symbol {symbol_u or '—'} is not tradable"
            if not facts.symbol_tradable
            else ""
        ),
    )
    margin_ok = (
        True
        if (facts.status_snapshot and not facts.margin_evaluated)
        else facts.margin_available
    )
    add(
        "margin_available",
        "Margin available",
        margin_ok,
        (
            (
                "Free margin not sampled — not blocking status"
                if facts.status_snapshot and not facts.margin_evaluated
                else ("Insufficient free margin" if not facts.margin_available else "")
            )
            if not margin_ok or (facts.status_snapshot and not facts.margin_evaluated)
            else ""
        ),
    )
    add(
        "broker_restrictions",
        "No broker restrictions",
        facts.no_broker_restrictions,
        "Broker restrictions block trading" if not facts.no_broker_restrictions else "",
    )
    from app.domain.institutional_trading.risk_lock_override import (
        risk_lock_override_enabled,
    )

    daily_override = bool(facts.daily_loss_exceeded and risk_lock_override_enabled())
    add(
        "daily_loss",
        "Daily loss limit OK",
        (not facts.daily_loss_exceeded) or daily_override,
        (
            "TEST MODE — daily loss lock overridden"
            if daily_override
            else ("Maximum daily loss exceeded" if facts.daily_loss_exceeded else "")
        ),
    )
    add(
        "daily_pnl_verified",
        "Daily P/L verified",
        bool(facts.daily_pnl_verified),
        (
            "Daily P/L unavailable — verifying"
            if not facts.daily_pnl_verified
            else ""
        ),
    )
    opens_ok = facts.open_positions < policy.max_open_positions
    add(
        "max_open_positions",
        "Maximum open positions",
        opens_ok,
        (
            f"Open positions {facts.open_positions} at max "
            f"{policy.max_open_positions}"
            if not opens_ok
            else ""
        ),
    )
    session_key = (facts.session or "").strip().lower()
    allowed_sessions = {s.strip().lower() for s in policy.allowed_sessions if s.strip()}
    if facts.status_snapshot and not facts.session_evaluated:
        session_ok = True
        session_detail = "Trading session not evaluated — no pending auto-trade"
    else:
        from app.domain.institutional_trading.operations.broker_session_truth import (
            SESSION_STATE_INCONSISTENCY,
            build_broker_session_snapshot,
        )

        resolved = build_broker_session_snapshot(
            utc_session=session_key,
            broker_open=facts.broker_session_open,
            trade_mode="",
            trade_allowed=facts.symbol_tradable if facts.broker_session_open else None,
        )
        if facts.broker_session_open is True:
            session_ok = True
            session_detail = (
                f"{SESSION_STATE_INCONSISTENCY}: UTC '{session_key}' vs broker OPEN"
                if resolved.inconsistency
                else ""
            )
        elif facts.broker_session_open is False:
            session_ok = False
            session_detail = (
                f"BROKER_SESSION_CLOSED (utc='{session_key or '—'}')"
            )
        else:
            session_ok = session_key in allowed_sessions if allowed_sessions else False
            session_detail = (
                f"Session '{session_key or '—'}' not allowed" if not session_ok else ""
            )
    add(
        "trading_session",
        "Allowed trading session",
        session_ok,
        session_detail,
    )
    if facts.status_snapshot and not facts.spread_evaluated:
        spread_ok = True
        spread_detail = "Spread not sampled — not blocking status"
    else:
        spread_ok = facts.spread is not None and facts.spread <= policy.max_spread
        spread_detail = (
            "Spread unavailable — fail-closed"
            if facts.spread is None
            else (
                f"Spread {facts.spread} exceeds max {policy.max_spread}"
                if not spread_ok
                else ""
            )
        )
    add(
        "max_spread",
        "Maximum spread",
        spread_ok,
        spread_detail,
    )
    if policy.news_filter_enabled:
        news_ok = not facts.news_blocked
        add(
            "news_filter",
            "News filter clear",
            news_ok,
            (facts.news_reason or "News blackout active") if not news_ok else "",
        )
    else:
        add(
            "news_filter",
            "News filter",
            True,
            "News filter OFF — not blocking",
        )

    lt_state = str(facts.live_trading_state or "UNSET").strip().upper()
    if lt_state and lt_state != "UNSET":
        live_ok = lt_state in {"ENABLED", "LIVE_ENABLED"}
        add(
            "live_trading_state",
            "Live trading ENABLED",
            live_ok,
            (
                f"LIVE TRADING is {lt_state} — new orders blocked"
                if not live_ok
                else ""
            ),
        )

    failed_reasons = tuple(
        dict.fromkeys(
            (c.detail if c.detail else f"{c.label} failed")
            for c in conditions
            if not c.passed
        )
    )
    allowed = all(c.passed for c in conditions)
    return AutoTradeSafetyResult(
        allowed=allowed,
        status="Enabled" if allowed else "Disabled",
        conditions=tuple(conditions),
        failed_reasons=failed_reasons,
        policy=policy,
    )


# Risk-category conditions must not abort BUY/SELL/sniper/TAKE recording.
# They still block OMS. Kill switch, MT5 AutoTrading, connectivity remain Safety.
_SCAN_CONTINUE_CONDITION_KEYS = frozenset(
    {
        "daily_loss",
        "max_open_positions",
        "risk_engine",
        "margin_available",
        "live_trading_state",
    }
)


def safety_blocks_decision(result: AutoTradeSafetyResult) -> bool:
    """True when Safety/operator/connectivity should abort before Decision.

    Daily-loss / max-positions / risk-engine failures keep scanning and can
    still produce TAKE; OMS remains blocked at Risk.
    """
    if result.allowed:
        return False
    failed = [c for c in result.conditions if not c.passed]
    if not failed:
        return True
    return any(c.key not in _SCAN_CONTINUE_CONDITION_KEYS for c in failed)


def daily_loss_is_blocking(result: AutoTradeSafetyResult) -> bool:
    return any(c.key == "daily_loss" and not c.passed for c in result.conditions)
