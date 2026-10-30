"""Whether broker-minimum volume fits a small account.

The stop, lot, and broker specification are inputs. This module does not
shrink a valid stop, raise the lot, or treat unknown commission as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MAX_LOT,
    OWNER_MAX_PLANNED_RISK_PCT,
    declared_commission,
    planned_risk_usd,
    price_unit_value,
    resolve_entry_commission,
)

_CENT = Decimal("0.01")
_PCT = Decimal("100")

# Closed XAUUSD M1 ATR14, spread, and contract specification observed on the
# attached account at 2026-10-30T13:48:03Z. Slippage is the 0.010 buffer the
# OMS used on risk rejects. Commission was not declared. These figures are a
# snapshot, not a fresh quote and not a certification that a trade fits.
OBSERVED_AT = "2026-10-30T13:48:03Z"
OBSERVED_M1_ATR = Decimal("4.371428571428571")
OBSERVED_STOP_DISTANCE = OBSERVED_M1_ATR  # 1.00 x ATR; structure may be wider
OBSERVED_SPREAD = Decimal("0.424")
OBSERVED_SLIPPAGE = Decimal("0.010")
OBSERVED_CONTRACT_SIZE = Decimal("100")
OBSERVED_TICK_SIZE = Decimal("0.001")
OBSERVED_TICK_VALUE = Decimal("0.1")
OBSERVED_VOLUME_MIN = Decimal("0.01")
SMALL_ACCOUNT_EQUITIES = (
    Decimal("5"),
    Decimal("10"),
    Decimal("15"),
    Decimal("20"),
    Decimal("25"),
    Decimal("30"),
)


@dataclass(frozen=True, slots=True)
class SmallAccountFeasibility:
    equity: Decimal
    volume: Decimal
    stop_distance: Decimal
    spread: Decimal
    slippage: Decimal
    commission: Decimal | None
    planned_risk_usd: Decimal | None
    risk_cap_usd: Decimal
    accepted: bool
    reason: str
    minimum_equity_usd: Decimal | None
    uncertified_zero_commission_equity_usd: Decimal | None


def risk_cap_usd(equity: Decimal, risk_pct: Decimal) -> Decimal:
    """Floored cent cap. The same rounding as the live planned-risk budget."""
    eq = Decimal(str(equity or 0))
    pct = Decimal(str(risk_pct or 0))
    if eq <= 0 or pct <= 0:
        return Decimal("0")
    return (eq * pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


def minimum_equity_usd(*, planned_risk: Decimal, risk_pct: Decimal) -> Decimal | None:
    """Smallest cent equity whose floored cap still covers ``planned_risk``.

    ``None`` when the risk is not a positive amount. The comparison matches
    the live gate: equality is allowed, and a larger amount is rejected.
    """
    risk = Decimal(str(planned_risk or 0))
    pct = Decimal(str(risk_pct or 0))
    if risk <= 0 or pct <= 0:
        return None
    raw = risk * _PCT / pct
    equity = raw.quantize(_CENT, rounding=ROUND_DOWN)
    if equity <= 0:
        equity = _CENT
    for _ in range(20):
        if risk <= risk_cap_usd(equity, pct):
            return equity
        equity += _CENT
    return None


def evaluate_min_volume(
    *,
    equity: Decimal,
    stop_distance: Decimal,
    spread: Decimal,
    slippage: Decimal = Decimal("0"),
    commission: object = None,
    contract_size: Decimal = OBSERVED_CONTRACT_SIZE,
    volume: Decimal = OBSERVED_VOLUME_MIN,
    tick_size: Decimal | None = OBSERVED_TICK_SIZE,
    tick_value: Decimal | None = OBSERVED_TICK_VALUE,
    max_lot: Decimal = OWNER_MAX_LOT,
    risk_pct: Decimal = OWNER_MAX_PLANNED_RISK_PCT,
) -> SmallAccountFeasibility:
    """Accept the order only when inclusive risk fits the configured budget.

    ``volume`` is the broker minimum the caller wants to send. It is not
    increased to manufacture affordability and it is not cut below that
    minimum when the cap is too small.
    """
    eq = Decimal(str(equity))
    stop = Decimal(str(stop_distance))
    spr = Decimal(str(spread))
    slip = Decimal(str(slippage or 0))
    vol = Decimal(str(volume))
    lot_cap = Decimal(str(max_lot))
    pct = Decimal(str(risk_pct))
    contract = Decimal(str(contract_size))
    cap = risk_cap_usd(eq, pct)
    fee = declared_commission(commission)
    if fee is None:
        fee = resolve_entry_commission("XAUUSD", None)
    unit = price_unit_value(
        contract_size=contract, tick_size=tick_size, tick_value=tick_value
    )
    per_unit = unit * vol

    def pack(
        *,
        accepted: bool,
        reason: str,
        risk: Decimal | None,
        known_fee: Decimal | None,
        minimum: Decimal | None,
        zero_floor: Decimal | None,
    ) -> SmallAccountFeasibility:
        return SmallAccountFeasibility(
            equity=eq,
            volume=vol,
            stop_distance=stop,
            spread=spr,
            slippage=slip,
            commission=known_fee,
            planned_risk_usd=risk,
            risk_cap_usd=cap,
            accepted=accepted,
            reason=reason,
            minimum_equity_usd=minimum,
            uncertified_zero_commission_equity_usd=zero_floor,
        )

    if vol <= 0 or vol > lot_cap:
        return pack(
            accepted=False,
            reason=(
                "INVALID_BROKER_SPEC" if vol <= 0 else "BROKER_VOLUME_ABOVE_LOT_CAP"
            ),
            risk=None,
            known_fee=fee,
            minimum=None,
            zero_floor=None,
        )
    if stop <= 0 or contract <= 0 or per_unit <= 0:
        return pack(
            accepted=False,
            reason="INVALID_BROKER_SPEC",
            risk=None,
            known_fee=fee,
            minimum=None,
            zero_floor=None,
        )
    # Prefer the larger published unit so a spec mismatch cannot understate risk.
    risk_contract = contract if contract >= unit else unit
    zero_risk = planned_risk_usd(
        stop_distance=stop,
        spread=spr,
        contract_size=risk_contract,
        volume=vol,
        slippage=slip,
        commission=Decimal("0"),
    )
    zero_floor = minimum_equity_usd(planned_risk=zero_risk, risk_pct=pct)
    if fee is None:
        return pack(
            accepted=False,
            reason="OWNER_COMMISSION_UNKNOWN",
            risk=None,
            known_fee=None,
            minimum=None,
            zero_floor=zero_floor,
        )
    if fee < 0:
        return pack(
            accepted=False,
            reason="OWNER_COMMISSION_INVALID",
            risk=None,
            known_fee=fee,
            minimum=None,
            zero_floor=zero_floor,
        )
    risk = planned_risk_usd(
        stop_distance=stop,
        spread=spr,
        contract_size=risk_contract,
        volume=vol,
        slippage=slip,
        commission=fee,
    )
    minimum = minimum_equity_usd(planned_risk=risk, risk_pct=pct)
    if risk > cap:
        return pack(
            accepted=False,
            reason="OWNER_SL_RISK",
            risk=risk,
            known_fee=fee,
            minimum=minimum,
            zero_floor=zero_floor,
        )
    return pack(
        accepted=True,
        reason="",
        risk=risk,
        known_fee=fee,
        minimum=minimum,
        zero_floor=zero_floor,
    )


def observed_min_lot_rows(
    equities: tuple[Decimal, ...] = SMALL_ACCOUNT_EQUITIES,
    *,
    commission: object = None,
) -> tuple[SmallAccountFeasibility, ...]:
    """Evaluate the 2026-10-30 snapshot at each equity. The stop is not shrunk."""
    return tuple(
        evaluate_min_volume(
            equity=equity,
            stop_distance=OBSERVED_STOP_DISTANCE,
            spread=OBSERVED_SPREAD,
            slippage=OBSERVED_SLIPPAGE,
            commission=commission,
            contract_size=OBSERVED_CONTRACT_SIZE,
            volume=OBSERVED_VOLUME_MIN,
            tick_size=OBSERVED_TICK_SIZE,
            tick_value=OBSERVED_TICK_VALUE,
            max_lot=OWNER_MAX_LOT,
            risk_pct=OWNER_MAX_PLANNED_RISK_PCT,
        )
        for equity in equities
    )
