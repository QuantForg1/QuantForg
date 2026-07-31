#!/usr/bin/env python3
"""Stream Railway logs and append unique cycle_evidence rejections.

Observation only. Shares store with collect_decision_rejection_cycles.py.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

STORE = Path(
    os.environ.get("COLLECT_STORE", "/tmp/ai-decision-collector/cycles_by_trace.json")
)
TARGET = int(os.environ.get("COLLECT_TARGET", "1000"))
SERVICE = os.environ.get("RAILWAY_SERVICE", "QuantForg")


def load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text())
    return {}


def save(cycles: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(cycles))


def main() -> None:
    cycles = load()
    print(f"log_miner_start n={len(cycles)}", flush=True)
    proc = subprocess.Popen(
        ["railway", "logs", "--service", SERVICE],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if "cycle_evidence" not in line or "Rejected because:" not in line:
                continue
            tm = re.search(r"trace_id=(\S+)", line)
            pm = re.search(r"Rejected because: (\S+)", line)
            if not tm or not pm:
                continue
            trace = tm.group(1)
            if trace in cycles:
                continue
            reasons_m = re.search(r"reasons=(\[.*\])\s+session=", line)
            sizing_m = re.search(r"sizing=(\{.*\})\s+stage=", line)
            try:
                reasons = eval(reasons_m.group(1)) if reasons_m else []  # noqa: S307
            except Exception:
                reasons = []
            try:
                sizing = eval(sizing_m.group(1)) if sizing_m else {}  # noqa: S307
            except Exception:
                sizing = {}
            q = mtf = None
            for r in reasons:
                mq = re.search(r"Trade quality\s+(\d+)", str(r))
                if mq:
                    q = int(mq.group(1))
                mm = re.search(r"score=(\d+)\s+not aligned", str(r))
                if mm:
                    mtf = int(mm.group(1))
            codes = [c for c in reasons if re.fullmatch(r"[a-z0-9_]+", str(c))]
            sm = re.search(r"session=(\S+)", line)
            cycles[trace] = {
                "recorded_at": line[:32],
                "trace_id": trace,
                "source": "railway_log_stream",
                "decision_action": "NO_TRADE",
                "rejected": True,
                "market_session": sm.group(1) if sm else None,
                "quality": {
                    "score": q,
                    "required": 80,
                    "passed": False if q is not None else None,
                },
                "confluence": {
                    "total": None,
                    "required": 80,
                    "engine_factors": {},
                    "components": {},
                },
                "trend": {
                    "score": mtf,
                    "aligned": False if mtf is not None else None,
                },
                "rejection": {
                    "primary": pm.group(1),
                    "all_codes": codes,
                    "decision_reasons": [str(r) for r in reasons],
                },
                "sizing": sizing if isinstance(sizing, dict) else {},
                "atr": (sizing or {}).get("atr") if isinstance(sizing, dict) else None,
            }
            save(cycles)
            if len(cycles) % 5 == 0:
                print(
                    json.dumps(
                        {
                            "n": len(cycles),
                            "q": q,
                            "mtf": mtf,
                            "primary": pm.group(1),
                        }
                    ),
                    flush=True,
                )
            if len(cycles) >= TARGET:
                print(f"DONE n={len(cycles)}", flush=True)
                break
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
