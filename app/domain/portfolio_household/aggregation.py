"""Household portfolio aggregation — honest nulls, never fabricate zeros."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.domain.portfolio_household.models import ConversionStatus, DataStatus

STALE_AFTER = timedelta(minutes=15)


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@dataclass(frozen=True, slots=True)
class PositionKey:
    account_key: str
    ticket: int


@dataclass(frozen=True, slots=True)
class PositionSlice:
    account_key: str
    broker_account_id: str | None
    broker_code: str | None
    ticket: int
    symbol: str
    side: str
    volume: Decimal
    profit: Decimal | None
    strategy: str | None = None


@dataclass(frozen=True, slots=True)
class AccountMetricSlice:
    broker_account_id: str | None
    broker_code: str | None
    broker_name: str | None
    server: str | None
    login: str | None
    currency: str | None
    data_status: DataStatus
    as_of: datetime | None
    balance: Decimal | None = None
    equity: Decimal | None = None
    margin: Decimal | None = None
    free_margin: Decimal | None = None
    used_margin: Decimal | None = None
    floating_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    daily_pnl: Decimal | None = None
    weekly_pnl: Decimal | None = None
    monthly_pnl: Decimal | None = None
    active_positions: int | None = None
    pending_orders: int | None = None
    ownership_verified: bool | None = None
    trade_allowed: bool | None = None
    conversion_status: ConversionStatus = "native_only"
    conversion_as_of: datetime | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class HouseholdTotals:
    """Totals only over accounts with measurable figures in a common currency."""

    display_currency: str | None
    conversion_status: ConversionStatus
    conversion_as_of: datetime | None
    balance: Decimal | None
    equity: Decimal | None
    margin: Decimal | None
    free_margin: Decimal | None
    used_margin: Decimal | None
    floating_pnl: Decimal | None
    realized_pnl: Decimal | None
    daily_pnl: Decimal | None
    weekly_pnl: Decimal | None
    monthly_pnl: Decimal | None
    overall_return_pct: Decimal | None
    overall_return_reason: str | None
    active_positions: int
    pending_orders: int
    connected_accounts: int
    accounts_with_metrics: int
    accounts_excluded: int


@dataclass(frozen=True, slots=True)
class HouseholdPortfolio:
    user_id: str
    as_of: datetime
    accounts: tuple[AccountMetricSlice, ...]
    positions: tuple[PositionSlice, ...]
    totals: HouseholdTotals
    methodology: dict[str, Any] = field(default_factory=dict)


def classify_status(
    *,
    has_live: bool,
    as_of: datetime | None,
    connected: bool | None,
    ownership_verified: bool | None,
    now: datetime | None = None,
) -> DataStatus:
    if ownership_verified is False:
        return "unverified"
    if has_live:
        return "live"
    if not connected and as_of is None:
        return "disconnected"
    if as_of is None:
        return "unavailable"
    clock = now or datetime.now(UTC)
    age = clock - (as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC))
    if age > STALE_AFTER:
        return "stale"
    if connected is False:
        return "disconnected"
    return "cached"


def dedupe_positions(positions: list[PositionSlice]) -> list[PositionSlice]:
    """Keep first occurrence of (account_key, ticket)."""
    seen: set[tuple[str, int]] = set()
    out: list[PositionSlice] = []
    for p in positions:
        key = (p.account_key, p.ticket)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _sum_optional(values: list[Decimal | None]) -> Decimal | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present, Decimal("0"))


def aggregate_household(
    *,
    user_id: UUID,
    accounts: list[AccountMetricSlice],
    positions: list[PositionSlice],
    display_currency: str | None = None,
    verified_fx: dict[str, Decimal] | None = None,
    fx_as_of: datetime | None = None,
    now: datetime | None = None,
) -> HouseholdPortfolio:
    """Roll up household metrics with honest nulls.

    ``verified_fx`` maps currency → rate into display_currency. Missing rate
    excludes that account from convertible totals (never invent FX).
    """
    clock = now or datetime.now(UTC)
    positions = dedupe_positions(positions)
    fx = verified_fx or {}

    convertible: list[AccountMetricSlice] = []
    excluded = 0
    for acct in accounts:
        if (
            acct.data_status in {"unavailable", "disconnected", "unverified"}
            and acct.equity is None
            and acct.balance is None
        ):
            excluded += 1
            continue
        if acct.equity is None and acct.balance is None:
            excluded += 1
            continue
        cur = (acct.currency or "").upper() or None
        if (
            display_currency
            and cur
            and cur != display_currency.upper()
            and cur not in fx
        ):
            excluded += 1
            continue
        convertible.append(acct)

    def _scaled(acct: AccountMetricSlice, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        cur = (acct.currency or "").upper()
        if not display_currency or not cur or cur == display_currency.upper():
            return value
        rate = fx.get(cur)
        if rate is None:
            return None
        return value * rate

    bal = _sum_optional([_scaled(a, a.balance) for a in convertible])
    eq = _sum_optional([_scaled(a, a.equity) for a in convertible])
    margin = _sum_optional([_scaled(a, a.margin) for a in convertible])
    free = _sum_optional([_scaled(a, a.free_margin) for a in convertible])
    used = _sum_optional([_scaled(a, a.used_margin) for a in convertible])
    floating = _sum_optional([_scaled(a, a.floating_pnl) for a in convertible])
    realized = _sum_optional([_scaled(a, a.realized_pnl) for a in convertible])
    daily = _sum_optional([_scaled(a, a.daily_pnl) for a in convertible])
    weekly = _sum_optional([_scaled(a, a.weekly_pnl) for a in convertible])
    monthly = _sum_optional([_scaled(a, a.monthly_pnl) for a in convertible])

    overall: Decimal | None = None
    overall_reason: str | None = None
    if eq is not None and bal is not None and bal > 0:
        overall = ((eq - bal) / bal) * Decimal("100")
    elif eq is None or bal is None:
        overall_reason = "incomplete_equity_or_balance"
    else:
        overall_reason = "non_positive_balance"

    conv_status: ConversionStatus = "native_only"
    if display_currency and any(
        (a.currency or "").upper() not in {"", display_currency.upper()}
        for a in convertible
    ):
        conv_status = "ok" if fx else "unavailable"
    elif display_currency:
        conv_status = "ok"

    pos_count = sum(
        (a.active_positions or 0) for a in convertible if a.active_positions is not None
    )
    if not any(a.active_positions is not None for a in convertible):
        pos_count = len(positions)
    pend_count = sum(
        (a.pending_orders or 0) for a in convertible if a.pending_orders is not None
    )

    connected = sum(1 for a in accounts if a.data_status in {"live", "cached"})

    totals = HouseholdTotals(
        display_currency=display_currency,
        conversion_status=conv_status,
        conversion_as_of=fx_as_of if conv_status == "ok" else None,
        balance=bal,
        equity=eq,
        margin=margin,
        free_margin=free,
        used_margin=used,
        floating_pnl=floating,
        realized_pnl=realized,
        daily_pnl=daily,
        weekly_pnl=weekly,
        monthly_pnl=monthly,
        overall_return_pct=overall,
        overall_return_reason=overall_reason,
        active_positions=pos_count,
        pending_orders=pend_count,
        connected_accounts=connected,
        accounts_with_metrics=len(convertible),
        accounts_excluded=excluded,
    )

    return HouseholdPortfolio(
        user_id=str(user_id),
        as_of=clock,
        accounts=tuple(accounts),
        positions=tuple(positions),
        totals=totals,
        methodology={
            "aggregation": "sum_convertible_accounts_only",
            "missing_as": "null_never_zero",
            "dedupe": "account_key+ticket",
            "stale_after_minutes": int(STALE_AFTER.total_seconds() // 60),
            "fx": "verified_rates_only",
        },
    )


def account_from_live_snapshot(
    *,
    broker_account_id: str | None,
    broker_code: str | None,
    broker_name: str | None,
    snapshot: dict[str, Any],
    ownership_verified: bool | None = True,
    trade_allowed: bool | None = None,
    realized_pnl: Decimal | None = None,
    daily_pnl: Decimal | None = None,
    weekly_pnl: Decimal | None = None,
    monthly_pnl: Decimal | None = None,
    active_positions: int | None = None,
    pending_orders: int | None = None,
    as_of: datetime | None = None,
) -> AccountMetricSlice:
    margin = _dec(snapshot.get("margin"))
    free = _dec(snapshot.get("free_margin"))
    used = None
    if margin is not None and free is not None:
        used = margin  # MT5 margin is typically used margin
    return AccountMetricSlice(
        broker_account_id=broker_account_id,
        broker_code=broker_code,
        broker_name=broker_name,
        server=str(snapshot.get("server") or "") or None,
        login=str(snapshot.get("login") or "") or None,
        currency=str(snapshot.get("currency") or "") or None,
        data_status="live",
        as_of=as_of or datetime.now(UTC),
        balance=_dec(snapshot.get("balance")),
        equity=_dec(snapshot.get("equity")),
        margin=margin,
        free_margin=free,
        used_margin=used,
        floating_pnl=_dec(snapshot.get("profit")),
        realized_pnl=realized_pnl,
        daily_pnl=daily_pnl,
        weekly_pnl=weekly_pnl,
        monthly_pnl=monthly_pnl,
        active_positions=active_positions,
        pending_orders=pending_orders,
        ownership_verified=ownership_verified,
        trade_allowed=trade_allowed,
        conversion_status="native_only",
        note=None,
    )
