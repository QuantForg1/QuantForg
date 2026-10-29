"""Owner live limits (MICRO_LIVE 2026-10-22, real account, Gold only).

Single source for the owner's hard trading limits. USD caps win over percent
caps when smaller. Every other risk layer may be stricter, never looser.

``evaluate_owner_entry`` is the final deterministic guard for NEW entries on
the live submit path. Closes and SL/TP management are never blocked here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from app.domain.trading.gold_only import is_gold_symbol

OWNER_MAX_LOT = Decimal("0.01")
# Planned SL loss band at 0.01 lot: at least $1.00, at most $3.00.
OWNER_MIN_SL_RISK_USD = Decimal("1.00")
OWNER_MAX_SL_RISK_USD = Decimal("3.00")
# Percent per-trade cap only applies once equity is above this threshold.
OWNER_SL_RISK_PCT = Decimal("2.0")
OWNER_SL_RISK_PCT_EQUITY_THRESHOLD = Decimal("100")
# Daily stop = max(floor USD, pct of start-of-day equity), never above ceiling pct.
OWNER_DAILY_LOSS_FLOOR_USD = Decimal("5.00")
OWNER_DAILY_LOSS_PCT = Decimal("3.0")
OWNER_DAILY_LOSS_CEILING_PCT = Decimal("10.0")
OWNER_MIN_REWARD_RISK = Decimal("1.50")
OWNER_MAX_OPEN_POSITIONS = 1
OWNER_MAX_ENTRIES_PER_CYCLE = 1
OWNER_MAX_CONSECUTIVE_LOSSES = 3
# "Pause for the day" after the loss streak — conservative full-day cooldown.
OWNER_LOSS_STREAK_COOLDOWN_MINUTES = 24 * 60
# MICRO_LIVE: fixed USD stops and a hard equity floor.
OWNER_DAILY_STOP_USD = Decimal("5.00")
OWNER_WEEKLY_STOP_USD = Decimal("10.00")
OWNER_EQUITY_FLOOR_USD = Decimal("40.00")
# New entries only during London + New York (UTC hours, end exclusive).
OWNER_SESSION_START_HOUR_UTC = 7
OWNER_SESSION_END_HOUR_UTC = 17
OWNER_MAX_SPREAD = Decimal("0.45")

_CENT = Decimal("0.01")


def max_sl_risk_usd(equity: Decimal) -> Decimal:
    """Per-trade planned SL-loss cap in USD for the given equity."""
    cap = OWNER_MAX_SL_RISK_USD
    eq = Decimal(str(equity or 0))
    if eq > OWNER_SL_RISK_PCT_EQUITY_THRESHOLD:
        pct_cap = (eq * OWNER_SL_RISK_PCT / Decimal("100")).quantize(
            _CENT, rounding=ROUND_DOWN
        )
        cap = min(cap, pct_cap)
    return cap


def daily_loss_cap_usd(
    start_of_day_equity: Decimal, pct: Decimal = OWNER_DAILY_LOSS_PCT
) -> Decimal:
    """Owner daily stop in USD: a fixed $5.00 (MICRO_LIVE).

    ``pct`` is kept for callers that still pass a percent; it no longer
    changes the USD stop.
    """
    _ = pct
    sod = Decimal(str(start_of_day_equity or 0))
    if sod <= 0:
        return Decimal("0")
    return OWNER_DAILY_STOP_USD


def daily_loss_exceeded(
    *,
    daily_pnl: Decimal,
    base_now: Decimal,
    pct: Decimal = OWNER_DAILY_LOSS_PCT,
) -> bool:
    """True when today's loss is strictly above the owner daily stop.

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
    """Owner daily stop expressed as a percent of ``base_now``.

    For layers that compare ``loss / base_now`` against a percent threshold.
    """
    base = Decimal(str(base_now or 0))
    if base <= 0:
        return Decimal(str(pct))
    loss = max(-Decimal(str(daily_pnl or 0)), Decimal("0"))
    cap_usd = daily_loss_cap_usd(base + loss, pct)
    return (cap_usd / base * Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_DOWN
    )


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
) -> list[str]:
    """Return owner-limit violations for a NEW entry (empty list = allowed).

    Reward:risk counts the spread once, on the risk leg:
    ``|tp - entry| / (|entry - sl| + spread)`` must be >= 1.50
    (e.g. SL 2.00 + spread 0.44 needs a TP at least 3.66 away).
    ``min_stop_distance`` is the broker stops_level in price units
    (``point * stops_level``); SL and TP must both be at least that far away.
    """
    reasons: list[str] = []
    vol = Decimal(str(volume or 0))
    px = Decimal(str(entry or 0))
    cs = Decimal(str(contract_size or 0))
    side_u = (side or "").strip().upper()

    # Policy violations are collected; missing inputs stop evaluation below.
    violations: list[str] = []
    if not is_gold_symbol(symbol):
        violations.append(f"OWNER_GOLD_ONLY: symbol {symbol!r} is not XAUUSD")
    if vol > OWNER_MAX_LOT:
        violations.append(f"OWNER_MAX_LOT: volume {vol} > {OWNER_MAX_LOT}")
    if vol <= 0:
        reasons.append("OWNER_VOLUME_INVALID: volume must be > 0")
    if side_u not in {"BUY", "SELL"}:
        reasons.append(f"OWNER_SIDE_INVALID: {side!r}")
    if px <= 0:
        reasons.append("OWNER_ENTRY_UNKNOWN: entry price unresolved")
    if cs <= 0:
        reasons.append("OWNER_CONTRACT_UNKNOWN: contract size unresolved")
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
    risk_usd = (sl_dist * cs * vol).quantize(_CENT)
    cap = max_sl_risk_usd(equity)
    if risk_usd > cap:
        violations.append(f"OWNER_SL_RISK: planned SL loss ${risk_usd} > ${cap}")
    if risk_usd < OWNER_MIN_SL_RISK_USD:
        violations.append(
            f"OWNER_SL_RISK_BELOW_MIN: planned SL loss ${risk_usd} "
            f"must be at least ${OWNER_MIN_SL_RISK_USD}"
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


def weekly_loss_exceeded(weekly_pnl: Decimal) -> bool:
    """True when this UTC week's realized loss is strictly above $10.00."""
    pnl = Decimal(str(weekly_pnl or 0))
    return pnl < 0 and -pnl > OWNER_WEEKLY_STOP_USD


def equity_floor_breached(equity: Decimal) -> bool:
    """True at or below the $40.00 hard floor."""
    return Decimal(str(equity or 0)) <= OWNER_EQUITY_FLOOR_USD


def in_owner_session(now: datetime) -> bool:
    """London + New York only: 07:00 <= UTC hour < 17:00."""
    clock = now if now.tzinfo else now.replace(tzinfo=UTC)
    hour = clock.astimezone(UTC).hour
    return OWNER_SESSION_START_HOUR_UTC <= hour < OWNER_SESSION_END_HOUR_UTC


def next_utc_day(now: datetime) -> datetime:
    """Midnight UTC that starts the next day (loss-streak pause end)."""
    clock = now if now.tzinfo else now.replace(tzinfo=UTC)
    day = clock.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day + timedelta(days=1)


def utc_week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of the current week."""
    clock = now if now.tzinfo else now.replace(tzinfo=UTC)
    day = clock.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def evaluate_micro_live_entry(
    *,
    now: datetime,
    equity: Decimal | None,
    spread: Decimal | None,
    daily_pnl: Decimal | None,
    weekly_pnl: Decimal | None,
    pnl_trusted: bool,
    equity_floor_latched: bool,
) -> list[str]:
    """MICRO_LIVE account gates for a NEW entry (empty list = allowed).

    Closes and SL tightening never come through here. Unknown P/L or equity
    fails closed.
    """
    reasons: list[str] = []
    if equity_floor_latched:
        reasons.append(
            "MICRO_EQUITY_FLOOR_LATCHED: equity reached the "
            f"${OWNER_EQUITY_FLOOR_USD} floor — owner must clear it"
        )
    if equity is None:
        reasons.append("MICRO_EQUITY_UNKNOWN: cannot verify the equity floor")
    elif equity_floor_breached(equity):
        reasons.append(
            f"MICRO_EQUITY_FLOOR: equity ${equity} <= ${OWNER_EQUITY_FLOOR_USD}"
        )
    if not in_owner_session(now):
        reasons.append(
            "MICRO_SESSION_CLOSED: entries only "
            f"{OWNER_SESSION_START_HOUR_UTC:02d}:00-"
            f"{OWNER_SESSION_END_HOUR_UTC:02d}:00 UTC"
        )
    if spread is None:
        reasons.append("MICRO_SPREAD_UNKNOWN")
    elif Decimal(str(spread)) > OWNER_MAX_SPREAD:
        reasons.append(f"MICRO_SPREAD: {spread} > {OWNER_MAX_SPREAD}")
    if not pnl_trusted or daily_pnl is None or weekly_pnl is None:
        reasons.append("MICRO_PNL_UNVERIFIED: daily/weekly realized P/L unavailable")
    else:
        if (
            Decimal(str(daily_pnl)) < 0
            and -Decimal(str(daily_pnl)) > OWNER_DAILY_STOP_USD
        ):
            reasons.append(
                f"MICRO_DAILY_STOP: loss ${-Decimal(str(daily_pnl))} > "
                f"${OWNER_DAILY_STOP_USD}"
            )
        if weekly_loss_exceeded(Decimal(str(weekly_pnl))):
            reasons.append(
                f"MICRO_WEEKLY_STOP: loss ${-Decimal(str(weekly_pnl))} > "
                f"${OWNER_WEEKLY_STOP_USD}"
            )
    return reasons
