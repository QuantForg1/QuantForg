# ruff: noqa: E501, E741, PTH123, C408
"""Shadow forward test for candidate strategies (no orders, read-only MT5).

Every run evaluates the candidate plugins on the latest closed H1 bars,
records any NEW signal, and settles earlier signals against later bars with the
same fixed model used in the backtest (SL 1.5xATR, TP 2xATR, 48-bar time exit,
spread + 0.05 slippage). Results accumulate in ``data/shadow_candidates.csv``.
It never calls order_send and never touches the live robot.

    poetry run python scripts/shadow_forward_test.py            # live bars from MT5
    poetry run python scripts/shadow_forward_test.py --csv data/history/XAUUSD_H1.csv --replay-last 400
    poetry run python scripts/shadow_forward_test.py --summary
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    OhlcBar,
    StrategySnapshot,
)
from app.strategies import default_strategy_plugins

CANDIDATES = (
    "choppiness_breakout",
    "bollinger_band_walk",
    "session_breakout",
    "dema_cross",
    "awesome_oscillator",
    "ppo_signal_cross",
    "market_structure_bos",
    "elder_impulse",
    "turtle_55",
    "atr_channel_breakout",
)
WIN = 150
FIELDS = [
    "strategy",
    "signal_time",
    "side",
    "entry",
    "sl",
    "tp",
    "status",
    "exit_time",
    "pnl",
    "risk",
]
OUT = Path("data/shadow_candidates.csv")
SLIP = 0.05
HORIZON = 48


def _atr(bars: list[tuple], i: int, n: int = 14) -> float:
    s = 0.0
    for k in range(i - n + 1, i + 1):
        _, _, h, l, _, _ = bars[k]
        pc = bars[k - 1][4]
        s += max(h - l, abs(h - pc), abs(l - pc))
    return s / n


def _read_csv(path: str) -> list[tuple]:
    rows = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            rows.append(
                (
                    r["time"],
                    float(r["open"]),
                    float(r["high"]),
                    float(r["low"]),
                    float(r["close"]),
                    float(r["spread"]) * 0.001,
                )
            )
    return rows


def _read_mt5(symbol: str, count: int = 400) -> list[tuple]:
    import MetaTrader5 as mt5  # type: ignore[import-not-found]

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        point = float(info.point) if info else 0.001
        rates = mt5.copy_rates_from_pos(
            symbol, mt5.TIMEFRAME_H1, 1, count
        )  # closed bars only
        if rates is None:
            raise SystemExit(f"no rates: {mt5.last_error()}")
        return [
            (
                datetime.fromtimestamp(int(r["time"]), UTC).isoformat(),
                float(r["open"]),
                float(r["high"]),
                float(r["low"]),
                float(r["close"]),
                float(r["spread"]) * point,
            )
            for r in rates
        ]
    finally:
        mt5.shutdown()


def _load() -> list[dict]:
    if not OUT.exists():
        return []
    with OUT.open() as fh:
        return list(csv.DictReader(fh))


def _save(rows: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _settle(rows: list[dict], bars: list[tuple]) -> None:
    index = {b[0]: i for i, b in enumerate(bars)}
    for r in rows:
        if r["status"] != "open" or r["signal_time"] not in index:
            continue
        d = 1 if r["side"] == "BUY" else -1
        entry, sl, tp = float(r["entry"]), float(r["sl"]), float(r["tp"])
        start = index[r["signal_time"]] + 1
        for j in range(start, min(len(bars), start + HORIZON + 1)):
            _, _, h, l, c, sp = bars[j]
            hit = None
            if d == 1:
                hit = sl if l <= sl else (tp if h >= tp else None)
            else:
                hit = sl if h + sp >= sl else (tp if l + sp <= tp else None)
            if hit is not None:
                r.update(
                    status="closed",
                    exit_time=bars[j][0],
                    pnl=f"{(hit - entry) * d:.3f}",
                )
                break
        else:
            if len(bars) - 1 >= start + HORIZON:
                c = bars[start + HORIZON][4]
                r.update(
                    status="closed",
                    exit_time=bars[start + HORIZON][0],
                    pnl=f"{(c - entry) * d:.3f}",
                )


def _evaluate(bars: list[tuple], upto: int, rows: list[dict]) -> None:
    plugins = {p.key: p for p in default_strategy_plugins()}
    seen = {(r["strategy"], r["signal_time"]) for r in rows}
    ohlc = [
        OhlcBar(open=b[1], high=b[2], low=b[3], close=b[4], time=b[0]) for b in bars
    ]
    t = bars[upto][0]
    for key in CANDIDATES:
        p = plugins.get(key)
        if p is None or (key, t) in seen:
            continue
        snap = StrategySnapshot(
            symbol="XAUUSD",
            timeframe="H1",
            bars=tuple(ohlc[upto - WIN + 1 : upto + 1]),
            params=dict(p.default_params),
            as_of=t,
        )
        act = p.evaluate(snap).action
        if act not in (EngineSignalAction.BUY, EngineSignalAction.SELL):
            continue
        if any(r["strategy"] == key and r["status"] == "open" for r in rows):
            continue  # one open shadow trade per strategy
        a = _atr(bars, upto)
        risk = 1.5 * a
        nxt = bars[upto][
            4
        ]  # entry proxy: last closed price (next open is unknown live)
        sp = bars[upto][5]
        if act == EngineSignalAction.BUY:
            entry = nxt + sp + SLIP
            sl, tp, side = entry - risk, entry + 2 * risk, "BUY"
        else:
            entry = nxt - SLIP
            sl, tp, side = entry + risk, entry - 2 * risk, "SELL"
        rows.append(
            dict(
                strategy=key,
                signal_time=t,
                side=side,
                entry=f"{entry:.3f}",
                sl=f"{sl:.3f}",
                tp=f"{tp:.3f}",
                status="open",
                exit_time="",
                pnl="",
                risk=f"{risk:.3f}",
            )
        )


def summary(rows: list[dict]) -> None:
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["strategy"], []).append(r)
    print(
        f"{'strategy':24} {'closed':>6} {'win%':>6} {'PF':>6} {'net$/oz':>9} {'open':>5}"
    )
    for k in CANDIDATES:
        rs = by.get(k, [])
        cl = [float(r["pnl"]) for r in rs if r["status"] == "closed"]
        w = sum(p for p in cl if p > 0)
        l = -sum(p for p in cl if p <= 0)
        pf = (w / l) if l else (99.0 if w else 0.0)
        wr = 100 * sum(1 for p in cl if p > 0) / len(cl) if cl else 0.0
        print(
            f"{k:24} {len(cl):6d} {wr:6.1f} {pf:6.2f} {sum(cl):9.1f} {sum(1 for r in rs if r['status'] == 'open'):5d}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--csv", default="")
    ap.add_argument("--replay-last", type=int, default=0)
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    rows = _load()
    if args.summary:
        summary(rows)
        return 0
    bars = _read_csv(args.csv) if args.csv else _read_mt5(args.symbol)
    if args.replay_last:
        start = max(WIN, len(bars) - args.replay_last)
        for i in range(start, len(bars)):
            _settle(rows, bars[: i + 1])
            _evaluate(bars, i, rows)
    else:
        _settle(rows, bars)
        _evaluate(bars, len(bars) - 1, rows)
    _save(rows)
    summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
