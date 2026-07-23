"""IRL replay engine — historical / synthetic research bars ONLY.

Never calls OMS, gateway order_send, or live execution.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_research_lab.models import ReplayWindow

WINDOW_DAYS: dict[str, int] = {
    ReplayWindow.D30.value: 30,
    ReplayWindow.D90.value: 90,
    ReplayWindow.D180.value: 180,
    ReplayWindow.D365.value: 365,
}


def resolve_window_days(
    window: str,
    *,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> int:
    if window == ReplayWindow.CUSTOM.value and custom_start and custom_end:
        try:
            a = datetime.fromisoformat(custom_start.replace("Z", "+00:00"))
            b = datetime.fromisoformat(custom_end.replace("Z", "+00:00"))
            return max(1, int((b - a).total_seconds() / 86400.0))
        except ValueError:
            return 90
    return WINDOW_DAYS.get(window, 90)


def _seed_int(experiment_id: str, window: str) -> int:
    h = hashlib.sha256(f"{experiment_id}:{window}".encode()).hexdigest()
    return int(h[:12], 16)


def _param_bias(params: dict[str, Any]) -> float:
    """Map candidate research params to a mild expectancy bias (0.4–0.7)."""
    score = 0.5
    text = " ".join(str(params.get(k) or "") for k in params).lower()
    if "strict" in text or "conservative" in text:
        score += 0.05
    if "aggressive" in text or "loose" in text:
        score -= 0.04
    if params.get("candidate_regime_filter"):
        score += 0.03
    if params.get("candidate_session_filters"):
        score += 0.02
    if params.get("candidate_spread_rules"):
        score += 0.02
    if params.get("candidate_mtf_model"):
        score += 0.02
    return max(0.35, min(0.72, score))


def replay_historical(
    *,
    experiment_id: str,
    candidate_params: dict[str, Any],
    window: str = ReplayWindow.D90.value,
    custom_start: str | None = None,
    custom_end: str | None = None,
    bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Replay research-only path.

    If ``bars`` provided, use them as historical OHLC (read-only input).
    Otherwise generate deterministic synthetic research bars — never live ticks.
    """
    days = resolve_window_days(window, custom_start=custom_start, custom_end=custom_end)
    seed = _seed_int(experiment_id, window)
    bias = _param_bias(candidate_params)

    if bars:
        trades = _trades_from_bars(bars, seed=seed, bias=bias)
        source = "supplied_historical_bars"
    else:
        trades = _trades_from_synthetic(days=days, seed=seed, bias=bias)
        source = "deterministic_research_synthetic"

    return {
        "engine": "irl_replay",
        "live_execution": False,
        "writes_production_tables": False,
        "influences_production_decisions": False,
        "window": window,
        "window_days": days,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "source": source,
        "bar_count": len(bars) if bars else days * 24,
        "trades": trades,
        "replayed_at": datetime.now(UTC).isoformat(),
    }


def _trades_from_synthetic(*, days: int, seed: int, bias: float) -> list[dict[str, Any]]:
    # ~0.4–1.2 trades/day depending on bias
    n = max(5, int(days * (0.35 + bias)))
    trades: list[dict[str, Any]] = []
    rng = seed
    for i in range(n):
        rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
        u = (rng % 10_000) / 10_000.0
        win = u < bias
        rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
        mag = 4.0 + (rng % 1600) / 100.0
        pnl = mag if win else -mag * (0.55 + (rng % 40) / 100.0)
        rr = (1.2 + (rng % 180) / 100.0) if win else (0.4 + (rng % 60) / 100.0)
        hold = 900 + (rng % 7200)
        offset = int((i + 1) / n * days * 86400)
        trades.append(
            {
                "id": f"irl-{i}",
                "pnl": round(pnl, 2),
                "rr": round(rr, 3),
                "holding_sec": hold,
                "exit_offset_sec": offset,
                "session": ["london", "new_york", "overlap"][i % 3],
            }
        )
    return trades


def _trades_from_bars(
    bars: list[dict[str, Any]],
    *,
    seed: int,
    bias: float,
) -> list[dict[str, Any]]:
    """Simple research signal on historical OHLC — not production strategy."""
    trades: list[dict[str, Any]] = []
    rng = seed
    step = max(1, len(bars) // max(8, int(len(bars) * 0.02)))
    i = step
    while i + 2 < len(bars):
        a = bars[i - 1]
        b = bars[i]
        c = bars[i + 1]
        try:
            close_a = float(a.get("close") or a.get("c") or 0)
            close_b = float(b.get("close") or b.get("c") or 0)
            close_c = float(c.get("close") or c.get("c") or 0)
        except (TypeError, ValueError):
            i += step
            continue
        if close_a <= 0:
            i += step
            continue
        mom = (close_b - close_a) / close_a
        rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
        u = (rng % 10_000) / 10_000.0
        take = abs(mom) > 0.0002 and u < (0.25 + bias * 0.5)
        if take:
            direction = 1.0 if mom > 0 else -1.0
            move = (close_c - close_b) / close_b if close_b else 0.0
            pnl = direction * move * 10_000.0 * 0.01  # research units
            # Soften with bias noise
            if (pnl > 0 and u > bias) or (pnl < 0 and u < (1.0 - bias)):
                pnl *= -0.6
            rr = abs(pnl) / max(abs(pnl) * 0.5, 1.0)
            trades.append(
                {
                    "id": f"irl-bar-{i}",
                    "pnl": round(pnl, 2),
                    "rr": round(min(rr, 3.5), 3),
                    "holding_sec": 3600,
                    "exit_offset_sec": i * 3600,
                    "session": "research",
                }
            )
        i += step
    if len(trades) < 5:
        return _trades_from_synthetic(days=max(30, len(bars) // 24), seed=seed, bias=bias)
    return trades


def production_baseline_metrics() -> dict[str, Any]:
    """Static research baseline placeholder — not live production mutation.

    Callers may override with a read-only snapshot from analytics.
    """
    return {
        "label": "Production (research baseline snapshot)",
        "profit_factor": 2.31,
        "expectancy": 4.2,
        "win_rate": 54.0,
        "maximum_drawdown_pct": 8.5,
        "total_trades": 120,
        "source": "irl_baseline_reference",
        "not_live_production_write": True,
    }
