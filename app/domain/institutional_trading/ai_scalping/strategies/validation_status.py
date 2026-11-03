"""Strategy health / validation status for live influence weighting.

Uses independently recorded StrategyStatsBook outcomes only.
Never fabricates P&L. Never auto-promotes research plugins to live.
Never weakens Risk / OMS / MT5 gates — only reduces SOE selection influence.
"""

from __future__ import annotations

from typing import Any, Literal

HealthStatus = Literal[
    "insufficient_sample",
    "healthy",
    "watch",
    "deteriorating",
    "unknown",
]

# Closed-trade sample gates (matched outcomes only).
MIN_CLOSED_FOR_WATCH = 5
MIN_CLOSED_FOR_DETERIORATION = 8
MIN_CLOSED_FOR_HEALTHY_CLAIM = 12

# Soft performance thresholds — advisory influence only.
PF_DETERIORATING = 0.90
PF_WATCH = 1.00
EXPECTANCY_DETERIORATING = 0.0
WIN_RATE_DETERIORATING = 40.0  # percent


def _closed(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    try:
        return int(row.get("wins") or 0) + int(row.get("losses") or 0)
    except (TypeError, ValueError):
        return 0


def _pf(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    raw = row.get("profit_factor")
    if raw is None:
        gp = float(row.get("gross_profit") or 0)
        gl = float(row.get("gross_loss") or 0)
        if gl > 0:
            return gp / gl
        if gp > 0 and _closed(row) >= 1:
            # Undefined / infinite PF — only informative with a sample.
            return None
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _expectancy(row: dict[str, Any] | None) -> float | None:
    """Average net PnL per closed trade from gross profit/loss counts."""
    if not row:
        return None
    n = _closed(row)
    if n <= 0:
        return None
    gp = float(row.get("gross_profit") or 0)
    gl = float(row.get("gross_loss") or 0)
    running = row.get("running_pnl")
    if running is not None:
        try:
            return float(running) / n
        except (TypeError, ValueError):
            pass
    return (gp - gl) / n


def classify_strategy_health(row: dict[str, Any] | None) -> dict[str, Any]:
    """Classify one strategy from production stats (or empty → insufficient)."""
    closed = _closed(row)
    pf = _pf(row)
    exp = _expectancy(row)
    wr = None
    if row and row.get("win_rate") is not None:
        try:
            wr = float(row.get("win_rate"))
        except (TypeError, ValueError):
            wr = None

    status: HealthStatus = "insufficient_sample"
    flags: list[str] = []
    live_influence_allowed = True
    reason = "Insufficient closed-trade sample — neutral influence"

    if closed < MIN_CLOSED_FOR_WATCH:
        status = "insufficient_sample"
        reason = f"closed={closed} < {MIN_CLOSED_FOR_WATCH} — no deterioration claim"
    else:
        deteriorating = False
        watch = False
        enough = closed >= MIN_CLOSED_FOR_DETERIORATION
        if pf is not None and pf < PF_DETERIORATING and enough:
            deteriorating = True
            flags.append(f"profit_factor={pf:.3f}<{PF_DETERIORATING}")
        if exp is not None and exp < EXPECTANCY_DETERIORATING and enough:
            deteriorating = True
            flags.append(f"expectancy={exp:.4f}<{EXPECTANCY_DETERIORATING}")
        if wr is not None and wr < WIN_RATE_DETERIORATING and enough:
            watch = True
            flags.append(f"win_rate={wr:.1f}<{WIN_RATE_DETERIORATING}")
        if pf is not None and pf < PF_WATCH:
            watch = True
            flags.append(f"profit_factor={pf:.3f}<{PF_WATCH}")

        if deteriorating:
            status = "deteriorating"
            live_influence_allowed = False
            reason = "Deteriorating on matched outcomes — SOE influence veto"
        elif watch:
            status = "watch"
            reason = "Under-performing vs breakeven — reduced SOE influence"
        elif (
            closed >= MIN_CLOSED_FOR_HEALTHY_CLAIM and pf is not None and pf >= PF_WATCH
        ):
            status = "healthy"
            reason = "Adequate sample with non-negative profit factor"
        else:
            status = "unknown"
            reason = "Sample present but inconclusive"

    return {
        "strategy_id": (row or {}).get("strategy_id"),
        "status": status,
        "closed_trades": closed,
        "profit_factor": pf,
        "expectancy": exp,
        "win_rate": wr,
        "live_influence_allowed": live_influence_allowed,
        "flags": flags,
        "reason": reason,
        "disclaimer": "Historical data does not guarantee future profitability.",
    }


def strategy_health_snapshot(stats_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Map StrategyStatsBook.snapshot() → per-strategy health."""
    rows = []
    if isinstance(stats_snapshot, dict):
        raw = stats_snapshot.get("strategies")
        if isinstance(raw, list):
            rows = [r for r in raw if isinstance(r, dict)]
        elif isinstance(raw, dict):
            rows = [v for v in raw.values() if isinstance(v, dict)]
    out: dict[str, Any] = {}
    for row in rows:
        sid = str(row.get("strategy_id") or "")
        if not sid:
            continue
        out[sid] = classify_strategy_health(row)
    return out


def influence_weight_for_strategy(
    *,
    strategy_id: str,
    live_rank_boost: float = 0.0,
    health_row: dict[str, Any] | None = None,
) -> float:
    """Map health + live_rank_boost → SOE influence in [0.0, 1.35].

    0.0 = veto from selection (still visible in analysis).
    1.0 = neutral.
    >1 = modest boost for independently verified healthy strategies.
    """
    _ = strategy_id
    health = health_row or classify_strategy_health(None)
    status = str(health.get("status") or "insufficient_sample")

    if status == "deteriorating" or health.get("live_influence_allowed") is False:
        return 0.0

    weight = 1.0
    if status == "watch":
        weight = 0.55
    elif status == "healthy":
        weight = 1.15
    elif status == "insufficient_sample":
        weight = 1.0
    else:
        weight = 0.85

    # Fold existing live_rank_boost (-20..+25) into a small multiplier.
    boost = max(-20.0, min(25.0, float(live_rank_boost)))
    weight *= 1.0 + (boost / 100.0)
    return max(0.0, min(1.35, round(weight, 4)))
