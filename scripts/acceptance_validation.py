#!/usr/bin/env python3
"""Run v1.0.1 acceptance validation suite and write evidence JSON.

Does not invent wall-clock soak results. Marks multi-day soak as PENDING.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> dict:
    proc = subprocess.run(  # noqa: S603 — trusted local pytest/soak commands only
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
    }


def main() -> int:
    evidence: dict[str, object] = {
        "schema_version": "1.0.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "acceptance_validation",
        "wall_clock_soak": {
            "24h": "PENDING OPERATIONAL EVIDENCE",
            "72h": "PENDING OPERATIONAL EVIDENCE",
            "7d": "PENDING OPERATIONAL EVIDENCE",
            "note": (
                "Do not fabricate. Run "
                "scripts/institutional_soak.py --wall-seconds on a host."
            ),
        },
        "gates": {},
    }

    evidence["gates"]["acceptance_unit"] = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/test_acceptance_validation_v101.py",
            "tests/unit/test_institutional_trading_phase_g.py",
            "tests/unit/test_institutional_trading_phase_h.py",
            "tests/unit/test_auto_trading_status_sync.py",
            "tests/unit/test_live_account_risk_tracker.py",
            "-q",
            "--tb=line",
            "--no-cov",
        ]
    )
    evidence["gates"]["soak_stress"] = _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "institutional_soak.py"),
            "--profile",
            "stress",
        ]
    )

    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"acceptance_evidence_{stamp}.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "evidence": str(out)}))
    gates = evidence["gates"]
    assert isinstance(gates, dict)
    unit_ok = bool((gates.get("acceptance_unit") or {}).get("ok"))
    soak_ok = bool((gates.get("soak_stress") or {}).get("ok"))
    return 0 if unit_ok and soak_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
