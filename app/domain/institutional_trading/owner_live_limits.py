"""Owner live limits (2026-10-22 final decision, Gold only, real account).

Single source for the owner's hard trading limits. Every dollar amount is
derived from live equity; nothing below is a fixed USD cap. Every other risk
layer may be stricter, never looser.

- Max PLANNED risk per trade: 9% of the risk reference (live equity; $4.50 at
  $50). Planned risk = (|entry - SL| + spread) x contract size x volume. This is
  a planned maximum, not a cap on realised loss: slippage, gaps, commissions
  and execution failures can make a loss larger.
- Daily loss limit: 19% of the UTC day's starting equity ($9.50 at $50).
- No weekly, monthly or overall-drawdown limit (owner 2026-10-23).
- Stop loss: max(1.5 x ATR(M1|M5), beyond the nearest structure + spread).
  A stop is never shrunk to fit the budget: too wide -> no trade.
- Reward:risk after spread >= 1.50: |tp - entry| / (|entry - sl| + spread).
  TP is a real structure level: the nearest one that clears 1.50, at most
  the second level out (2026-10-23). Neither clears -> no trade.
- Entries any UTC hour, every day. Broker symbol session, weekend close,
  holidays, and maintenance remain the availability gate. Spread <= 0.45.
- Volume 0.01 (gateway max); 1 open position; 1 entry per cycle.
- No consecutive-loss pause (owner 2026-10-23).

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


def _now() -> datetime:
    """Clock for session / day-boundary defaults (tests pin it)."""
    return datetime.now(UTC)


OWNER_MAX_LOT = Decimal("0.01")
# Starting reference capital (configurable). Live equity is the risk reference;
# this value is the documented starting point and the $-figures shown at rest.
OWNER_RISK_REFERENCE_USD = _env_decimal("OWNER_RISK_REFERENCE_USD", "50")
OWNER_MAX_PLANNED_RISK_PCT = Decimal("9.0")
# Authoritative daily stop: 19% of the UTC day's starting equity.
# A loss equal to the cap does not halt; a loss above the cap does.
OWNER_DAILY_LOSS_PCT = Decimal("19.0")
# Weekly / monthly loss limits removed (0 = disabled, as for drawdown). Weekly
# and monthly P/L are still computed for reporting (summaries, journal).
OWNER_WEEKLY_LOSS_PCT = Decimal("0")
OWNER_MONTHLY_LOSS_PCT = Decimal("0")
OWNER_MIN_REWARD_RISK = Decimal("1.50")
# Owner 2026-10-26: the fixed Monday-Friday 07:00-17:00 desk window is retired.
# Eligibility is 00:00-23:59 UTC every day. Broker symbol sessions, weekend
# closures, holidays, and maintenance stay the availability gate. A stale
# OWNER_SESSION_* environment value cannot put the desk clock back.
OWNER_MAX_SPREAD = _env_decimal("OWNER_MAX_SPREAD", "0.45")
OWNER_SESSION_START_UTC = time(0, 0)
OWNER_SESSION_END_UTC = time(23, 59, 59, 999999)
# Owner 2026-10-23: 1.5 x ATR (was 2.5); structure + spread still wins when wider.
OWNER_SL_ATR_MULTIPLIER = _env_decimal("OWNER_SL_ATR_MULTIPLIER", "1.5")
# TP may move to the second structure level only when the first is < 1.50 RR.
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
# Hard floor on the AI trade quality of a robot entry (owner 2026-10-24: 80;
# lowered to 75 by the owner 2026-10-26). Fixed: no env override can lower it.
OWNER_MIN_TRADE_QUALITY = 75

# Compatibility names used by other layers (values at the reference capital).
OWNER_SL_RISK_PCT = OWNER_MAX_PLANNED_RISK_PCT
# No minimum planned-risk floor: the stop comes from ATR/structure, not a $ band.
OWNER_MIN_SL_RISK_USD = Decimal("0")
OWNER_DAILY_LOSS_CEILING_PCT = OWNER_DAILY_LOSS_PCT


def _active_planned_risk_pct() -> Decimal:
    """Saved policy may be stricter than 9%. It cannot be looser."""
    from app.domain.institutional_trading.runtime_policy import (
        active_max_planned_risk_pct,
    )

    return active_max_planned_risk_pct()


def max_aggregate_risk_usd(equity: Decimal) -> Decimal:
    """Shared open-risk budget. Never above the per-trade cap or 9%."""
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    from app.domain.institutional_trading.runtime_policy import (
        active_max_aggregate_open_risk_pct,
    )

    pct = min(active_max_aggregate_open_risk_pct(), _active_planned_risk_pct())
    return (eq * pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


def max_planned_risk_usd(equity: Decimal) -> Decimal:
    """Planned-risk cap for live equity, rounded down to the cent.

    The approved ceiling is 9%. An installed runtime policy may use a lower
    percent. A missing policy uses 9%.
    """
    eq = Decimal(str(equity or 0))
    if eq <= 0:
        return Decimal("0")
    pct = _active_planned_risk_pct()
    return (eq * pct / _PCT).quantize(_CENT, rounding=ROUND_DOWN)


# Planned-risk cap at the reference capital ($4.50 at $50) for static configs.
OWNER_MAX_SL_RISK_USD = max_planned_risk_usd(OWNER_RISK_REFERENCE_USD)


def owner_risk_cap_usd(
    *,
    equity: Decimal | None,
    configured: Decimal | None,
    reference_default: Decimal,
    positions: int = 1,
) -> Decimal:
    """Planned-risk cap from 9% of LIVE equity (owner, 2026-10-23).

    Static configs carry the cap at the $50 reference capital ($4.50); that
    default is replaced by 9% of live equity (x ``positions`` for an
    aggregate cap). A stricter explicitly configured cap stays.
    """
    eq = Decimal(str(equity or 0))
    if eq > 0 and (configured is None or configured == reference_default):
        return max_planned_risk_usd(eq) * positions
    return configured if configured is not None else reference_default


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
    start_of_day_equity: Decimal, pct: Decimal | None = None
) -> Decimal:
    """Daily stop in USD: pct (max 19%) of the UTC day's starting equity.

    ``pct is None`` uses the installed runtime policy, or 19% when no policy
    is installed. An explicit percent cannot exceed 19%.
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
    """True for every UTC clock time, Monday through Sunday.

    Owner 2026-10-26: 07:00-17:00 Monday-Friday is not a gate. Broker symbol
    sessions, weekend closures, holidays, and maintenance are enforced by
    broker session truth, not by this clock.
    """
    clock = now or _now()
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    utc = clock.astimezone(UTC)
    return OWNER_SESSION_START_UTC <= utc.time() <= OWNER_SESSION_END_UTC


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
    """Owner RR: |tp - entry| / (|entry - sl| + spread). None when undefined."""
    risk = stop_distance + max(spread, Decimal("0"))
    if risk <= 0 or tp_distance <= 0:
        return None
    return tp_distance / risk


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
) -> list[str]:
    """Return owner-limit violations for a NEW entry (empty list = allowed).

    Planned risk includes the spread once:
    ``(|entry - sl| + spread) x contract x volume <= 9% of equity``.
    Reward:risk counts the spread once, on the risk leg:
    ``|tp - entry| / (|entry - sl| + spread)`` must be >= 1.50.
    ``min_stop_distance`` is the broker stops_level in price units
    (``point * stops_level``); SL and TP must both be at least that far away.
    """
    from app.domain.institutional_trading.runtime_policy import (
        active_max_lot,
        active_max_spread,
        active_min_lot,
        active_min_reward_risk,
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
    risk_usd = planned_risk_usd(
        stop_distance=sl_dist, spread=spr, contract_size=cs, volume=vol
    )
    cap = max_planned_risk_usd(eq)
    if risk_usd > cap:
        violations.append(
            f"OWNER_SL_RISK: planned risk ${risk_usd} > ${cap} "
            f"({_active_planned_risk_pct()}% of equity {eq})"
        )
    min_dist = Decimal(str(min_stop_distance or 0))
    if min_dist > 0 and (sl_dist < min_dist or tp_dist < min_dist):
        violations.append(
            f"OWNER_STOPS_LEVEL: SL {sl_dist} / TP {tp_dist} closer than broker "
            f"stops_level distance {min_dist}"
        )
    rr = reward_risk_after_spread(
        tp_distance=tp_dist, stop_distance=sl_dist, spread=spr
    ) or Decimal("0")
    if rr < rr_floor:
        violations.append(
            f"OWNER_MIN_RR: reward:risk after spread {rr.quantize(_CENT)} "
            f"< {rr_floor}"
        )
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
) -> list[str]:
    """Final owner check on the exact tick the market request was built from.

    Re-runs the full owner entry check with ``request_price`` and that tick's
    spread, the stop-shrink guard against the plan price, and (when
    ``rr_buffer`` > 0) RR with the fill assumed ``rr_buffer`` worse.
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
        rr = reward_risk_after_spread(
            tp_distance=abs(Decimal(str(take_profit)) - request_price) - buf,
            stop_distance=abs(request_price - Decimal(str(stop_loss))) + buf,
            spread=spread,
        ) or Decimal("0")
        if rr < OWNER_MIN_REWARD_RISK:
            violations.append(
                f"OWNER_MIN_RR_SLIPPAGE: reward:risk {rr.quantize(_CENT)} with "
                f"{buf} slippage buffer < {OWNER_MIN_REWARD_RISK}"
            )
    return [f"PRESEND {v}" for v in violations]
