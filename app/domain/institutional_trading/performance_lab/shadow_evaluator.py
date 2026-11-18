"""Shadow Signal Evaluator: HYPOTHETICAL outcomes of recorded signals.

Read-only research; never feeds LIVE parameters. Each recorded signal
(``signal_history`` row id = intent id) is replayed against the quotes that
were recorded after it. Nothing is invented:

- Executable sides: BUY enters at ask and exits at bid; SELL enters at bid and
  exits at ask. Slippage is charged on both sides; commission (USD per 0.01
  lot, the owner's fixed lot) is charged once, as the policy tariff defines it.
  Swap is zero for a <= 30 min hold unless the window crosses the daily
  rollover, which is flagged.
- Quotes are scan snapshots, not ticks. A gap longer than ``STALE_GAP_S``
  before the outcome is known makes the observation ``incomplete``. A level
  first seen across after a gap longer than ``AMBIGUOUS_GAP_S`` is
  ``ambiguous`` (the other level may have been touched between snapshots).
- Bracket: stop = 1 x stop ATR, target = ``TARGET_R`` x stop. This is an
  ATR bracket, not the engine's own SL/TP proposal (not recorded yet).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

HORIZONS_MIN = (1, 5, 15, 30)
TARGET_R = 1.5
STALE_GAP_S = 90.0
AMBIGUOUS_GAP_S = 45.0
HORIZON_TOLERANCE_S = 60.0
DEFAULT_SLIPPAGE = 0.05  # price units per side
USD_PER_PRICE_UNIT_AT_MIN_LOT = 1.0  # XAUUSD: 100 oz x 0.01 lot
ROLLOVER_HOUR_UTC = 21
MIN_EVIDENCE = 30
_FACTOR_KEYS = ("trend_strength", "volatility", "mtf", "h1_bias", "m15_structure")


@dataclass(frozen=True, slots=True)
class Quote:
    at: datetime
    bid: float
    ask: float


@dataclass(frozen=True, slots=True)
class ShadowSignal:
    signal_id: str
    at: datetime
    side: str
    bid: float
    ask: float
    stop_atr: float | None
    accepted: bool
    blocking_gate: str | None
    quality: int | None = None
    confidence: int | None = None
    strategy: str | None = None
    session: str | None = None
    factors: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Costs:
    slippage: float = DEFAULT_SLIPPAGE
    commission_usd: float | None = 0.0  # None = unknown tariff


def gate_family(blocking_gate: str | None, *, accepted: bool) -> str:
    if accepted:
        return "ACCEPTED"
    text = str(blocking_gate or "").strip()
    if not text:
        return "UNKNOWN"
    head = text.split(";", 1)[0].split(":", 1)[0].strip()
    return head[:60] or "UNKNOWN"


def news_condition(blocking_gate: str | None) -> str:
    return "news_blackout" if "news" in str(blocking_gate or "").lower() else "clear"


def regime_proxy(factors: dict[str, Any]) -> str:
    """Coarse label from recorded factor scores (not a regime-engine verdict)."""
    try:
        trend = float(factors.get("trend_strength"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown"
    if trend >= 70:
        return "trending"
    if trend <= 30:
        return "ranging"
    return "mixed"


def quality_band(quality: int | None) -> str:
    if quality is None:
        return "unknown"
    if quality >= 90:
        return "90+"
    if quality >= 80:
        return "80-89"
    if quality >= 70:
        return "70-79"
    return "<70"


def spread_band(spread: float) -> str:
    if spread < 0.30:
        return "<0.30"
    if spread < 0.40:
        return "0.30-0.39"
    if spread <= 0.45:
        return "0.40-0.45"
    return ">0.45"


def _entry(signal: ShadowSignal, slip: float) -> float:
    return signal.ask + slip if signal.side == "BUY" else signal.bid - slip


def _exit(side: str, quote: Quote, slip: float) -> float:
    return quote.bid - slip if side == "BUY" else quote.ask + slip


def _move(side: str, entry: float, exit_: float) -> float:
    return exit_ - entry if side == "BUY" else entry - exit_


def _crosses_rollover(start: datetime, end: datetime) -> bool:
    edge = start.replace(hour=ROLLOVER_HOUR_UTC, minute=0, second=0, microsecond=0)
    if edge < start:
        edge += timedelta(days=1)
    return start < edge <= end


def evaluate_signal(
    signal: ShadowSignal, later: list[Quote], costs: Costs | None = None
) -> dict[str, Any]:
    """One HYPOTHETICAL outcome. ``later`` = quotes after the signal, sorted."""
    cost = costs or Costs()
    slip = cost.slippage
    entry = _entry(signal, slip)
    commission = cost.commission_usd
    end = signal.at + timedelta(minutes=max(HORIZONS_MIN))
    window = [q for q in later if q.at <= end + timedelta(seconds=HORIZON_TOLERANCE_S)]
    moves: dict[str, float | None] = {}
    for minutes in HORIZONS_MIN:
        cutoff = signal.at + timedelta(minutes=minutes)
        quote = next((q for q in window if q.at >= cutoff), None)
        if quote is not None and (quote.at - cutoff).total_seconds() <= (
            HORIZON_TOLERANCE_S
        ):
            moves[f"m{minutes}"] = round(
                _move(signal.side, entry, _exit(signal.side, quote, slip)), 3
            )
        else:
            moves[f"m{minutes}"] = None
    status = "complete"
    reasons: list[str] = []
    bracket: str | None = None
    r_value: float | None = None
    stop = signal.stop_atr if signal.stop_atr and signal.stop_atr > 0 else None
    if stop is None:
        status, reasons = "incomplete", ["stop_atr_missing"]
    else:
        target = stop * TARGET_R
        prev_at = signal.at
        for quote in window:
            if quote.at > end:
                break
            gap = (quote.at - prev_at).total_seconds()
            move = _move(signal.side, entry, _exit(signal.side, quote, slip))
            hit = "stop" if move <= -stop else "target" if move >= target else None
            if hit is not None:
                bracket = hit
                r_value = -1.0 if hit == "stop" else TARGET_R
                if gap > AMBIGUOUS_GAP_S:
                    status, reasons = "ambiguous", [f"level_seen_after_{int(gap)}s_gap"]
                break
            if gap > STALE_GAP_S:
                status, reasons = "incomplete", [f"stale_quotes_{int(gap)}s"]
                break
            prev_at = quote.at
        if bracket is None and status == "complete":
            final = moves[f"m{max(HORIZONS_MIN)}"]
            if final is None:
                status, reasons = "incomplete", ["no_quote_at_30m"]
            else:
                bracket, r_value = "timeout", round(final / stop, 3)
    net_price = moves[f"m{max(HORIZONS_MIN)}"]
    if bracket in {"stop", "target"} and stop is not None:
        net_price = -stop if bracket == "stop" else stop * TARGET_R
    net_usd: float | None = None
    if net_price is not None and commission is not None and status != "incomplete":
        net_usd = round(net_price * USD_PER_PRICE_UNIT_AT_MIN_LOT - commission, 3)
    if commission is None:
        reasons.append("commission_unknown")
    return {
        "signal_id": signal.signal_id,
        "observed_at": signal.at.isoformat(),
        "side": signal.side,
        "accepted": signal.accepted,
        "blocking_gate": signal.blocking_gate,
        "gate_family": gate_family(signal.blocking_gate, accepted=signal.accepted),
        "news_condition": news_condition(signal.blocking_gate),
        "strategy": signal.strategy,
        "session": signal.session,
        "hour_utc": signal.at.hour,
        "quality": signal.quality,
        "confidence": signal.confidence,
        "regime_proxy": regime_proxy(signal.factors),
        "factors": {k: signal.factors[k] for k in _FACTOR_KEYS if k in signal.factors},
        "entry_price": round(entry, 3),
        "spread": round(signal.ask - signal.bid, 3),
        "stop_distance": stop,
        "target_distance": round(stop * TARGET_R, 3) if stop else None,
        "slippage_per_side": slip,
        "commission_usd": commission,
        "crosses_rollover": _crosses_rollover(signal.at, end),
        **{f"move_{k}": v for k, v in moves.items()},
        "bracket": bracket,
        "r_multiple": r_value,
        "net_usd_min_lot": net_usd,
        "status": status,
        "status_reasons": reasons,
    }


def evaluate_pending(
    signals: list[ShadowSignal],
    quotes: list[Quote],
    *,
    already: set[str],
    now: datetime,
    costs: Costs | None = None,
) -> list[dict[str, Any]]:
    """Evaluate each signal once, only after its 30 min window has closed."""
    ordered = sorted(quotes, key=lambda q: q.at)
    horizon = timedelta(minutes=max(HORIZONS_MIN), seconds=HORIZON_TOLERANCE_S)
    out: list[dict[str, Any]] = []
    seen: set[str] = set(already)
    for signal in sorted(signals, key=lambda s: s.at):
        if signal.signal_id in seen or signal.at + horizon > now:
            continue
        seen.add(signal.signal_id)
        later = [q for q in ordered if q.at > signal.at]
        out.append(evaluate_signal(signal, later, costs))
    return out


def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    done = [r for r in rows if r["status"] == "complete"]
    out: dict[str, Any] = {
        "signals": len(rows),
        "evaluated": len(done),
        "incomplete": sum(1 for r in rows if r["status"] == "incomplete"),
        "ambiguous": sum(1 for r in rows if r["status"] == "ambiguous"),
    }
    for minutes in HORIZONS_MIN:
        key = f"move_m{minutes}"
        vals = [r[key] for r in done if r.get(key) is not None]
        out[f"avg_net_move_{minutes}m"] = (
            round(sum(vals) / len(vals), 3) if vals else None
        )
    nets = [r["net_usd_min_lot"] for r in done if r["net_usd_min_lot"] is not None]
    out["positive"] = sum(1 for v in nets if v > 0)
    out["negative"] = sum(1 for v in nets if v <= 0)
    out["avg_net_usd_min_lot"] = round(sum(nets) / len(nets), 3) if nets else None
    rs = [r["r_multiple"] for r in done if r["r_multiple"] is not None]
    out["expectancy_r"] = round(sum(rs) / len(rs), 3) if rs else None
    missed = [
        r["net_usd_min_lot"]
        for r in done
        if not r["accepted"] and r["net_usd_min_lot"] is not None
    ]
    # Positive = profit the filters left on the table; negative = loss avoided.
    out["opportunity_cost_usd_min_lot"] = round(sum(missed), 3)
    out["evidence"] = "ok" if len(done) >= MIN_EVIDENCE else "insufficient_data"
    return out


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key)), []).append(row)
    return {name: _bucket(groups[name]) for name in sorted(groups)}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = [
        r
        | {
            "quality_band": quality_band(r.get("quality")),
            "spread_band": spread_band(float(r.get("spread") or 0.0)),
            "hour": f"{int(r.get('hour_utc') or 0):02d}",
        }
        for r in rows
    ]
    return {
        "label": "HYPOTHETICAL",
        "overall": _bucket(enriched),
        "by_strategy": _group(enriched, "strategy"),
        "by_side": _group(enriched, "side"),
        "by_regime_proxy": _group(enriched, "regime_proxy"),
        "by_rejection_reason": _group(enriched, "gate_family"),
        "by_quality_band": _group(enriched, "quality_band"),
        "by_spread_band": _group(enriched, "spread_band"),
        "by_hour_utc": _group(enriched, "hour"),
        "by_news_condition": _group(enriched, "news_condition"),
    }
