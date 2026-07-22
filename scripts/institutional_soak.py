#!/usr/bin/env python3
"""Institutional soak harness — accelerated + optional wall-clock sample.

Does not invent broker activity. Writes a stability report JSON under
``docs/production/reports/`` (or ``--out``).

Examples::

    python scripts/institutional_soak.py --profile stress
    python scripts/institutional_soak.py --profile 24h --wall-seconds 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-untyped]

        return float(psutil.Process().memory_info().rss) / (1024 * 1024)
    except Exception:  # noqa: S110 — optional dependency
        pass
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        val = float(usage.ru_maxrss)
        # Linux: KB; macOS: bytes
        return val / (1024 * 1024) if val > 10_000_000 else val / 1024.0
    except Exception:
        return 0.0


def run_accelerated(profile: str) -> dict:
    from app.domain.scalping_ai_v2 import ScalpingAiV2

    return ScalpingAiV2().run_soak(profile=profile)


def run_wall_sample(seconds: float) -> dict:
    """Short wall-clock sample of API/gateway probes (not a fake 7-day claim)."""
    from app.application.services.institutional_live_probes import LiveProbeCollector
    from core.config.settings import get_settings

    settings = get_settings()
    collector = LiveProbeCollector(settings=settings)
    samples: list[dict] = []
    t_end = time.monotonic() + max(1.0, seconds)
    reconnects = 0
    last_gw = None
    while time.monotonic() < t_end:
        t0 = time.perf_counter()
        probes = collector.collect()
        lat = (time.perf_counter() - t0) * 1000.0
        gw = bool(probes.gateway_available)
        if last_gw is True and gw is False:
            reconnects += 1
        last_gw = gw
        samples.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "gateway": gw,
                "mt5": bool(probes.mt5_connected),
                "latency_ms": round(lat, 2),
                "rss_mb": round(_rss_mb(), 2),
            }
        )
        time.sleep(min(2.0, max(0.2, seconds / 10)))
    return {
        "wall_seconds_requested": seconds,
        "samples": samples,
        "reconnect_events": reconnects,
        "latency_ms_max": max((s["latency_ms"] for s in samples), default=0),
        "latency_ms_avg": (
            round(sum(s["latency_ms"] for s in samples) / len(samples), 2)
            if samples
            else 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantForg institutional soak")
    parser.add_argument(
        "--profile",
        default="stress",
        choices=["stress", "24h", "48h", "72h"],
        help="Accelerated soak profile (CI-safe)",
    )
    parser.add_argument(
        "--wall-seconds",
        type=float,
        default=0.0,
        help="Optional wall-clock probe sample (seconds)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Report output path",
    )
    args = parser.parse_args()

    tracemalloc.start()
    t0 = time.perf_counter()
    accelerated = run_accelerated(args.profile)
    wall = run_wall_sample(args.wall_seconds) if args.wall_seconds > 0 else None
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": args.profile,
        "elapsed_seconds": round(time.perf_counter() - t0, 3),
        "accelerated_soak": accelerated,
        "wall_clock_sample": wall,
        "process": {
            "rss_mb": round(_rss_mb(), 2),
            "tracemalloc_current_mb": round(current / (1024 * 1024), 3),
            "tracemalloc_peak_mb": round(peak / (1024 * 1024), 3),
        },
        "targets": {
            "24h": "Run: --profile 24h --wall-seconds 86400 on a dedicated host",
            "72h": "Run: --profile 72h --wall-seconds 259200 on a dedicated host",
            "7d": "Run: --profile 72h --wall-seconds 604800 on a dedicated host",
        },
        "notes": [
            "Accelerated profiles validate bounded resources "
            "without sleeping wall-clock days.",
            "Wall-clock samples measure real gateway/MT5 probe "
            "stability when configured.",
            "Do not claim multi-day soak completion unless "
            "wall_seconds covers that window.",
        ],
    }

    out = args.out
    if out is None:
        out_dir = ROOT / "docs" / "production" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = out_dir / f"soak_{args.profile}_{stamp}.json"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(out), "profile": args.profile}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
