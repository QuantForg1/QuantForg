"""Continuous LIVE execution witness — observe only, never mutate strategy/Risk/Safety.

Polls production /ite/ops/auto-trading and appends unique cycle fingerprints to
docs/production/reports/live_execution_witness.jsonl until MT5 ticket or Ctrl-C.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "production" / "reports" / "live_execution_witness.jsonl"
SUMMARY = ROOT / "docs" / "production" / "reports" / "live_execution_witness_latest.json"
BASE = (
    os.environ.get("QUANTFORG_API_URL") or "https://quantforg-production.up.railway.app"
).rstrip("/")
INTERVAL_SEC = int(os.environ.get("WITNESS_INTERVAL_SEC") or "45")


def _req(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def login() -> str:
    token = (os.environ.get("QUANTFORG_OWNER_TOKEN") or "").strip()
    if token:
        return token
    email = (
        os.environ.get("QUANTFORG_OWNER_EMAIL") or os.environ.get("E2E_EMAIL") or ""
    ).strip()
    password = (
        os.environ.get("QUANTFORG_OWNER_PASSWORD")
        or os.environ.get("E2E_PASSWORD")
        or ""
    ).strip()
    out = _req("POST", "/auth/login", body={"email": email, "password": password})
    return str(out["access_token"])


def fingerprint(last: dict) -> str:
    return "|".join(
        [
            str(last.get("trace_id") or ""),
            str(last.get("signal_id") or ""),
            str(last.get("cycle_outcome") or ""),
            str(last.get("abort_reason") or ""),
            str(last.get("decision_action") or ""),
            str(last.get("mt5_ticket") or ""),
            str(last.get("detail") or "")[:160],
        ]
    )


def extract(at: dict) -> dict:
    last = (at.get("orchestrator") or {}).get("last_cycle") or {}
    diag = last.get("market_context_diagnostics") or {}
    reasons = last.get("decision_reasons") or []
    quality = None
    confluence = None
    for r in reasons:
        s = str(r)
        if "Trade quality" in s and quality is None:
            quality = s
        if "Confluence" in s and confluence is None:
            confluence = s
    detail = str(last.get("detail") or "")
    return {
        "observed_at": datetime.now(UTC).isoformat(),
        "ops_mode": at.get("ops_mode"),
        "gate": (at.get("execution_state") or {}).get("gate_status"),
        "run_state": (at.get("policy") or {}).get("run_state"),
        "trace_id": last.get("trace_id"),
        "signal_id": last.get("signal_id"),
        "snapshot_present": last.get("snapshot_present"),
        "cycle_outcome": last.get("cycle_outcome"),
        "abort_reason": last.get("abort_reason"),
        "decision_action": last.get("decision_action"),
        "decision_reasons": reasons,
        "safety_failed_reasons": last.get("safety_failed_reasons") or [],
        "forwarded_to_oms": last.get("forwarded_to_oms"),
        "oms_message": last.get("oms_message"),
        "broker_retcode": last.get("broker_retcode"),
        "mt5_ticket": last.get("mt5_ticket"),
        "latency_ms": last.get("latency_ms"),
        "session": diag.get("trading_session"),
        "session_allowed": diag.get("session_allowed"),
        "quality_note": quality,
        "confluence_note": confluence,
        "detail": detail[:500],
        "success": bool(last.get("mt5_ticket"))
        or (
            bool(last.get("forwarded_to_oms"))
            and str(last.get("cycle_outcome") or "") == "forwarded"
        ),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    token = login()
    seen: set[str] = set()
    print(
        json.dumps(
            {
                "event": "witness_started",
                "interval_sec": INTERVAL_SEC,
                "out": str(OUT),
            }
        ),
        flush=True,
    )
    while True:
        try:
            at = _req("GET", "/ite/ops/auto-trading", token)
            row = extract(at)
            last = (at.get("orchestrator") or {}).get("last_cycle") or {}
            fp = fingerprint(last if isinstance(last, dict) else {})
            SUMMARY.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
            if fp and fp not in seen:
                seen.add(fp)
                with OUT.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                event = "EXECUTION_SUCCESS" if row["success"] else "CANDIDATE_REJECTED"
                print(
                    json.dumps({"event": event, **row}, default=str)[:2000],
                    flush=True,
                )
                if row["success"]:
                    print("AGENT_LOOP_WAKE_live_exec {\"prompt\":\"First MT5 execution captured — summarize ticket and stop witness if complete\"}", flush=True)
                    return 0
            else:
                print(
                    json.dumps(
                        {
                            "event": "heartbeat",
                            "observed_at": row["observed_at"],
                            "ops_mode": row["ops_mode"],
                            "cycle_outcome": row["cycle_outcome"],
                            "abort_reason": row["abort_reason"],
                            "session": row["session"],
                            "mt5_ticket": row["mt5_ticket"],
                        },
                        default=str,
                    ),
                    flush=True,
                )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "event": "witness_error",
                        "error": str(exc),
                        "at": datetime.now(UTC).isoformat(),
                    }
                ),
                flush=True,
            )
            # refresh token on auth failures
            try:
                token = login()
            except Exception:
                pass
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
