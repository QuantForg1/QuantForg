"""Strategy scorecard - every strategy plugin backtested on real recent XAUUSD.

Read-only research. It never sends, sizes or modifies an order, and it never
changes LIVE strategy selection; promotion to LIVE stays a manual owner
decision through the existing eligibility registry and risk gates.

Method (identical for every strategy, so results are comparable):

* Real M15 XAUUSD candles from the platform feed (MT5 first).
* Each plugin is evaluated bar by bar on a rolling window (no look-ahead).
* An *entry event* is a BUY/SELL intention that differs from the previous
  bar's intention (state strategies count only when they flip).
* Entry at the next bar's open, paying the measured spread.
* Stop 1.5xATR(14), target 1.5R (the owner's minimum reward:risk floor).
* A bar touching both stop and target counts as a loss (conservative).
* Time exit after 48 bars (12 h). One open trade per strategy.

Past results on a few weeks of data do not guarantee future results; the
output says so and reports sample size so thin samples are not over-read.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

WINDOW = 260
STOP_ATR = 1.5
REWARD_R = 1.5
MAX_HOLD = 48
REFRESH_S = 30 * 60
CANDLE_COUNT = 3000
DEFAULT_SPREAD = 0.30

DISCLAIMER = (
    "Backtest on recent real XAUUSD M15 data with spread included. "
    "Past results do not guarantee future results."
)


@dataclass(slots=True)
class Bar:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _atr(bars: list[Bar], end: int, n: int = 14) -> float:
    lo = max(1, end - n + 1)
    trs = [
        max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        for i in range(lo, end + 1)
    ]
    return sum(trs) / len(trs) if trs else 0.0


def simulate_trade(
    bars: list[Bar], signal_i: int, side: str, spread: float
) -> tuple[float, int] | None:
    """Return (R multiple, exit index) for an entry at bar ``signal_i + 1``."""
    entry_i = signal_i + 1
    if entry_i >= len(bars):
        return None
    atr = _atr(bars, signal_i)
    if atr <= 0:
        return None
    risk = STOP_ATR * atr
    # Candles are bid prices: longs buy at the ask, shorts sell at the bid.
    if side == "BUY":
        entry = bars[entry_i].open + spread
        stop, target = entry - risk, entry + REWARD_R * risk
    else:
        entry = bars[entry_i].open
        stop, target = entry + risk, entry - REWARD_R * risk
    last = min(len(bars) - 1, entry_i + MAX_HOLD)
    for j in range(entry_i, last + 1):
        b = bars[j]
        # exits are hit on the bid (longs) / ask (shorts)
        lo, hi = (b.low, b.high) if side == "BUY" else (b.low + spread, b.high + spread)
        hit_stop = lo <= stop if side == "BUY" else hi >= stop
        hit_target = hi >= target if side == "BUY" else lo <= target
        if hit_stop:
            return -1.0, j
        if hit_target:
            return REWARD_R, j
    if last < entry_i + MAX_HOLD:
        return None  # still open at the end of the data - not counted
    exit_px = bars[last].close - (0 if side == "BUY" else -spread)
    r = (exit_px - entry) / risk if side == "BUY" else (entry - exit_px) / risk
    return r, last


def metrics(rs: list[float]) -> dict[str, Any]:
    n = len(rs)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    pf = (
        (gross_win / gross_loss)
        if gross_loss > 0
        else (math.inf if gross_win > 0 else 0.0)
    )
    return {
        "trades": n,
        "wins": len(wins),
        "win_rate": round(len(wins) / n * 100, 1) if n else 0.0,
        "profit_factor": None if math.isinf(pf) else round(pf, 2),
        "expectancy_r": round(sum(rs) / n, 3) if n else 0.0,
        "net_r": round(sum(rs), 2),
        "max_drawdown_r": round(dd, 2),
    }


def grade(m: dict[str, Any]) -> str:
    n = m["trades"]
    pf = m["profit_factor"]
    pf_v = 99.0 if pf is None and m["wins"] else float(pf or 0.0)
    if n < 8:
        return "insufficient_data"
    if n >= 20 and pf_v >= 1.3 and m["expectancy_r"] > 0.1:
        return "strong"
    if pf_v >= 1.05 and m["expectancy_r"] > 0:
        return "positive"
    if pf_v >= 0.9:
        return "neutral"
    return "weak"


def backtest_plugin(plugin: Any, bars: list[Bar], spread: float) -> dict[str, Any]:
    from app.domain.interfaces.strategy_engine import OhlcBar, StrategySnapshot

    ohlc = [OhlcBar(b.open, b.high, b.low, b.close, b.volume, b.time) for b in bars]
    params = dict(getattr(plugin, "default_params", {}) or {})
    prev = "HOLD"
    open_until = -1
    rs: list[float] = []
    errors = 0
    last_action = "HOLD"
    last_reason = ""
    last_signal_time = ""
    start = min(WINDOW, max(60, len(bars) // 4))
    for i in range(start, len(bars)):
        snap = StrategySnapshot(
            symbol="XAUUSD",
            timeframe="M15",
            bars=tuple(ohlc[max(0, i - WINDOW + 1) : i + 1]),
            params=params,
        )
        try:
            it = plugin.evaluate(snap)
            action = getattr(it.action, "value", str(it.action)).upper()
        except Exception:
            errors += 1
            action = "HOLD"
            it = None
        if i == len(bars) - 1:
            last_action = action
            if it is not None and it.explanations:
                last_reason = it.explanations[0].reason
        if action in {"BUY", "SELL"} and action != prev:
            last_signal_time = bars[i].time
            if i > open_until:
                res = simulate_trade(bars, i, action, spread)
                if res is not None:
                    rs.append(res[0])
                    open_until = res[1]
        prev = action
    m = metrics(rs)
    return {
        "key": plugin.key,
        "name": getattr(plugin, "name", plugin.key),
        "category": getattr(plugin, "category", ""),
        "description": getattr(plugin, "description", ""),
        **m,
        "grade": grade(m),
        "current_signal": last_action,
        "current_reason": last_reason if last_action != "HOLD" else "",
        "last_signal_at": last_signal_time,
        "errors": errors,
    }


def run_scorecard(raw_bars: list[dict[str, Any]], spread: float) -> dict[str, Any]:
    """Pure CPU job (runs in a worker process). ``raw_bars`` oldest first."""
    from app.strategies import default_strategy_plugins

    t0 = time.monotonic()
    bars = [Bar(**b) for b in raw_bars]
    rows = []
    for plugin in default_strategy_plugins():
        if plugin.key == "custom_rules":
            continue  # user-defined rules, not a fixed strategy
        try:
            rows.append(backtest_plugin(plugin, bars, spread))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("scorecard_plugin_failed key=%s err=%s", plugin.key, exc)
    order = {
        "strong": 0,
        "positive": 1,
        "neutral": 2,
        "weak": 3,
        "insufficient_data": 4,
    }
    rows.sort(key=lambda r: (order[r["grade"]], -r["net_r"]))
    for rank, r in enumerate(rows, start=1):
        r["rank"] = rank
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["grade"]] = counts.get(r["grade"], 0) + 1
    return {
        "strategies": rows,
        "summary": {
            "strategies": len(rows),
            "grades": counts,
            "bars": len(bars),
            "from": bars[0].time if bars else None,
            "to": bars[-1].time if bars else None,
            "spread": round(spread, 2),
            "rules": {
                "timeframe": "M15",
                "stop": f"{STOP_ATR}x ATR(14)",
                "target": f"{REWARD_R}R",
                "max_hold_bars": MAX_HOLD,
            },
            "compute_seconds": round(time.monotonic() - t0, 1),
        },
        "consensus": consensus(rows),
        "disclaimer": DISCLAIMER,
    }


def consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Direction implied by strategies with a positive track record right now."""
    buy = sell = 0.0
    voters: list[str] = []
    for r in rows:
        if r["grade"] not in {"strong", "positive"} or r["current_signal"] not in {
            "BUY",
            "SELL",
        }:
            continue
        weight = max(0.1, r["expectancy_r"]) * (2 if r["grade"] == "strong" else 1)
        if r["current_signal"] == "BUY":
            buy += weight
        else:
            sell += weight
        voters.append(r["key"])
    total = buy + sell
    if total == 0:
        return {"direction": "WAIT", "strength": 0, "voters": []}
    lean = (buy - sell) / total
    direction = "BUY" if lean > 0.3 else "SELL" if lean < -0.3 else "WAIT"
    return {
        "direction": direction,
        "strength": round(abs(lean) * 100),
        "voters": voters,
    }


# ------------------------------------------------------------------ service


def _to_float(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def candles_to_bars(
    candles: list[Any], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Normalise feed candles; shift broker-clock times to UTC for session rules."""
    rows = []
    for c in candles:
        o, h, lo, cl = (
            _to_float(getattr(c, k, None)) for k in ("open", "high", "low", "close")
        )
        t = getattr(c, "open_time", None)
        if None in (o, h, lo, cl) or not isinstance(t, datetime):
            continue
        rows.append(
            (
                t if t.tzinfo else t.replace(tzinfo=UTC),
                o,
                h,
                lo,
                cl,
                _to_float(getattr(c, "tick_volume", 0)) or 0.0,
            )
        )
    if not rows:
        return []
    now = now or datetime.now(UTC)
    # Broker servers label bars in their own clock (often UTC+2/+3). If the
    # newest bar is "in the future" by whole hours, remove that offset.
    ahead_h = round((rows[-1][0] - now).total_seconds() / 3600)
    shift = timedelta(hours=ahead_h) if 1 <= ahead_h <= 4 else timedelta(0)
    return [
        {
            "time": (t - shift).isoformat(),
            "open": o,
            "high": h,
            "low": lo,
            "close": cl,
            "volume": v,
        }
        for t, o, h, lo, cl, v in rows
    ]


class StrategyScorecardService:
    def __init__(self) -> None:
        self._result: dict[str, Any] | None = None
        self._at = 0.0
        self._task: asyncio.Task[None] | None = None
        self._pool: ProcessPoolExecutor | None = None
        self._last_error: str | None = None

    def _executor(self) -> ProcessPoolExecutor | None:
        if os.environ.get("QF_SCORECARD_INPROCESS") == "1":
            return None
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=1)
        return self._pool

    async def _refresh(self, feed: Any) -> None:
        try:
            bundle = await asyncio.wait_for(
                feed.candles(symbol="XAUUSD", timeframe="M15", count=CANDLE_COUNT), 30
            )
            bars = candles_to_bars(list(getattr(bundle, "candles", []) or []))
            if len(bars) < 400:
                self._last_error = "not enough market history"
                return
            spread = DEFAULT_SPREAD
            try:
                tb = await asyncio.wait_for(feed.tick(symbol="XAUUSD"), 6)
                tick = getattr(tb, "tick", None)
                bid, ask = _to_float(getattr(tick, "bid", None)), _to_float(
                    getattr(tick, "ask", None)
                )
                if bid and ask and 0 < ask - bid < 2:
                    spread = ask - bid
            except Exception as exc:
                logger.debug("strategy_scorecard_spread_fallback err=%s", exc)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._executor(), run_scorecard, bars, spread
            )
            result["generated_at_utc"] = (
                datetime.now(UTC).replace(microsecond=0).isoformat()
            )
            self._result, self._at, self._last_error = result, time.monotonic(), None
            logger.info(
                "strategy_scorecard_refreshed strategies=%s bars=%s seconds=%s",
                result["summary"]["strategies"],
                len(bars),
                result["summary"]["compute_seconds"],
            )
        except Exception as exc:
            self._last_error = type(exc).__name__
            logger.warning("strategy_scorecard_refresh_failed err=%s", exc)

    def compact(self, top: int = 8) -> dict[str, Any] | None:
        """Cached summary for QuantForg AI context (never triggers a compute)."""
        if self._result is None:
            return None
        rows = self._result.get("strategies", [])
        pick = (
            "key",
            "name",
            "trades",
            "win_rate",
            "profit_factor",
            "net_r",
            "grade",
            "current_signal",
        )
        return {
            "method": DISCLAIMER + " Stop 1.5xATR, target 1.5R, M15.",
            "period": {
                k: self._result["summary"].get(k) for k in ("from", "to", "bars")
            },
            "grades": self._result["summary"].get("grades"),
            "consensus_of_positive_strategies": self._result.get("consensus"),
            "top": [{k: r.get(k) for k in pick} for r in rows[:top]],
            "signalling_now": [
                {k: r.get(k) for k in pick}
                for r in rows
                if r.get("current_signal") in {"BUY", "SELL"}
            ][:12],
        }

    async def get(self, feed: Any) -> dict[str, Any]:
        stale = self._result is None or time.monotonic() - self._at > REFRESH_S
        if stale and (self._task is None or self._task.done()):
            self._task = asyncio.create_task(self._refresh(feed))
        if self._result is None:
            return {"status": "warming", "strategies": [], "disclaimer": DISCLAIMER}
        return {"status": "ready", **self._result}


_SERVICE: StrategyScorecardService | None = None


def get_strategy_scorecard_service() -> StrategyScorecardService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = StrategyScorecardService()
    return _SERVICE
