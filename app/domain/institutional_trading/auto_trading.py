"""Auto Trading safety gate — fail-closed; never bypasses risk / broker / margin."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class AutoTradePolicy:
    """Operator-configurable auto-trade controls (persisted on ops plane)."""

    enabled: bool = False
    max_open_positions: int = 1
    risk_per_trade_pct: Decimal = Decimal("1.0")
    max_daily_loss_pct: Decimal = Decimal("3.0")
    allowed_sessions: tuple[str, ...] = (
        "london",
        "new_york",
        "london_ny_overlap",
    )
    allowed_symbols: tuple[str, ...] = ("XAUUSD",)
    max_spread: Decimal = Decimal("2.00")
    news_filter_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_open_positions": self.max_open_positions,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "allowed_sessions": list(self.allowed_sessions),
            "allowed_symbols": list(self.allowed_symbols),
            "max_spread": str(self.max_spread),
            "news_filter_enabled": self.news_filter_enabled,
        }


@dataclass(frozen=True, slots=True)
class AutoTradeLiveFacts:
    """Live connectivity / account / market facts for the safety gate."""

    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: tuple[str, ...] = ()
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    spread: Decimal | None = None
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False
    emergency_stop: bool = False
    ops_mode: str = "SHADOW"
    execution_enabled: bool = False


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

    def add(key: str, label: str, passed: bool, detail: str = "") -> None:
        conditions.append(
            AutoTradeCondition(key=key, label=label, passed=passed, detail=detail)
        )

    add(
        "auto_trading_toggle",
        "Auto Trading ON",
        policy.enabled,
        "Operator Auto Trading toggle is OFF" if not policy.enabled else "",
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
        "EXECUTION_ENABLED=false — OMS not permitted"
        if not facts.execution_enabled
        else "",
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
        facts.risk_engine_pass,
        (
            "; ".join(facts.risk_engine_reasons)
            if facts.risk_engine_reasons
            else "Risk Engine did not PASS"
        )
        if not facts.risk_engine_pass
        else "",
    )
    add(
        "account_trading",
        "Account trading enabled",
        facts.account_trading_enabled,
        "Account trading is disabled" if not facts.account_trading_enabled else "",
    )
    add(
        "mt5_autotrading",
        "AutoTrading enabled in MT5 terminal",
        facts.mt5_autotrading_enabled,
        (
            "AutoTrading is disabled in MetaTrader 5"
            if not facts.mt5_autotrading_enabled
            else ""
        ),
    )
    symbol_u = (facts.symbol or "").strip().upper()
    allowed_syms = {s.strip().upper() for s in policy.allowed_symbols if s.strip()}
    symbol_allowed = symbol_u in allowed_syms if allowed_syms else False
    add(
        "symbol_allowed",
        "Symbol allowed",
        symbol_allowed,
        (
            f"Symbol {symbol_u or '—'} not in allowed list"
            if not symbol_allowed
            else ""
        ),
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
    add(
        "margin_available",
        "Margin available",
        facts.margin_available,
        "Insufficient free margin" if not facts.margin_available else "",
    )
    add(
        "broker_restrictions",
        "No broker restrictions",
        facts.no_broker_restrictions,
        "Broker restrictions block trading" if not facts.no_broker_restrictions else "",
    )
    add(
        "daily_loss",
        "Daily loss limit OK",
        not facts.daily_loss_exceeded,
        "Maximum daily loss exceeded" if facts.daily_loss_exceeded else "",
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
    session_ok = session_key in allowed_sessions if allowed_sessions else False
    add(
        "trading_session",
        "Allowed trading session",
        session_ok,
        f"Session '{session_key or '—'}' not allowed" if not session_ok else "",
    )
    spread_ok = facts.spread is None or facts.spread <= policy.max_spread
    add(
        "max_spread",
        "Maximum spread",
        spread_ok,
        (
            f"Spread {facts.spread} exceeds max {policy.max_spread}"
            if not spread_ok
            else ""
        ),
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
