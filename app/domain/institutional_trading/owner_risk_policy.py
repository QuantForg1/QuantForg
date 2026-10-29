"""Owner capital-protection policy for live new entries.

One source for the two hard limits:
- planned stop-loss loss on a new entry is at most 9% of live equity
- daily loss above 19% of day-start equity halts new entries

Exact 9% and exact 19% are allowed. The next step above either limit is not.
There is no fixed dollar stop budget and no independent weekly, monthly, or
peak-drawdown entry halt in this module.
"""

from __future__ import annotations

from decimal import Decimal

MAX_PLANNED_RISK_PCT = Decimal("9.0")
MAX_DAILY_LOSS_PCT = Decimal("19.0")

_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")


def planned_risk_cap_usd(equity: Decimal) -> Decimal:
    """Maximum planned stop-loss loss for one new entry, in account currency."""
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    return (eq * MAX_PLANNED_RISK_PCT / _HUNDRED).quantize(_CENTS)


def day_start_equity(
    *,
    equity: Decimal,
    daily_pnl: Decimal,
    balance: Decimal | None = None,
) -> Decimal:
    """Session baseline before today's realized trade P/L.

    ``daily_pnl`` is realized session trade cash only. Deposits are excluded
    by the caller. When balance is positive, day-start is balance minus that
    P/L. Otherwise day-start is current equity minus that P/L.
    """
    eq = Decimal(str(equity or 0))
    pnl = Decimal(str(daily_pnl or 0))
    bal = Decimal(str(balance)) if balance is not None else Decimal("0")
    start = (bal - pnl) if bal > 0 else (eq - pnl)
    if start <= 0:
        return Decimal("0")
    return start


def daily_loss_pct(
    *,
    equity: Decimal,
    daily_pnl: Decimal,
    balance: Decimal | None = None,
) -> Decimal:
    """Loss from day-start equity to current equity, as a percent.

    Current equity includes floating loss when it is below balance.
    Flat or profitable sessions return 0. A non-positive day-start returns 0
    so a missing baseline cannot look like a breached cap.
    """
    eq = Decimal(str(equity or 0))
    start = day_start_equity(equity=eq, daily_pnl=daily_pnl, balance=balance)
    if start <= 0:
        return Decimal("0")
    loss = start - eq
    if loss <= 0:
        return Decimal("0")
    return (loss / start * _HUNDRED).quantize(_CENTS)


def daily_loss_exceeded(
    *,
    equity: Decimal,
    daily_pnl: Decimal,
    balance: Decimal | None,
    max_daily_loss_pct: Decimal,
) -> bool:
    """True only when measured loss is strictly above the cap."""
    cap = Decimal(str(max_daily_loss_pct or 0))
    if cap <= 0:
        return False
    return daily_loss_pct(equity=equity, daily_pnl=daily_pnl, balance=balance) > cap
