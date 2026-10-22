"""Owner live limits (2026-10-22 final decision, Gold only, real account).

Single source for the owner's hard trading limits. Every dollar amount is
derived from live equity; nothing below is a fixed USD cap. Every other risk
layer may be stricter, never looser.

- Max PLANNED risk per trade: 9% of the risk reference (live equity; $4.50 at
  $50). Planned risk = (|entry - SL| + spread) x contract size x volume. This is
  a planned maximum, not a cap on realised loss: slippage, gaps, commissions
  and execution failures can make a loss larger.
- Daily loss limit: 19% of the UTC day's starting equity ($9.50 at $50).
- No independent overall-drawdown limit.
- Stop loss: max(2.5 x ATR(M1|M5), beyond the nearest structure + spread).
  A stop is never shrunk to fit the budget: too wide -> no trade.
- Reward:risk after spread >= 1.50: |tp - entry| / (|entry - sl| + spread).
- Entries 07:00-17:00 UTC (London + New York), spread <= 0.45.
- Volume 0.01 (gateway max); 1 open position; 1 entry per cycle.
- 3 consecutive losses pause new entries until the next UTC day.

``evaluate_owner_entry`` is the final deterministic guard for NEW entries on
the live submit path. Closes and SL/TP management are never blocked here.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal, InvalidOperation

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

OWNER_MAX_LOT = Decimal("0.01")
# Starting reference capital (configurable). Live equity is the risk reference;
# this value is the documented starting point and the $-figures shown at rest.
OWNER_RISK_REFERENCE_USD = _env_decimal("OWNER_RISK_REFERENCE_USD", "50")
OWNER_MAX_PLANNED_RISK_PCT = Decimal("9.0")
OWNER_DAILY_LOSS_PCT = Decimal("19.0")
# Weekly / monthly guards sit above the daily stop so one maximum loss (or one
# full daily stop) never blocks the week: weekly = 2 daily stops, monthly = 3.
OWNER_WEEKLY_LOSS_PCT = OWNER_DAILY_LOSS_PCT * 2
OWNER_MONTHLY_LOSS_PCT = OWNER_DAILY_LOSS_PCT * 3
OWNER_MIN_REWARD_RISK = Decimal("1.50")
OWNER_MAX_SPREAD = Decimal("0.45")
OWNER_SESSION_START_UTC = time(7, 0)
OWNER_SESSION_END_UTC = time(17, 0)
OWNER_SL_ATR_MULTIPLIER = _env_decimal("OWNER_SL_ATR_MULTIPLIER", "2.5")
OWNER_SL_ATR_TIMEFRAME = (os.environ.get("OWNER_SL_ATR_TIMEFRAME") or "M1").strip().upper()
if OWNER_SL_ATR_TIMEFRAME not in {"M1", "M5"}:
    OWNER_SL_ATR_TIMEFRAME = "M1"
OWNER_MAX_OPEN_POSITIONS = 1
OWNER_MAX_ENTRIES_PER_CYCLE = 1
OWNER_MAX_CONSECUTIVE_LOSSES = 3
# Upper bound for the streak pause; the pause itself ends at the next UTC day.
OWNER_LOSS_STREAK_COOLDOWN_MINUTES = 24 * 60

# Compatibility names used by other layers (values at the reference capital).
OWNER_SL_RISK_PCT = OWNER_MAX_PLANNED_RISK_PCT
# No minimum planned-risk floor: the stop comes from ATR/structure, not a $ band.
OWNER_MIN_SL_RISK_USD = Decimal("0")
OWNER_DAILY_LOSS_CEILING_PCT = OWNER_DAILY_LOSS_PCT


def max_planned_risk_usd(equity: Decimal) -> Decimal:
    """9% of the risk reference (live equity), rounded down to the cent."""
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    return (eq * OWNER_MAX_PLANNED_RISK_PCT / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


# Planned-risk cap at the reference capital ($4.50 at $50) for static configs.
OWNER_MAX_SL_RISK_USD = max_planned_risk_usd(OWNER_RISK_REFERENCE_USD)


def max_sl_risk_usd(equity: Decimal) -> Decimal:
    """Per-trade planned-loss cap in USD for the given equity (alias)."""
    return max_planned_risk_usd(equity)


def planned_risk_usd(
    *,
    stop_distance: Decimal,
    spread: Decimal | None,
    contract_size: Decimal,
    volume: Decimal,
) -> Decimal:
    """(|entry - SL| + spread) x contract size x volume, to the cent."""
    spr = Decimal(str(spread or 0))
    if spr < 0:
        spr = Decimal("0")
    dist = abs(Decimal(str(stop_distance or 0)))
    cs = Decimal(str(contract_size))
    vol = Decimal(str(volume))
    return ((dist + spr) * cs * vol).quantize(_CENT)


def daily_loss_cap_usd(
    start_of_day_equity: Decimal, pct: Decimal = OWNER_DAILY_LOSS_PCT
) -> Decimal:
    """Daily stop in USD: pct (max 19%) of the UTC day's starting equity."""
    sod = Decimal(str(start_of_day_equity or 0))
    if sod <= 0:
        return Decimal("0")
    eff = min(Decimal(str(pct)), OWNER_DAILY_LOSS_PCT)
    return (sod * eff / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


def daily_loss_exceeded(
    *,
    daily_pnl: Decimal,
    base_now: Decimal,
    pct: Decimal = OWNER_DAILY_LOSS_PCT,
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
    pct: Decimal = OWNER_DAILY_LOSS_PCT,
) -> Decimal:
    """Daily stop expressed as a percent of ``base_now``.

    For layers that compare ``loss / base_now`` against a percent threshold.
    """
    base = Decimal(str(base_now or 0))
    if base <= 0:
        return Decimal(str(pct))
    loss = max(-Decimal(str(daily_pnl or 0)), Decimal("0"))
    cap_usd = daily_loss_cap_usd(base + loss, pct)
    return (cap_usd / base * _PCT).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def in_owner_session(now: datetime | None = None) -> bool:
    """London + New York: 07:00 <= UTC time < 17:00."""
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    t = clock.astimezone(UTC).time()
    return OWNER_SESSION_START_UTC <= t < OWNER_SESSION_END_UTC


def next_utc_day_start(now: datetime | None = None) -> datetime:
    """Start of the next UTC day (end of the loss-streak pause)."""
    clock = now or datetime.now(UTC)
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
) -> list[str]:
    """Return owner-limit violations for a NEW entry (empty list = allowed).

    Planned risk includes the spread once:
    ``(|entry - sl| + spread) x contract x volume <= 9% of equity``.
    Reward:risk counts the spread once, on the risk leg:
    ``|tp - entry| / (|entry - sl| + spread)`` must be >= 1.50.
    ``min_stop_distance`` is the broker stops_level in price units
    (``point * stops_level``); SL and TP must both be at least that far away.
    """
    reasons: list[str] = []
    vol = Decimal(str(volume or 0))
    px = Decimal(str(entry or 0))
    cs = Decimal(str(contract_size or 0))
    eq = Decimal(str(equity or 0))
    side_u = (side or "").strip().upper()

    # Policy violations are collected; missing inputs stop evaluation below.
    violations: list[str] = []
    if not is_gold_symbol(symbol):
        violations.append(f"OWNER_GOLD_ONLY: symbol {symbol!r} is not XAUUSD")
    if vol > OWNER_MAX_LOT:
        violations.append(f"OWNER_MAX_LOT: volume {vol} > {OWNER_MAX_LOT}")
    if not in_owner_session(now):
        violations.append(
            "OWNER_SESSION: entries only 07:00-17:00 UTC (London + New York)"
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
    if spr > OWNER_MAX_SPREAD:
        violations.append(f"OWNER_MAX_SPREAD: spread {spr} > {OWNER_MAX_SPREAD}")
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
    risk_usd = planned_risk_usd(
        stop_distance=sl_dist, spread=spr, contract_size=cs, volume=vol
    )
    cap = max_planned_risk_usd(eq)
    if risk_usd > cap:
        violations.append(
            f"OWNER_SL_RISK: planned risk ${risk_usd} > ${cap} "
            f"({OWNER_MAX_PLANNED_RISK_PCT}% of equity {eq})"
        )
    min_dist = Decimal(str(min_stop_distance or 0))
    if min_dist > 0 and (sl_dist < min_dist or tp_dist < min_dist):
        violations.append(
            f"OWNER_STOPS_LEVEL: SL {sl_dist} / TP {tp_dist} closer than broker "
            f"stops_level distance {min_dist}"
        )
    rr = tp_dist / (sl_dist + spr)
    if rr < OWNER_MIN_REWARD_RISK:
        violations.append(
            f"OWNER_MIN_RR: reward:risk after spread {rr.quantize(_CENT)} "
            f"< {OWNER_MIN_REWARD_RISK}"
        )
    return violations
