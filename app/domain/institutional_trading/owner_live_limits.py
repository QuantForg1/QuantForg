"""Owner live limits (owner baseline 2026-11-16, Gold only, real account).

Single source for the owner's hard trading limits. Every dollar amount is
derived from live equity; nothing below is a fixed USD cap. Every other risk
layer may be stricter, never looser.

- Max PLANNED risk per trade: 9% of live equity. The aggregate open-risk
  budget for every position and pending order together is also 9% (one
  concurrent position is the maximum count).
  Planned risk = (|entry - SL| + spread + order slippage) x contract x
  volume + known commission, rounded up to the cent. The cap is rounded down.
  An amount is never rounded down to pass. Unknown commission is not zero:
  the entry is rejected. A verified owner commission of 0.00 is a known zero.
  This is a planned maximum, not a cap on realised loss: gaps and execution
  failures can make a loss larger.
- Daily loss limit: 25% of the UTC day's starting equity, enforced as a
  pre-trade budget: realised loss today + floating loss + the new entry's
  planned risk must fit inside it. Unknown daily P/L blocks new entries.
  A deposit never forgives a loss already taken that day.
- A customer's own saved risk settings may only tighten these limits.
- No weekly, monthly or overall-drawdown limit unless an owner save sets one.
- Stop loss: max(1.00 x ATR(M1|M5), beyond the nearest structure + spread).
  A stop is never shrunk to fit the budget: too wide -> no trade.
- Net reward:risk floor is 1.50 after spread, expected slippage, and a
  confirmed commission. No experimental floor below it exists. TP is a real
  structure level, at most the second level out. Neither clears -> no trade.
- New entries Monday-Friday 07:00-17:00 UTC only. Broker symbol session,
  holidays and maintenance remain an additional gate. Spread <= 0.45.
- AI trade quality >= 75.
- Volume 0.01 (gateway max); at most 1 open position; 1 entry per cycle.
- No martingale, grid, averaging down or forced trades.

``evaluate_owner_entry`` is the final deterministic guard for NEW entries on
the live submit path. Closes and SL/TP management are never blocked here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal, InvalidOperation

from app.domain.trading.gold_only import is_gold_symbol


def _env_decimal(name: str, default: str) -> Decimal:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = Decimal(raw) if raw else Decimal(default)
    except InvalidOperation:
        value = Decimal(default)
    return value if value > 0 else Decimal(default)


_CENT = Decimal("0.01")
_PCT = Decimal("100")


def _now() -> datetime:
    """Clock for session / day-boundary defaults (tests pin it)."""
    return datetime.now(UTC)


OWNER_MAX_LOT = Decimal("0.01")
# Starting reference capital (configurable). Live equity is the risk reference;
# this value is the documented starting point and the $-figures shown at rest.
OWNER_RISK_REFERENCE_USD = _env_decimal("OWNER_RISK_REFERENCE_USD", "50")
OWNER_MAX_PLANNED_RISK_PCT = Decimal("9.0")
# Shared book cap. It is not the per-trade cap and it is not multiplied by
# the position count. With one open position it equals the per-trade cap.
OWNER_MAX_AGGREGATE_OPEN_RISK_PCT = Decimal("9.0")
# Authoritative daily stop: 25% of the UTC day's starting equity (owner
# baseline 2026-11-16). Enforced twice: as a halt once realised loss is
# above the cap, and as a pre-trade budget (loss so far + floating loss +
# the new entry's planned risk must fit inside the cap).
OWNER_DAILY_LOSS_PCT = Decimal("25.0")
# Weekly / monthly loss limits removed (0 = disabled, as for drawdown). Weekly
# and monthly P/L are still computed for reporting (summaries, journal).
OWNER_WEEKLY_LOSS_PCT = Decimal("0")
OWNER_MONTHLY_LOSS_PCT = Decimal("0")
# Owner baseline 2026-11-16: net reward:risk after spread, slippage and a known
# commission must be at least 1.50. A saved policy may only be stricter.
OWNER_MIN_REWARD_RISK = Decimal("1.50")
# Soft geometry target. Never below the hard floor.
OWNER_PREFERRED_REWARD_RISK = Decimal("1.50")
# No experimental floor below OWNER_MIN_REWARD_RISK may be saved or promoted.
OWNER_EXPERIMENTAL_REWARD_RISK: tuple[Decimal, ...] = ()
OWNER_MIN_REWARD_RISK_FLOOR = OWNER_MIN_REWARD_RISK
# Owner baseline 2026-11-16: hard spread ceiling 0.45. A saved policy may be
# tighter. No environment value can raise it.
OWNER_MAX_SPREAD = Decimal("0.45")
# Owner baseline 2026-11-16: new entries only Monday-Friday, 07:00 inclusive
# to 17:00 exclusive UTC. Broker sessions, holidays and maintenance remain an
# additional gate. Closes and SL/TP management are never blocked by this.
OWNER_SESSION_START_UTC = time(7, 0)
OWNER_SESSION_END_UTC = time(17, 0)
OWNER_SESSION_WEEKDAYS = frozenset({0, 1, 2, 3, 4})
# Owner 2026-10-30 experiment: 1.00 x ATR. Structure + spread still wins when
# wider. The stop is never shrunk to fit 0.01 lot.
OWNER_SL_ATR_MULTIPLIER = _env_decimal("OWNER_SL_ATR_MULTIPLIER", "1.00")
# A stop of k x ATR is inside the average true range when k < 1 and the ATR
# floor binds. 0.75 and 0.90 are rejected for that reason. 1.00 is the noise
# boundary and is the experimental default. 1.25 and 1.50 remain savable.
OWNER_SL_ATR_MULTIPLIERS = (
    Decimal("1.00"),
    Decimal("1.25"),
    Decimal("1.50"),
)
OWNER_SL_ATR_MULTIPLIERS_INSIDE_NOISE = (
    Decimal("0.75"),
    Decimal("0.90"),
)
# TP may use the second structure level when the first misses the active
# reward:risk floor, or when the second level meets OWNER_PREFERRED_REWARD_RISK
# while the first only clears the hard floor (asymmetric-win repair).
OWNER_TP_MAX_STRUCTURE_LEVELS = 2
OWNER_SL_ATR_TIMEFRAME = (
    (os.environ.get("OWNER_SL_ATR_TIMEFRAME") or "M1").strip().upper()
)
if OWNER_SL_ATR_TIMEFRAME not in {"M1", "M5"}:
    OWNER_SL_ATR_TIMEFRAME = "M1"
OWNER_MAX_OPEN_POSITIONS = 1
OWNER_MAX_ENTRIES_PER_CYCLE = 1
# Consecutive-loss pause removed (owner 2026-10-23): 0 = disabled.
OWNER_MAX_CONSECUTIVE_LOSSES = 0
# Unused while the pause is disabled; kept for the shared config shape.
OWNER_LOSS_STREAK_COOLDOWN_MINUTES = 24 * 60
# Hard floor on the AI trade quality of a robot entry (owner baseline 75).
# Unset policy stays 75. A saved integer from 75 to 100 is used. Below 75
# fails closed to 75. No environment variable can lower the unset default.
OWNER_MIN_TRADE_QUALITY = 75
OWNER_MIN_TRADE_QUALITY_FLOOR = 75

# Owner-confirmed Weltrade tariff. This is not a broker deal record.
# Spread, swap, and slippage stay separate costs. A missing or altered
# block is unknown and the entry fails closed.
COMMISSION_STATUS_VERIFIED = "VERIFIED_BY_OWNER_SUPPORT"
COMMISSION_SOURCE_OWNER_CONFIRMED = "OWNER_CONFIRMED_WELTRADE_SUPPORT"
COMMISSION_MODEL_FIXED_PER_ORDER = "FIXED_ACCOUNT_CURRENCY_PER_ORDER"
COMMISSION_ACCOUNT_SCOPE = "ATTACHED_WELTRADE_REAL_HEDGE"
COMMISSION_SYMBOL = "XAUUSD"
COMMISSION_CURRENCY = "USD"
COMMISSION_CONFIGURATION_VERSION = "1"

# Compatibility names used by other layers (values at the reference capital).
OWNER_SL_RISK_PCT = OWNER_MAX_PLANNED_RISK_PCT
# No minimum planned-risk floor: the stop comes from ATR/structure, not a $ band.
OWNER_MIN_SL_RISK_USD = Decimal("0")
OWNER_DAILY_LOSS_CEILING_PCT = OWNER_DAILY_LOSS_PCT


def _active_planned_risk_pct() -> Decimal:
    """Saved policy may be stricter than the owner cap. It cannot be looser."""
    from app.domain.institutional_trading.runtime_policy import (
        active_max_planned_risk_pct,
    )

    return active_max_planned_risk_pct()


def max_aggregate_risk_usd(equity: Decimal) -> Decimal:
    """Shared open-risk budget for every open position and pending order."""
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    from app.domain.institutional_trading.runtime_policy import (
        active_max_aggregate_open_risk_pct,
    )

    pct = active_max_aggregate_open_risk_pct()
    return (eq * pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


def max_planned_risk_usd(equity: Decimal) -> Decimal:
    """Planned-risk cap for live equity, rounded down to the cent.

    The approved ceiling is ``OWNER_MAX_PLANNED_RISK_PCT``. An installed
    runtime policy may use a lower percent. A missing policy uses the ceiling.
    """
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    pct = _active_planned_risk_pct()
    return (eq * pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


# Planned-risk cap at the reference capital ($7.00 at $50) for static configs.
OWNER_MAX_SL_RISK_USD = max_planned_risk_usd(OWNER_RISK_REFERENCE_USD)


def owner_authorized_max_lot(broker_max: Decimal | None = None) -> Decimal:
    """Final executable lot ceiling for every strategy.

    Never above the active owner max lot (hard ceiling ``OWNER_MAX_LOT``).
    Never above the broker ``volume_max`` when that spec is known.
    Callers must still reject when broker ``volume_min`` exceeds this ceiling.
    """
    from app.domain.institutional_trading.runtime_policy import active_max_lot

    cap = active_max_lot()
    if broker_max is None:
        return cap
    try:
        broker = Decimal(str(broker_max))
    except Exception:
        return cap
    if broker <= 0:
        return cap
    return min(broker, cap)


def owner_authorized_lot_ceiling_violated(
    *,
    volume: Decimal,
    broker_min: Decimal | None = None,
) -> str | None:
    """Return a reject code when volume or broker min exceeds the owner lot cap."""
    from app.domain.institutional_trading.runtime_policy import active_max_lot

    cap = active_max_lot()
    vol = Decimal(str(volume or 0))
    if broker_min is not None:
        try:
            floor = Decimal(str(broker_min))
        except Exception:
            floor = Decimal("0")
        if floor > 0 and floor > cap:
            return (
                f"OWNER_BROKER_MIN_EXCEEDS_MAX_LOT: broker volume_min {floor} "
                f"> owner max_lot {cap}"
            )
    if vol > cap:
        return f"OWNER_MAX_LOT: volume {vol} > {cap}"
    return None


def owner_risk_cap_usd(
    *,
    equity: Decimal | None,
    configured: Decimal | None,
    reference_default: Decimal,
    positions: int = 1,
    book: bool = False,
) -> Decimal:
    """Live equity cap. ``positions`` does not multiply the budget.

    The book cap and the per-trade cap come from the owner limits. A stricter
    explicit dollar configuration stays. Positions never multiply the budget.
    """
    del positions
    eq = Decimal(str(equity or 0))
    if eq > 0 and (configured is None or configured == reference_default):
        if book:
            return max_aggregate_risk_usd(eq)
        return max_planned_risk_usd(eq)
    return configured if configured is not None else reference_default


def max_sl_risk_usd(equity: Decimal) -> Decimal:
    """Per-trade planned-loss cap in USD for the given equity (alias)."""
    return max_planned_risk_usd(equity)


def _nonneg(value: Decimal | None) -> Decimal:
    raw = Decimal(str(value or 0))
    return raw if raw > 0 else Decimal("0")


def owner_commission_configuration() -> dict[str, str]:
    """Explicit tariff. Deal history is a separate record and is not written."""
    return {
        "symbol": COMMISSION_SYMBOL,
        "account_scope": COMMISSION_ACCOUNT_SCOPE,
        "amount_usd": "0.00",
        "status": COMMISSION_STATUS_VERIFIED,
        "source": COMMISSION_SOURCE_OWNER_CONFIRMED,
        "model": COMMISSION_MODEL_FIXED_PER_ORDER,
        "currency": COMMISSION_CURRENCY,
        "configuration_version": COMMISSION_CONFIGURATION_VERSION,
        "applies_to": "new_order_planned_risk",
        "excludes": "spread,swap,slippage,broker_deal_history",
    }


def _commission_amount(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount.quantize(_CENT)


def verified_policy_commission(
    symbol: str, document: dict[str, object] | None = None
) -> Decimal | None:
    """Known tariff only when the saved block matches the owner confirmation.

    ``None`` means the configuration is missing or invalid. Callers fail
    closed. A matching 0.00 is a known zero, not an invented deal.
    """
    if not is_gold_symbol(symbol):
        return None
    if document is None:
        from app.domain.institutional_trading.runtime_policy import active_policy

        loaded = active_policy()
        document = loaded if isinstance(loaded, dict) else None
    if not isinstance(document, dict) or document.get("unavailable"):
        return None
    raw = document.get("commission")
    if not isinstance(raw, dict):
        return None
    expected = owner_commission_configuration()
    if set(raw) != set(expected):
        return None
    for key, required in expected.items():
        if key == "amount_usd":
            continue
        if raw.get(key) != required:
            return None
    return _commission_amount(raw.get("amount_usd"))


def clean_commission_configuration(
    raw: object,
) -> tuple[dict[str, str] | None, list[str]]:
    """Validate a save. The status and source must match the owner confirmation."""
    expected = owner_commission_configuration()
    if not isinstance(raw, dict):
        return None, ["commission must be an object"]
    errors: list[str] = []
    unknown = sorted(set(map(str, raw)) - set(expected))
    if unknown:
        errors.append("unknown commission keys: " + ", ".join(unknown))
    for key, required in expected.items():
        if key == "amount_usd":
            continue
        if raw.get(key) != required:
            errors.append(f"commission.{key} must be {required}")
    amount = _commission_amount(raw.get("amount_usd"))
    if amount is None:
        errors.append("commission.amount_usd must be a non-negative amount")
        return None, errors
    if errors:
        return None, errors
    cleaned = dict(expected)
    cleaned["amount_usd"] = format(amount, "f")
    return cleaned, []


def commission_audit(
    symbol: str, document: dict[str, object] | None = None
) -> dict[str, str]:
    """Source and configuration version for logs and the admin view."""
    amount = verified_policy_commission(symbol, document)
    usable = amount is not None
    return {
        "commission_usd": format(amount, "f") if usable else "",
        "commission_status": COMMISSION_STATUS_VERIFIED if usable else "UNVERIFIED",
        "commission_source": (
            COMMISSION_SOURCE_OWNER_CONFIRMED if usable else "MISSING_OR_INVALID"
        ),
        "commission_model": COMMISSION_MODEL_FIXED_PER_ORDER if usable else "",
        "commission_configuration_version": (
            COMMISSION_CONFIGURATION_VERSION if usable else ""
        ),
        "commission_usable": "true" if usable else "false",
    }


def resolve_entry_commission(symbol: str, supplied: object) -> Decimal | None:
    """Use an explicit numeric tariff, otherwise the verified policy block.

    A missing policy block stays unknown. This does not read broker deals.
    """
    fee = declared_commission(supplied)
    if fee is not None:
        return fee
    return verified_policy_commission(symbol)


def declared_commission(value: object) -> Decimal | None:
    """A supplied numeric commission, including a known zero.

    ``None``, booleans, and non-numeric objects are unknown. Unknown is not
    zero. A negative number is returned so the caller can reject it; it is
    never used to shrink planned risk.
    """
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        return None
    try:
        fee = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not fee.is_finite():
        return None
    return fee


def price_unit_value(
    *,
    contract_size: Decimal,
    tick_size: Decimal | None = None,
    tick_value: Decimal | None = None,
) -> Decimal:
    """Account-currency value of one price unit.

    ``tick_value / tick_size`` when the broker published both. That is the
    conversion used by the gateway. Otherwise the symbol contract size.
    """
    tick = _nonneg(tick_size)
    value = _nonneg(tick_value)
    if tick > 0 and value > 0:
        return value / tick
    return Decimal(str(contract_size or 0))


def planned_risk_usd(
    *,
    stop_distance: Decimal,
    spread: Decimal | None,
    contract_size: Decimal,
    volume: Decimal,
    slippage: Decimal | None = None,
    commission: Decimal | None = None,
) -> Decimal:
    """Monetary planned loss, rounded up to the cent.

    ``(|entry - SL| + spread + slippage) x contract x volume + commission``.
    Rounding up never lets an over-cap order pass. An amount that is already
    an exact cent stays on that cent.
    """
    spr = _nonneg(spread)
    dist = abs(Decimal(str(stop_distance or 0)))
    slip = _nonneg(slippage)
    fee = _nonneg(commission)
    cs = Decimal(str(contract_size))
    vol = Decimal(str(volume))
    return ((dist + spr + slip) * cs * vol + fee).quantize(
        _CENT, rounding=ROUND_CEILING
    )


def maximum_affordable_stop_distance(
    *,
    cap: Decimal,
    spread: Decimal | None,
    contract_size: Decimal,
    volume: Decimal,
    slippage: Decimal | None = None,
    commission: Decimal | None = None,
    tick_size: Decimal | None = None,
) -> Decimal | None:
    """Largest stop distance whose planned risk is still within ``cap``.

    ``None`` means this volume's spread, slippage, and commission already
    exceed the cap, so no protective stop can make the order legal. The
    distance is stepped down to the tick. Risk is never rounded down to pass.
    """
    budget = Decimal(str(cap or 0))
    per = Decimal(str(contract_size)) * Decimal(str(volume))
    if budget <= 0 or per <= 0:
        return None
    extra = _nonneg(spread) + _nonneg(slippage)
    fee = _nonneg(commission)
    room = budget - fee
    if room <= 0:
        return None
    raw = (room / per) - extra
    if raw <= 0:
        return None
    tick = _nonneg(tick_size) or Decimal("0.001")
    steps = (raw / tick).to_integral_value(rounding=ROUND_DOWN)
    fitted = steps * tick
    while (
        fitted > 0
        and planned_risk_usd(
            stop_distance=fitted,
            spread=spread,
            contract_size=contract_size,
            volume=volume,
            slippage=slippage,
            commission=commission,
        )
        > budget
    ):
        fitted -= tick
    return fitted if fitted > 0 else None


def format_owner_sl_risk(
    *,
    risk_usd: Decimal,
    cap: Decimal,
    equity: Decimal,
    stop_distance: Decimal,
    spread: Decimal,
    volume: Decimal,
    contract_size: Decimal,
    slippage: Decimal = Decimal("0"),
    commission: Decimal = Decimal("0"),
    tick_size: Decimal | None = None,
    pct: Decimal | None = None,
) -> str:
    """Rejection text: calculated risk, cap, inputs, and the safe correction."""
    shown_pct = _active_planned_risk_pct() if pct is None else pct
    base = (
        f"OWNER_SL_RISK: planned risk ${risk_usd} > ${cap} "
        f"({shown_pct}% of equity {equity})"
    )
    costs = (
        f"stop {stop_distance} + spread {spread} + slippage {slippage} "
        f"+ commission {commission}, volume {volume}, contract {contract_size}"
    )
    fitted = maximum_affordable_stop_distance(
        cap=cap,
        spread=spread,
        contract_size=contract_size,
        volume=volume,
        slippage=slippage,
        commission=commission,
        tick_size=tick_size,
    )
    if fitted is None:
        bare = planned_risk_usd(
            stop_distance=Decimal("0"),
            spread=spread,
            contract_size=contract_size,
            volume=volume,
            slippage=slippage,
            commission=commission,
        )
        return (
            f"{base}. {costs}. Minimum volume {volume} costs ${bare} "
            f"before any protective stop, which is above ${cap}. "
            "No smaller lot is allowed, so this order cannot be submitted."
        )
    return (
        f"{base}. {costs}. Tighten the stop to {fitted} or less so the "
        "planned risk fits the saved cap. The lot cannot be reduced "
        f"below {volume}."
    )


def daily_loss_cap_usd(
    start_of_day_equity: Decimal, pct: Decimal | None = None
) -> Decimal:
    """Daily stop in USD: pct of the UTC day's starting equity.

    ``pct is None`` uses the installed runtime policy, or the owner ceiling
    when no policy is installed. An explicit percent cannot exceed the
    owner ceiling ``OWNER_DAILY_LOSS_PCT``.
    """
    sod = Decimal(str(start_of_day_equity or 0))
    if sod <= 0:
        return Decimal("0")
    if pct is None:
        from app.domain.institutional_trading.runtime_policy import (
            active_daily_loss_pct,
        )

        eff = active_daily_loss_pct()
    else:
        eff = min(Decimal(str(pct)), OWNER_DAILY_LOSS_PCT)
    return (sod * eff / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


def daily_loss_exceeded(
    *,
    daily_pnl: Decimal,
    base_now: Decimal,
    pct: Decimal | None = None,
) -> bool:
    """True when today's loss is strictly above the daily stop.

    ``base_now`` is the caller's current base (balance or equity); start-of-day
    is reconstructed as ``base_now + loss`` so a realised loss does not shrink
    the stop it is measured against.
    """
    pnl = Decimal(str(daily_pnl or 0))
    base = Decimal(str(base_now or 0))
    if pnl >= 0 or base <= 0:
        return False
    loss = -pnl
    return loss > daily_loss_cap_usd(base + loss, pct)


def daily_loss_cap_pct(
    *,
    daily_pnl: Decimal,
    base_now: Decimal,
    pct: Decimal | None = None,
) -> Decimal:
    """Daily stop expressed as a percent of ``base_now``.

    For layers that compare ``loss / base_now`` against a percent threshold.
    """
    base = Decimal(str(base_now or 0))
    if base <= 0:
        if pct is None:
            from app.domain.institutional_trading.runtime_policy import (
                active_daily_loss_pct,
            )

            return active_daily_loss_pct()
        return Decimal(str(pct))
    loss = max(-Decimal(str(daily_pnl or 0)), Decimal("0"))
    cap_usd = daily_loss_cap_usd(base + loss, pct)
    return (cap_usd / base * _PCT).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def in_owner_session(now: datetime | None = None) -> bool:
    """True Monday-Friday from 07:00 (inclusive) to 17:00 (exclusive) UTC.

    Owner baseline 2026-11-16. Broker symbol sessions, weekend closures,
    holidays and maintenance are still enforced separately by broker session
    truth. This gate only applies to NEW entries.
    """
    clock = now or _now()
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    utc = clock.astimezone(UTC)
    if utc.weekday() not in OWNER_SESSION_WEEKDAYS:
        return False
    return OWNER_SESSION_START_UTC <= utc.time() < OWNER_SESSION_END_UTC


def next_utc_day_start(now: datetime | None = None) -> datetime:
    """Start of the next UTC day (end of the loss-streak pause)."""
    clock = now or _now()
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    day = clock.astimezone(UTC).date() + timedelta(days=1)
    return datetime.combine(day, time(0, 0), tzinfo=UTC)


def owner_stop_distance(
    *,
    atr: Decimal | None,
    structure_distance: Decimal | None,
    multiplier: Decimal = OWNER_SL_ATR_MULTIPLIER,
) -> Decimal | None:
    """Volatility- and structure-aware stop: max(k x ATR, structure + buffer).

    ``structure_distance`` already includes the spread buffer beyond the
    nearest valid structure level. Never narrower than k x ATR; never shrunk.
    None (no ATR) -> no stop -> no trade.
    """
    if atr is None or atr <= 0:
        return None
    floor = Decimal(str(atr)) * Decimal(str(multiplier))
    if structure_distance is not None and structure_distance > floor:
        return Decimal(str(structure_distance))
    return floor


def reward_risk_after_spread(
    *, tp_distance: Decimal, stop_distance: Decimal, spread: Decimal
) -> Decimal | None:
    """Spread-only RR: |tp - entry| / (|entry - sl| + spread). None when undefined.

    This is not the full net ratio. Use :func:`net_reward_risk` when slippage
    or a known commission must be included.
    """
    risk = stop_distance + max(spread, Decimal("0"))
    if risk <= 0 or tp_distance <= 0:
        return None
    return tp_distance / risk


def _quantize_cent(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def authorized_min_reward_risk(value: Decimal) -> Decimal | None:
    """Return an enforceable net floor, or None when the saved value is illegal.

    Any value at least ``OWNER_MIN_REWARD_RISK`` is allowed. Nothing below.
    """
    try:
        rr = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if rr >= OWNER_MIN_REWARD_RISK:
        return rr
    normalized = _quantize_cent(rr)
    if normalized in OWNER_EXPERIMENTAL_REWARD_RISK and rr == normalized:
        return normalized
    return None


def authorized_min_trade_quality(value: object) -> int | None:
    """75-100 is savable. The unset default remains 75."""
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        return None
    try:
        quality = int(value)
    except (TypeError, ValueError):
        return None
    if quality < OWNER_MIN_TRADE_QUALITY_FLOOR or quality > 100:
        return None
    return quality


def atr_multiplier_verdict(value: Decimal) -> str:
    """``accepted``, ``inside_noise``, or ``rejected``.

    A multiplier below 1.00 places the ATR floor inside the average true
    range whenever that floor binds. 0.75 and 0.90 are inside that noise.
    1.00 equals one ATR (the boundary). 1.25 and 1.50 are outside it.
    """
    try:
        mult = _quantize_cent(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return "rejected"
    if mult < Decimal("1.00") or mult in {
        _quantize_cent(item) for item in OWNER_SL_ATR_MULTIPLIERS_INSIDE_NOISE
    }:
        return "inside_noise"
    if mult in {_quantize_cent(item) for item in OWNER_SL_ATR_MULTIPLIERS}:
        return "accepted"
    return "rejected"


@dataclass(frozen=True, slots=True)
class NetRewardRisk:
    """Gross is |tp-entry|/|entry-sl|. Net adds spread, slippage, and known fees.

    ``commission_included`` is False when commission is None or cannot be
    converted to price. That ratio is not a verified net-of-commission result.
    A None commission is never treated as zero for this flag.
    """

    ratio: Decimal | None
    gross_ratio: Decimal | None
    commission_included: bool


def net_reward_risk(
    *,
    tp_distance: Decimal,
    stop_distance: Decimal,
    spread: Decimal,
    slippage: Decimal | None = None,
    commission: Decimal | None = None,
    contract_size: Decimal | None = None,
    volume: Decimal | None = None,
    spread_already_in_stop: bool = False,
) -> NetRewardRisk:
    """Net RR. Slippage widens the risk leg, matching planned-risk dollars.

    Known commission is converted with ``contract_size * volume`` and added to
    the risk leg. Unknown commission is omitted. Reward is the target distance
    minus that known commission in price units.

    When ``spread_already_in_stop`` is True, ``stop_distance`` already embeds the
    owner spread buffer beyond structure (see structure SL placement). The spread
    is then **not** added again on the risk leg — counting it twice falsely
    depresses net RR and rejects valid owner-floor setups. Slippage and known
    commission still apply.
    """
    tp = Decimal(str(tp_distance or 0))
    stop = Decimal(str(stop_distance or 0))
    spr = max(Decimal(str(spread or 0)), Decimal("0"))
    if spread_already_in_stop:
        spr = Decimal("0")
    slip = _nonneg(slippage)
    gross = (tp / stop) if stop > 0 and tp > 0 else None
    fee_price = Decimal("0")
    commission_included = False
    if commission is not None and contract_size is not None and volume is not None:
        per = Decimal(str(contract_size)) * Decimal(str(volume))
        if per > 0:
            fee_price = Decimal(str(commission)) / per
            if fee_price < 0:
                fee_price = Decimal("0")
            commission_included = True
    reward = tp - fee_price
    risk = stop + spr + slip + fee_price
    if reward <= 0 or risk <= 0:
        return NetRewardRisk(None, gross, commission_included)
    return NetRewardRisk(reward / risk, gross, commission_included)


def gross_distance_rr_block(
    *, tp_distance: Decimal, stop_distance: Decimal
) -> str | None:
    """Block geometry whose gross reward:risk cannot meet the active floor.

    Gross is only an upper bound on net; the owner entry check then applies
    spread, slippage, and known commission. A target that does not exceed the
    stop is reported as such when the floor is at least 1.
    """
    from app.domain.institutional_trading.runtime_policy import active_min_reward_risk

    floor = active_min_reward_risk()
    tp = Decimal(str(tp_distance or 0))
    stop = Decimal(str(stop_distance or 0))
    if floor >= Decimal("1") and (stop <= 0 or tp <= stop):
        return (
            "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
            f"planned TP {tp} <= planned SL {stop}"
        )
    if stop <= 0 or tp <= 0 or (tp / stop) < floor:
        return (
            f"OWNER_MIN_RR: gross reward:risk "
            f"{(tp / stop).quantize(_CENT) if stop > 0 else Decimal('0')} < {floor}"
        )
    return None


def estimated_rr_block(estimated_rr: Decimal | None) -> str | None:
    """Same floor as :func:`gross_distance_rr_block` when only a ratio is known."""
    if estimated_rr is None:
        return None
    from app.domain.institutional_trading.runtime_policy import active_min_reward_risk

    floor = active_min_reward_risk()
    rr = Decimal(str(estimated_rr))
    if floor >= Decimal("1") and rr <= Decimal("1"):
        return (
            "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
            f"planned RR {rr} does not exceed 1.0"
        )
    if rr < floor:
        return f"OWNER_MIN_RR: estimated reward:risk {rr} < {floor}"
    return None


# Market entries: the stop distance at the live price may shrink at most this
# much versus the signal's distance before the order is refused (2026-10-23).
OWNER_MAX_STOP_SHRINK_PCT = _env_decimal("OWNER_MAX_STOP_SHRINK_PCT", "10")

# Pre-send RR check: assume the fill lands this far adversely from the check
# price (TP distance - B over stop distance + spread + B). Owner default 0
# (2026-10-23); recalibrate from logged check-vs-fill moves after ~30 fills.
OWNER_RR_SLIPPAGE_BUFFER = _env_decimal("OWNER_RR_SLIPPAGE_BUFFER", "0")


def stop_shrink_violation(
    *,
    side: str,
    signal_price: Decimal | None,
    live_price: Decimal | None,
    stop_loss: Decimal | None,
    max_shrink_pct: Decimal = OWNER_MAX_STOP_SHRINK_PCT,
) -> str | None:
    """Refuse a market entry whose stop shrank because price moved since the signal.

    The SL is an absolute price beyond structure. If price moved toward it
    between the signal and the send, the real stop is narrower than the owner
    rule allows ("never shrunk"). Returns a reason, or None when acceptable or
    when any input is unknown (other guards cover missing data).
    """
    if signal_price is None or live_price is None or stop_loss is None:
        return None
    if signal_price <= 0 or live_price <= 0 or stop_loss <= 0:
        return None
    sell = str(side).strip().upper() == "SELL"
    planned = (stop_loss - signal_price) if sell else (signal_price - stop_loss)
    live = (stop_loss - live_price) if sell else (live_price - stop_loss)
    if planned <= 0:
        return None
    if live <= 0:
        return (
            f"OWNER_PRICE_DRIFT: live price {live_price} is already beyond the "
            f"stop loss {stop_loss} (signal price {signal_price}); not sent"
        )
    floor = planned * (Decimal("1") - Decimal(str(max_shrink_pct)) / Decimal("100"))
    if live < floor:
        return (
            f"OWNER_PRICE_DRIFT: stop distance shrank from {planned.quantize(_CENT)} "
            f"to {live.quantize(_CENT)} (price {signal_price} -> {live_price}); "
            f"more than {max_shrink_pct}% narrower than planned; not sent, "
            "re-evaluated next cycle"
        )
    return None


@dataclass(frozen=True, slots=True)
class DailyLossContext:
    """Today's (UTC) realised trading result for the pre-trade daily budget.

    ``realized_pnl`` is the sum of every trade deal closed today, including
    trades before a deposit: a deposit never forgives a loss. ``deposits`` is
    verified broker cash added today. ``trusted`` is False whenever the deal
    history could not be read; new entries are then blocked.
    """

    trusted: bool
    realized_pnl: Decimal = Decimal("0")
    deposits: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    source: str = ""

    @property
    def day_start_equity(self) -> Decimal:
        """Balance at 00:00 UTC, reconstructed from today's deals."""
        start = self.balance - self.realized_pnl - max(self.deposits, Decimal("0"))
        return start if start > 0 else Decimal("0")

    @property
    def budget_base(self) -> Decimal:
        """Day-start equity plus capital deposited today."""
        return self.day_start_equity + max(self.deposits, Decimal("0"))

    @property
    def committed_loss(self) -> Decimal:
        """Realised loss today plus current floating loss (never negative)."""
        realised = max(-self.realized_pnl, Decimal("0"))
        floating = max(self.balance - self.equity, Decimal("0"))
        return realised + floating


def daily_budget_violation(
    context: DailyLossContext | None,
    *,
    planned_risk: Decimal | None,
    pct: Decimal | None = None,
) -> str | None:
    """Reject a NEW entry that could push today's loss past the daily stop.

    Unknown or untrusted daily P/L rejects. The check is
    ``committed_loss + planned_risk <= pct x budget_base``. Closes and
    protective management never call this.
    """
    if context is None or not context.trusted:
        return (
            "OWNER_DAILY_PNL_UNAVAILABLE: today's realised P/L could not be "
            "verified from broker deals, so new entries are blocked"
        )
    base = context.budget_base
    if base <= 0:
        return "OWNER_DAILY_BASE_UNAVAILABLE: day-start equity is unknown"
    cap = daily_loss_cap_usd(base, pct)
    committed = context.committed_loss
    if committed > cap:
        return (
            f"OWNER_DAILY_STOP: loss today {committed.quantize(_CENT)} is above "
            f"the daily stop {cap} of day-start equity {base.quantize(_CENT)}"
        )
    risk = _nonneg(planned_risk)
    if committed + risk > cap:
        return (
            f"OWNER_DAILY_BUDGET: loss today {committed.quantize(_CENT)} + "
            f"planned risk {risk.quantize(_CENT)} > daily stop {cap} "
            f"(day-start equity {base.quantize(_CENT)})"
        )
    return None


def evaluate_owner_entry(
    *,
    symbol: str,
    side: str,
    volume: Decimal,
    entry: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    spread: Decimal | None,
    contract_size: Decimal,
    equity: Decimal,
    min_stop_distance: Decimal = Decimal("0"),
    now: datetime | None = None,
    weekly_pnl: Decimal | None = None,
    peak_equity: Decimal | None = None,
    peak_known: bool = True,
    slippage: Decimal | None = None,
    commission: Decimal | None = None,
    tick_size: Decimal | None = None,
    stop_includes_spread_buffer: bool = False,
    daily: DailyLossContext | None = None,
    user_planned_risk_pct: Decimal | None = None,
    user_daily_loss_pct: Decimal | None = None,
) -> list[str]:
    """Return owner-limit violations for a NEW entry (empty list = allowed).

    ``daily`` is required: without a trusted daily P/L the entry is rejected.
    ``user_planned_risk_pct`` / ``user_daily_loss_pct`` are the account owner's
    own saved settings; they can only tighten the owner caps (strictest wins).

    Planned risk includes the spread once, plus the order's slippage and the
    supplied commission, rounded up to the cent:
    ``(|entry - sl| + spread + slippage) x contract x volume + commission``.
    ``commission is None`` rejects the entry. It is not treated as zero.
    A known zero is included. Reward:risk counts the spread once, on the risk
    leg, plus order slippage and a known commission. The ratio must clear the
    active owner floor (``OWNER_MIN_REWARD_RISK``, or a stricter saved value).
    When ``stop_includes_spread_buffer`` is True, ``|entry - sl|`` already embeds
    the owner spread buffer; spread is not added again to planned risk or net RR
    (Phase-6 — avoid double-count; slippage + commission still apply).
    ``min_stop_distance`` is the broker stops_level in price units
    (``point * stops_level``); SL and TP must both be at least that far away.
    """
    from app.domain.institutional_trading.runtime_policy import (
        active_max_lot,
        active_max_spread,
        active_min_lot,
        active_min_reward_risk,
        drawdown_limit_pct,
        full_utc_day_required,
        policy_unavailable,
        weekly_loss_limit_pct,
    )

    if policy_unavailable():
        return ["CONFIG_UNAVAILABLE: runtime trading policy could not be read"]

    reasons: list[str] = []
    vol = Decimal(str(volume or 0))
    px = Decimal(str(entry or 0))
    cs = Decimal(str(contract_size or 0))
    eq = Decimal(str(equity or 0))
    side_u = (side or "").strip().upper()
    lot_cap = active_max_lot()
    spread_cap = active_max_spread()
    rr_floor = active_min_reward_risk()
    min_lot = active_min_lot()

    # Policy violations are collected; missing inputs stop evaluation below.
    violations: list[str] = []
    if not full_utc_day_required():
        violations.append(
            "OWNER_SESSION_POLICY: full UTC day evaluation cannot be disabled"
        )
    if not is_gold_symbol(symbol):
        violations.append(f"OWNER_GOLD_ONLY: symbol {symbol!r} is not XAUUSD")
    if vol > lot_cap:
        violations.append(f"OWNER_MAX_LOT: volume {vol} > {lot_cap}")
    if min_lot is not None and vol < min_lot:
        violations.append(f"OWNER_MIN_LOT: volume {vol} < {min_lot}")
    if not in_owner_session(now):
        violations.append(
            "OWNER_SESSION: entry is outside "
            f"{OWNER_SESSION_START_UTC:%H:%M}-{OWNER_SESSION_END_UTC:%H:%M} UTC"
        )
    if vol <= 0:
        reasons.append("OWNER_VOLUME_INVALID: volume must be > 0")
    if side_u not in {"BUY", "SELL"}:
        reasons.append(f"OWNER_SIDE_INVALID: {side!r}")
    if px <= 0:
        reasons.append("OWNER_ENTRY_UNKNOWN: entry price unresolved")
    if cs <= 0:
        reasons.append("OWNER_CONTRACT_UNKNOWN: contract size unresolved")
    if eq <= 0:
        reasons.append("OWNER_EQUITY_UNKNOWN: risk reference (equity) unavailable")
    if stop_loss is None or Decimal(str(stop_loss)) <= 0:
        reasons.append("OWNER_SL_REQUIRED: every entry needs a broker-side SL")
    if take_profit is None or Decimal(str(take_profit)) <= 0:
        reasons.append("OWNER_TP_REQUIRED: every entry needs a broker-side TP")
    if spread is None or Decimal(str(spread)) < 0:
        reasons.append("OWNER_SPREAD_UNKNOWN: cannot verify reward:risk after spread")
    if reasons:
        return violations + reasons

    sl = Decimal(str(stop_loss))
    tp = Decimal(str(take_profit))
    spr = Decimal(str(spread))
    if spr > spread_cap:
        violations.append(f"OWNER_MAX_SPREAD: spread {spr} > {spread_cap}")
    if side_u == "BUY" and not (sl < px < tp):
        return [
            *violations,
            f"OWNER_STOPS_WRONG_SIDE: BUY needs SL < entry < TP ({sl}/{px}/{tp})",
        ]
    if side_u == "SELL" and not (tp < px < sl):
        return [
            *violations,
            f"OWNER_STOPS_WRONG_SIDE: SELL needs TP < entry < SL ({tp}/{px}/{sl})",
        ]

    sl_dist = abs(px - sl)
    tp_dist = abs(tp - px)
    slip = _nonneg(slippage)
    # Spread still gates max-spread; only omit it from risk/RR when already in SL.
    risk_spread = Decimal("0") if stop_includes_spread_buffer else spr
    fee = resolve_entry_commission(symbol, commission)
    if fee is None:
        violations.append(
            "OWNER_COMMISSION_UNKNOWN: account commission was not supplied, "
            "so inclusive planned risk is unverified and the entry is rejected"
        )
    elif fee < 0:
        violations.append("OWNER_COMMISSION_INVALID: commission cannot be negative")
        fee = None
    risk_usd: Decimal | None = None
    if fee is not None:
        risk_usd = planned_risk_usd(
            stop_distance=sl_dist,
            spread=risk_spread,
            contract_size=cs,
            volume=vol,
            slippage=slip,
            commission=fee,
        )
        cap = max_planned_risk_usd(eq)
        user_pct = _nonneg(user_planned_risk_pct)
        if user_pct > 0:
            user_cap = (eq * user_pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)
            if user_cap < cap:
                cap = user_cap
        if risk_usd > cap:
            violations.append(
                format_owner_sl_risk(
                    risk_usd=risk_usd,
                    cap=cap,
                    equity=eq,
                    stop_distance=sl_dist,
                    spread=spr,
                    volume=vol,
                    contract_size=cs,
                    slippage=slip,
                    commission=fee,
                    tick_size=tick_size,
                )
            )
    daily_pct: Decimal | None = None
    user_daily = _nonneg(user_daily_loss_pct)
    if user_daily > 0:
        from app.domain.institutional_trading.runtime_policy import (
            active_daily_loss_pct,
        )

        daily_pct = min(user_daily, active_daily_loss_pct())
    daily_reason = daily_budget_violation(
        daily,
        planned_risk=risk_usd,
        pct=daily_pct,
    )
    if daily_reason:
        violations.append(daily_reason)
    min_dist = Decimal(str(min_stop_distance or 0))
    if min_dist > 0 and (sl_dist < min_dist or tp_dist < min_dist):
        violations.append(
            f"OWNER_STOPS_LEVEL: SL {sl_dist} / TP {tp_dist} closer than broker "
            f"stops_level distance {min_dist}"
        )
    net = net_reward_risk(
        tp_distance=tp_dist,
        stop_distance=sl_dist,
        spread=spr,
        slippage=slippage,
        commission=fee,
        contract_size=cs,
        volume=vol,
        spread_already_in_stop=stop_includes_spread_buffer,
    )
    rr = net.ratio if net.ratio is not None else Decimal("0")
    if rr < rr_floor:
        label = (
            "net reward:risk"
            if slip > 0 or net.commission_included or stop_includes_spread_buffer
            else "reward:risk after spread"
        )
        violations.append(f"OWNER_MIN_RR: {label} {rr.quantize(_CENT)} < {rr_floor}")
    week_cap = weekly_loss_limit_pct()
    if week_cap > 0:
        if weekly_pnl is None:
            violations.append(
                "WEEKLY_PNL_UNAVAILABLE: weekly loss limit is configured "
                "but weekly P/L could not be read"
            )
        else:
            week = Decimal(str(weekly_pnl))
            if week < 0 and eq > 0:
                loss = -week
                base = eq + loss
                cap_usd = (base * week_cap / _PCT).quantize(_CENT, rounding=ROUND_DOWN)
                if loss > cap_usd:
                    violations.append(
                        f"OWNER_WEEKLY_LOSS: weekly loss {loss} > {cap_usd} "
                        f"({week_cap}% of week-start equity)"
                    )
    dd_cap = drawdown_limit_pct()
    if dd_cap > 0:
        if not peak_known or peak_equity is None:
            violations.append(
                "DRAWDOWN_BASE_UNAVAILABLE: overall drawdown halt is configured "
                "but the stored equity peak could not be read"
            )
        else:
            peak = Decimal(str(peak_equity))
            if peak <= 0 or eq <= 0:
                violations.append(
                    "DRAWDOWN_BASE_UNAVAILABLE: overall drawdown halt is configured "
                    "but the stored equity peak could not be read"
                )
            else:
                loss = peak - eq
                if loss < 0:
                    loss = Decimal("0")
                cap_usd = (peak * dd_cap / _PCT).quantize(_CENT, rounding=ROUND_DOWN)
                if loss > cap_usd:
                    violations.append(
                        f"OWNER_DRAWDOWN: equity drawdown {loss} > {cap_usd} "
                        f"({dd_cap}% of peak equity {peak})"
                    )
    return violations


def presend_owner_violations(
    *,
    symbol: str,
    side: str,
    volume: Decimal,
    request_price: Decimal,
    bid: Decimal,
    ask: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    plan_price: Decimal | None,
    contract_size: Decimal,
    equity: Decimal,
    min_stop_distance: Decimal = Decimal("0"),
    rr_buffer: Decimal = OWNER_RR_SLIPPAGE_BUFFER,
    now: datetime | None = None,
    weekly_pnl: Decimal | None = None,
    peak_equity: Decimal | None = None,
    peak_known: bool = True,
    slippage: Decimal | None = None,
    tick_size: Decimal | None = None,
    commission: Decimal | None = None,
    stop_includes_spread_buffer: bool = False,
    daily: DailyLossContext | None = None,
    user_planned_risk_pct: Decimal | None = None,
    user_daily_loss_pct: Decimal | None = None,
) -> list[str]:
    """Final owner check on the exact tick the market request was built from.

    Re-runs the full owner entry check with ``request_price`` and that tick's
    spread, the stop-shrink guard against the plan price, and (when
    ``rr_buffer`` > 0) RR with the fill assumed ``rr_buffer`` worse.
    ``slippage`` is the order deviation in price units, not an extra spread.

    Pass ``stop_includes_spread_buffer=True`` when the SL already embeds the
    owner spread buffer (LIVE structure path) — otherwise spread is
    double-counted and valid setups fail at ``order_send``.
    """
    spread = Decimal(str(ask)) - Decimal(str(bid))
    violations = evaluate_owner_entry(
        symbol=symbol,
        side=side,
        volume=volume,
        entry=request_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        spread=spread,
        contract_size=contract_size,
        equity=equity,
        min_stop_distance=min_stop_distance,
        now=now,
        weekly_pnl=weekly_pnl,
        peak_equity=peak_equity,
        peak_known=peak_known,
        slippage=slippage,
        tick_size=tick_size,
        commission=commission,
        stop_includes_spread_buffer=stop_includes_spread_buffer,
        daily=daily,
        user_planned_risk_pct=user_planned_risk_pct,
        user_daily_loss_pct=user_daily_loss_pct,
    )
    drift = stop_shrink_violation(
        side=side,
        signal_price=plan_price,
        live_price=request_price,
        stop_loss=stop_loss,
    )
    if drift:
        violations.append(drift)
    buf = Decimal(str(rr_buffer or 0))
    if buf > 0 and stop_loss is not None and take_profit is not None:
        from app.domain.institutional_trading.runtime_policy import (
            active_min_reward_risk,
        )

        tp_dist = abs(Decimal(str(take_profit)) - request_price)
        stop_dist = abs(request_price - Decimal(str(stop_loss)))
        # Worse-fill buffer: shrink reward, widen risk. Reuse net_reward_risk so
        # commission + spread-buffer flag match evaluate_owner_entry.
        net = net_reward_risk(
            tp_distance=max(tp_dist - buf, Decimal("0")),
            stop_distance=stop_dist + buf,
            spread=spread,
            slippage=slippage,
            commission=commission,
            contract_size=contract_size,
            volume=volume,
            spread_already_in_stop=stop_includes_spread_buffer,
        )
        rr = net.ratio if net.ratio is not None else Decimal("0")
        rr_floor = active_min_reward_risk()
        if rr < rr_floor:
            violations.append(
                f"OWNER_MIN_RR_SLIPPAGE: reward:risk {rr.quantize(_CENT)} with "
                f"{buf} slippage buffer < {rr_floor}"
            )
    return [f"PRESEND {v}" for v in violations]
