"""Continuous LIVE execution witness — observe only, never mutate strategy/Risk/Safety.

Separates witness authentication health from trading execution health.
HTTP 401 → Witness Authentication Failed (never implies execution failure).
Polls production /ite/ops/auto-trading until MT5 ticket or Ctrl-C.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.services import witness_observability as wh  # noqa: E402
from app.application.services.witness_observability import (  # noqa: E402
    AUTH_LABEL,
    HEALTH_PATH,
)

OUT = ROOT / "docs" / "production" / "reports" / "live_execution_witness.jsonl"
SUMMARY = ROOT / "docs" / "production" / "reports" / "live_execution_witness_latest.json"
BASE = (
    os.environ.get("QUANTFORG_API_URL") or "https://quantforg-production.up.railway.app"
).rstrip("/")
INTERVAL_SEC = int(os.environ.get("WITNESS_INTERVAL_SEC") or "45")
AUTO_TRADING_PATH = "/ite/ops/auto-trading"
LOGIN_PATH = "/auth/login"


class WitnessHttpError(Exception):
    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.http_status = http_status


def _req(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = BASE + path
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_txt = ""
        try:
            body_txt = exc.read().decode(errors="replace")[:200]
        except Exception:
            pass
        raise WitnessHttpError(
            f"HTTP Error {exc.code}: {exc.reason}"
            + (f" ({body_txt})" if body_txt else ""),
            endpoint=path,
            http_status=int(exc.code),
        ) from exc
    except urllib.error.URLError as exc:
        raise WitnessHttpError(
            f"<urlopen error {exc.reason}>",
            endpoint=path,
            http_status=None,
        ) from exc


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
    out = _req("POST", LOGIN_PATH, body={"email": email, "password": password})
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


def _trading_health_from_row(row: dict | None) -> dict:
    if not row:
        return {
            "note": "No successful witness poll yet",
            "last_cycle_outcome": None,
            "last_session": None,
            "mt5_ticket": None,
        }
    return {
        "note": "From last successful witness poll of trading API",
        "last_cycle_outcome": row.get("cycle_outcome"),
        "last_session": row.get("session"),
        "mt5_ticket": row.get("mt5_ticket"),
        "observed_at": row.get("observed_at"),
        "ops_mode": row.get("ops_mode"),
        "abort_reason": row.get("abort_reason"),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    token = login()
    seen: set[str] = set()
    consecutive_ok = 0
    last_ok_at: datetime | None = None
    last_auth_error: dict | None = None
    open_incident: dict | None = None
    auth_retry_count = 0
    last_recovery_time: str | None = None
    last_trading_row: dict | None = None

    print(
        json.dumps(
            {
                "event": "witness_started",
                "interval_sec": INTERVAL_SEC,
                "out": str(OUT),
                "health": str(HEALTH_PATH),
            }
        ),
        flush=True,
    )

    while True:
        try:
            at = _req("GET", AUTO_TRADING_PATH, token)
            row = extract(at)
            last_trading_row = row
            last = (at.get("orchestrator") or {}).get("last_cycle") or {}
            fp = fingerprint(last if isinstance(last, dict) else {})
            # Successful poll → trading snapshot only (never wipe on auth errors)
            SUMMARY.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")

            now = datetime.now(UTC)
            gap = None
            if last_ok_at is not None:
                gap = round((now - last_ok_at).total_seconds(), 1)
            last_ok_at = now
            consecutive_ok += 1

            # Auth recovered after prior failure
            if open_incident is not None:
                recovered_at = now.isoformat()
                open_incident["recovery_status"] = "RECOVERED"
                open_incident["recovered_at"] = recovered_at
                wh.mark_open_incidents_recovered(recovered_at=recovered_at)
                last_recovery_time = recovered_at
                print(
                    json.dumps(
                        {
                            "event": "witness_auth_recovered",
                            "label": "Recovered",
                            "at": recovered_at,
                            "prior_incident": open_incident.get("id"),
                        }
                    ),
                    flush=True,
                )
                open_incident = None
                auth_retry_count = 0
                last_auth_error = None

            wh.write_health(
                wh.build_health_snapshot(
                    authentication="OK",
                    authentication_label=None,
                    last_successful_heartbeat=now.isoformat(),
                    last_authentication_error=None,
                    recovery_time=last_recovery_time,
                    heartbeat_continuity={
                        "expected_interval_sec": INTERVAL_SEC,
                        "last_gap_sec": gap,
                        "consecutive_ok": consecutive_ok,
                        "status": "HEALTHY"
                        if gap is None or gap < INTERVAL_SEC * 3
                        else "GAP",
                    },
                    trading_execution_health=_trading_health_from_row(row),
                    open_auth_incident=None,
                    witness_process="running",
                    interval_sec=INTERVAL_SEC,
                )
            )

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
                    print(
                        'AGENT_LOOP_WAKE_live_exec {"prompt":"First MT5 execution '
                        'captured — summarize ticket and stop witness if complete"}',
                        flush=True,
                    )
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
                            "witness_auth": "OK",
                        },
                        default=str,
                    ),
                    flush=True,
                )
        except Exception as exc:
            consecutive_ok = 0
            endpoint = AUTO_TRADING_PATH
            http_status = None
            err = str(exc)
            if isinstance(exc, WitnessHttpError):
                endpoint = exc.endpoint
                http_status = exc.http_status
            else:
                http_status = wh.parse_http_status(err)

            fault = wh.classify_witness_fault(err, http_status)

            if fault == "auth":
                auth_retry_count += 1
                now_iso = datetime.now(UTC).isoformat()
                if open_incident is None:
                    open_incident = {
                        "id": str(uuid4()),
                        "utc_timestamp": now_iso,
                        "endpoint": endpoint,
                        "http_status": http_status or 401,
                        "retry_count": auth_retry_count,
                        "recovery_status": "ONGOING",
                        "error": err,
                        "recovered_at": None,
                    }
                    wh.append_auth_incident(dict(open_incident))
                else:
                    open_incident["retry_count"] = auth_retry_count
                    open_incident["error"] = err
                    open_incident["http_status"] = http_status or open_incident.get(
                        "http_status"
                    )
                    open_incident["endpoint"] = endpoint

                last_auth_error = {
                    "utc_timestamp": now_iso,
                    "endpoint": endpoint,
                    "http_status": http_status or 401,
                    "retry_count": auth_retry_count,
                    "error": err,
                    "label": AUTH_LABEL,
                }

                print(
                    json.dumps(
                        {
                            "event": "witness_auth_failed",
                            "label": AUTH_LABEL,
                            "utc_timestamp": now_iso,
                            "endpoint": endpoint,
                            "http_status": http_status or 401,
                            "retry_count": auth_retry_count,
                            "recovery_status": "ONGOING",
                            "error": err,
                            # Explicit: not an execution failure
                            "trading_execution_affected": False,
                        }
                    ),
                    flush=True,
                )

                wh.write_health(
                    wh.build_health_snapshot(
                        authentication="FAILED",
                        authentication_label=AUTH_LABEL,
                        last_successful_heartbeat=(
                            last_ok_at.isoformat() if last_ok_at else None
                        ),
                        last_authentication_error=last_auth_error,
                        recovery_time=last_recovery_time,
                        heartbeat_continuity={
                            "expected_interval_sec": INTERVAL_SEC,
                            "last_gap_sec": None,
                            "consecutive_ok": 0,
                            "status": "AUTH_INTERRUPT",
                        },
                        trading_execution_health=_trading_health_from_row(
                            last_trading_row
                        ),
                        open_auth_incident=open_incident,
                        witness_process="running",
                        interval_sec=INTERVAL_SEC,
                    )
                )

                # Refresh token — still never mutates trading
                try:
                    token = login()
                except Exception as login_exc:
                    print(
                        json.dumps(
                            {
                                "event": "witness_auth_relogin_failed",
                                "label": AUTH_LABEL,
                                "error": str(login_exc),
                                "at": datetime.now(UTC).isoformat(),
                            }
                        ),
                        flush=True,
                    )
            else:
                print(
                    json.dumps(
                        {
                            "event": "witness_error",
                            "fault": fault,
                            "error": err,
                            "endpoint": endpoint,
                            "http_status": http_status,
                            "at": datetime.now(UTC).isoformat(),
                            "trading_execution_affected": False,
                        }
                    ),
                    flush=True,
                )
                wh.write_health(
                    wh.build_health_snapshot(
                        authentication="OK"
                        if open_incident is None
                        else "FAILED",
                        authentication_label=AUTH_LABEL if open_incident else None,
                        last_successful_heartbeat=(
                            last_ok_at.isoformat() if last_ok_at else None
                        ),
                        last_authentication_error=last_auth_error,
                        recovery_time=last_recovery_time,
                        heartbeat_continuity={
                            "expected_interval_sec": INTERVAL_SEC,
                            "last_gap_sec": None,
                            "consecutive_ok": 0,
                            "status": "TRANSPORT_INTERRUPT",
                        },
                        trading_execution_health=_trading_health_from_row(
                            last_trading_row
                        ),
                        open_auth_incident=open_incident,
                        witness_process="running",
                        interval_sec=INTERVAL_SEC,
                    )
                )
                if fault != "auth":
                    try:
                        token = login()
                    except Exception:
                        pass
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
