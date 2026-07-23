#!/usr/bin/env python3
"""Offline Institutional Execution Validation.

Finds real historical XAUUSD setups that satisfy all production gates, then
replays them through the complete pipeline with a simulated OMS/gateway/broker
fill. Prefers live MT5 gateway candles when reachable; falls back to
deterministic synthetic bars only when gateway history is unavailable.

Never calls live order_send. Never weakens strategy, MTF, quality, confluence,
risk, or safety.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_gateway_bars(*, days: int) -> tuple[dict[Any, list[Any]] | None, str]:
    """Fetch multi-TF XAUUSD candles from the local MT5 gateway (read-only)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass

    import os

    from app.application.services.ite_cycle_market_context import _rate_to_candle
    from app.domain.market_data.timeframe import Timeframe
    from app.domain.trading.gold_only import GOLD_SYMBOL
    from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

    base = (
        os.getenv("MT5_GATEWAY_URL")
        or os.getenv("MT5_GATEWAY_BASE_URL")
        or "http://127.0.0.1:8765"
    )
    token = (os.getenv("MT5_GATEWAY_TOKEN") or "").strip()
    if not token:
        return None, "no_MT5_GATEWAY_TOKEN"

    client = GatewayMT5Client(base_url=base, token=token)
    try:
        if not client.adopt_existing_session():
            return None, "gateway_session_not_attached"
    except Exception as exc:  # noqa: BLE001 - offline fallback path
        return None, f"gateway_adopt_failed:{exc}"

    # Gateway caps ~5000 candles/request. Size counts to cover ``days`` where possible.
    counts = {
        Timeframe.M5: min(5000, max(500, days * 24 * 12)),
        Timeframe.M15: min(5000, max(400, days * 24 * 4)),
        Timeframe.H1: min(5000, max(200, days * 24)),
        Timeframe.H4: min(2000, max(100, days * 6)),
    }
    bars: dict[Any, list[Any]] = {}
    try:
        for tf, count in counts.items():
            rates = client.copy_rates_from_pos(GOLD_SYMBOL, tf, 0, count)
            if len(rates) < 60:
                return None, f"insufficient_{tf.value}_bars:{len(rates)}"
            candles = [_rate_to_candle(r) for r in rates]
            candles.sort(key=lambda c: c.close_time)
            # Keep trailing window ≈ days (when enough history exists).
            cutoff = datetime.now(UTC) - timedelta(days=days)
            windowed = [c for c in candles if c.close_time >= cutoff]
            bars[tf] = windowed if len(windowed) >= 60 else candles
    except Exception as exc:  # noqa: BLE001 - offline fallback path
        return None, f"gateway_fetch_failed:{exc}"

    m15 = bars.get(Timeframe.M15) or []
    span_days = 0.0
    if len(m15) >= 2:
        span_days = (m15[-1].close_time - m15[0].close_time).total_seconds() / 86400.0
    return bars, f"mt5_gateway:{base}:m15_bars={len(m15)}:span_days={span_days:.1f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Institutional execution validation (offline)"
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--max-evaluations", type=int, default=400)
    parser.add_argument("--max-valid-setups", type=int, default=3)
    parser.add_argument("--equity", type=str, default="10000")
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Skip MT5 gateway and use deterministic synthetic bars only",
    )
    args = parser.parse_args()

    from app.application.services.institutional_execution_validation import (
        report_to_markdown,
        run_institutional_execution_validation,
    )

    bars_by_tf = None
    bar_source = "synthetic_deterministic"
    if not args.synthetic_only:
        bars_by_tf, bar_source = _load_gateway_bars(days=args.days)
        if bars_by_tf is None:
            print(
                f"Gateway history unavailable ({bar_source}); "
                "falling back to synthetic deterministic bars.",
                file=sys.stderr,
            )
            bar_source = f"synthetic_deterministic(fallback_from:{bar_source})"

    report = asyncio.run(
        run_institutional_execution_validation(
            days=args.days,
            max_evaluations=args.max_evaluations,
            max_valid_setups=args.max_valid_setups,
            equity=Decimal(args.equity),
            bars_by_tf=bars_by_tf,
            bar_source=bar_source,
        )
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "docs" / "production" / "reports"
    out.mkdir(parents=True, exist_ok=True)

    json_body = json.dumps(report, indent=2) + "\n"
    (out / f"institutional_execution_validation_{stamp}.json").write_text(
        json_body, encoding="utf-8"
    )
    (out / "institutional_execution_validation_latest.json").write_text(
        json_body, encoding="utf-8"
    )

    md = report_to_markdown(report)
    (out / f"institutional_execution_validation_{stamp}.md").write_text(
        md, encoding="utf-8"
    )
    (out / "INSTITUTIONAL_EXECUTION_VALIDATION.md").write_text(md, encoding="utf-8")

    sys.stdout.buffer.write(md.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    print(f"Wrote JSON/MD under {out}", file=sys.stderr)
    return 0 if report.get("valid_production_setup_exists") else 2


if __name__ == "__main__":
    raise SystemExit(main())
