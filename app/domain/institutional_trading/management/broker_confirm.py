"""Broker SL/TP confirmation after OMS modify — never invent success.

When confirmation is unavailable or the broker stop is worse than planned,
callers must not mark Break-Even / trail success locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BrokerPositionSnapshot:
    """Authoritative broker row for one ticket (or unavailable)."""

    ticket: int
    available: bool
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    volume: Decimal | None = None
    reason: str = ""


class BrokerPositionReader(Protocol):
    """Read a live MT5 position without submitting orders."""

    def read_position(self, ticket: int, *, symbol: str) -> BrokerPositionSnapshot: ...


@dataclass(frozen=True, slots=True)
class SlConfirmResult:
    confirmed: bool
    reason: str
    broker_sl: Decimal | None = None
    broker_tp: Decimal | None = None


def _tol(price_tolerance: Decimal) -> Decimal:
    t = Decimal(str(price_tolerance or 0))
    return t if t > 0 else Decimal("0.02")


def stop_meets_plan(
    *,
    side: str,
    planned_sl: Decimal,
    broker_sl: Decimal,
    price_tolerance: Decimal = Decimal("0.02"),
) -> bool:
    """True when broker SL matches plan or is more protective."""
    tol = _tol(price_tolerance)
    side_l = (side or "").lower()
    if side_l == "buy":
        # BUY: higher SL is better; allow tiny float/tick shortfall.
        return broker_sl + tol >= planned_sl
    if side_l == "sell":
        return broker_sl - tol <= planned_sl
    return False


def confirm_sl_modification(
    *,
    side: str,
    planned_sl: Decimal,
    planned_tp: Decimal | None,
    snapshot: BrokerPositionSnapshot,
    price_tolerance: Decimal = Decimal("0.02"),
    require_tp_when_planned: bool = False,
) -> SlConfirmResult:
    """Compare planned SL(/TP) to a broker re-read.

    Unavailable / missing SL ⇒ not confirmed (never invent success).
    """
    if not snapshot.available:
        return SlConfirmResult(
            confirmed=False,
            reason=snapshot.reason or "broker position re-read unavailable",
            broker_sl=snapshot.stop_loss,
            broker_tp=snapshot.take_profit,
        )
    if snapshot.stop_loss is None or snapshot.stop_loss <= 0:
        return SlConfirmResult(
            confirmed=False,
            reason="broker stop missing or non-positive after modify",
            broker_sl=snapshot.stop_loss,
            broker_tp=snapshot.take_profit,
        )
    if not stop_meets_plan(
        side=side,
        planned_sl=planned_sl,
        broker_sl=snapshot.stop_loss,
        price_tolerance=price_tolerance,
    ):
        return SlConfirmResult(
            confirmed=False,
            reason=(
                f"broker SL {snapshot.stop_loss} does not meet planned "
                f"{planned_sl} for {side}"
            ),
            broker_sl=snapshot.stop_loss,
            broker_tp=snapshot.take_profit,
        )
    if (
        require_tp_when_planned
        and planned_tp is not None
        and planned_tp > 0
        and snapshot.take_profit is not None
        and snapshot.take_profit > 0
    ):
        tol = _tol(price_tolerance)
        if abs(snapshot.take_profit - planned_tp) > tol:
            return SlConfirmResult(
                confirmed=False,
                reason=(
                    f"broker TP {snapshot.take_profit} diverges from planned "
                    f"{planned_tp}"
                ),
                broker_sl=snapshot.stop_loss,
                broker_tp=snapshot.take_profit,
            )
    return SlConfirmResult(
        confirmed=True,
        reason="broker SL confirmed",
        broker_sl=snapshot.stop_loss,
        broker_tp=snapshot.take_profit,
    )
