"""Export XAUUSD history from a local MT5 terminal to CSV (read-only).

Used to backtest the strategy library offline. Never places orders, never
reads credentials, writes only CSV files under --out.

    poetry run python scripts/export_mt5_history.py --symbol XAUUSD --years 2

Run it against the terminal you already use for market data; it only calls
copy_rates_range / symbol_info (read-only MetaTrader5 API).
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

_TFS = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "H1": "TIMEFRAME_H1",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--years", type=float, default=2.0)
    ap.add_argument("--timeframes", default="M15,H1")
    ap.add_argument("--out", default="data/history")
    ap.add_argument("--path", default="", help="optional terminal64.exe path")
    args = ap.parse_args()

    import MetaTrader5 as mt5  # type: ignore[import-not-found]

    ok = mt5.initialize(path=args.path) if args.path else mt5.initialize()
    if not ok:
        print("initialize failed:", mt5.last_error())
        return 1
    try:
        mt5.symbol_select(args.symbol, True)
        info = mt5.symbol_info(args.symbol)
        if info is None:
            print("symbol not found:", args.symbol)
            return 1
        end = datetime.now(UTC)
        start = end - timedelta(days=int(365 * args.years))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name in [
            t.strip().upper() for t in args.timeframes.split(",") if t.strip()
        ]:
            tf = getattr(mt5, _TFS[name])
            rows = mt5.copy_rates_range(args.symbol, tf, start, end)
            if rows is None or len(rows) == 0:
                print(name, "no data:", mt5.last_error())
                continue
            path = out / f"{args.symbol}_{name}.csv"
            with path.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(
                    ["time", "open", "high", "low", "close", "tick_volume", "spread"]
                )
                for r in rows:
                    w.writerow(
                        [
                            datetime.fromtimestamp(int(r["time"]), UTC).isoformat(),
                            r["open"],
                            r["high"],
                            r["low"],
                            r["close"],
                            int(r["tick_volume"]),
                            int(r["spread"]),
                        ]
                    )
            print(name, len(rows), "bars ->", path)
        print(
            "point",
            info.point,
            "digits",
            info.digits,
            "contract",
            info.trade_contract_size,
        )
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
