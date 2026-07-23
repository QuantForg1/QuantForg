"""Witness observability — separate auth health from trading execution health.

Read-only helpers for the live execution witness. Never touches Strategy, Risk,
Safety, OMS, or MT5 execution. Production Acceptance must not consume these
signals unless real execution evidence is present.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "docs" / "production" / "reports"
HEALTH_PATH = REPORTS / "witness_health_latest.json"
AUTH_INCIDENTS_PATH = REPORTS / "witness_auth_incidents.jsonl"
WITNESS_LATEST_PATH = REPORTS / "live_execution_witness_latest.json"

AUTH_LABEL = "Witness Authentication Failed"


@dataclass
class AuthIncident:
    utc_timestamp: str
    endpoint: str
    http_status: int | None
    retry_count: int
    recovery_status: str  # ONGOING | RECOVERED | FAILED
    error: str
    recovered_at: str | None = None
    id: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def is_auth_failure(error: str, http_status: int | None = None) -> bool:
    if http_status == 401:
        return True
    blob = (error or "").lower()
    return (
        "401" in blob
        or "unauthorized" in blob
        or "authentication" in blob and "fail" in blob
    )


def classify_witness_fault(
    error: str, http_status: int | None = None
) -> str:
    """Return auth | network | other — never labels trading execution failure."""
    if is_auth_failure(error, http_status):
        return "auth"
    blob = (error or "").lower()
    if any(
        m in blob
        for m in (
            "getaddrinfo",
            "timed out",
            "timeout",
            "connection refused",
            "network",
            "dns",
            "urlopen error",
        )
    ):
        return "network"
    return "other"


def parse_http_status(error: str) -> int | None:
    m = re.search(r"HTTP\s*Error\s*(\d{3})", error or "", re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{3})\b", error or "")
    if m and m.group(1) in {"401", "403", "404", "500", "502", "503"}:
        return int(m.group(1))
    return None


def empty_health() -> dict[str, Any]:
    return {
        "authentication": "UNKNOWN",
        "authentication_label": None,
        "last_successful_heartbeat": None,
        "last_authentication_error": None,
        "recovery_time": None,
        "heartbeat_continuity": {
            "expected_interval_sec": None,
            "last_gap_sec": None,
            "consecutive_ok": 0,
            "status": "UNKNOWN",
        },
        "trading_execution_health": {
            "note": "Derived only from successful witness polls of /ite/ops/auto-trading",
            "last_cycle_outcome": None,
            "last_session": None,
            "mt5_ticket": None,
        },
        "open_auth_incident": None,
        "auth_incidents_recent": [],
        "updated_at": None,
        "witness_process": "unknown",
    }


def load_auth_incidents(*, limit: int = 50) -> list[dict[str, Any]]:
    if not AUTH_INCIDENTS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in AUTH_INCIDENTS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-limit:]


def append_auth_incident(incident: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    with AUTH_INCIDENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(incident, default=str) + "\n")


def rewrite_auth_incidents(rows: list[dict[str, Any]]) -> None:
    """Rewrite ledger (used when marking recovery on the open incident)."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    with AUTH_INCIDENTS_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")


def mark_open_incidents_recovered(*, recovered_at: str | None = None) -> list[dict[str, Any]]:
    moment = recovered_at or datetime.now(UTC).isoformat()
    rows = load_auth_incidents(limit=10_000)
    changed = False
    for row in rows:
        if row.get("recovery_status") == "ONGOING":
            row["recovery_status"] = "RECOVERED"
            row["recovered_at"] = moment
            changed = True
    if changed:
        rewrite_auth_incidents(rows)
    return rows


def build_health_snapshot(
    *,
    authentication: str,
    authentication_label: str | None,
    last_successful_heartbeat: str | None,
    last_authentication_error: dict[str, Any] | None,
    recovery_time: str | None,
    heartbeat_continuity: dict[str, Any],
    trading_execution_health: dict[str, Any],
    open_auth_incident: dict[str, Any] | None,
    witness_process: str = "running",
    interval_sec: int | None = None,
) -> dict[str, Any]:
    recent = load_auth_incidents(limit=20)
    snap = {
        "authentication": authentication,
        "authentication_label": authentication_label,
        "last_successful_heartbeat": last_successful_heartbeat,
        "last_authentication_error": last_authentication_error,
        "recovery_time": recovery_time,
        "heartbeat_continuity": {
            **heartbeat_continuity,
            "expected_interval_sec": interval_sec
            or heartbeat_continuity.get("expected_interval_sec"),
        },
        "trading_execution_health": trading_execution_health,
        "open_auth_incident": open_auth_incident,
        "auth_incidents_recent": list(reversed(recent[-10:])),
        "updated_at": datetime.now(UTC).isoformat(),
        "witness_process": witness_process,
        "separation_note": (
            "Witness authentication health is independent of trading execution "
            "health. Auth failures must not alter Production Acceptance."
        ),
    }
    return snap


def write_health(snapshot: dict[str, Any]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    return HEALTH_PATH


def read_health() -> dict[str, Any]:
    if not HEALTH_PATH.exists():
        base = empty_health()
        base["witness_process"] = "no_health_file"
        # Still surface last trading snapshot if present (execution only)
        if WITNESS_LATEST_PATH.exists():
            try:
                trading = json.loads(WITNESS_LATEST_PATH.read_text(encoding="utf-8"))
                base["trading_execution_health"] = {
                    "note": "From last successful witness poll only",
                    "last_cycle_outcome": trading.get("cycle_outcome"),
                    "last_session": trading.get("session"),
                    "mt5_ticket": trading.get("mt5_ticket"),
                    "observed_at": trading.get("observed_at"),
                    "ops_mode": trading.get("ops_mode"),
                }
            except (OSError, json.JSONDecodeError):
                pass
        base["auth_incidents_recent"] = list(
            reversed(load_auth_incidents(limit=10))
        )
        return base
    try:
        return json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_health()


def dashboard_payload() -> dict[str, Any]:
    """API/UI payload — never includes fabricated execution acceptance."""
    health = read_health()
    return {
        "health": health,
        "authentication": health.get("authentication"),
        "last_successful_heartbeat": health.get("last_successful_heartbeat"),
        "last_authentication_error": health.get("last_authentication_error"),
        "recovery_time": health.get("recovery_time"),
        "heartbeat_continuity": health.get("heartbeat_continuity"),
        "trading_execution_health": health.get("trading_execution_health"),
        "auth_incidents": health.get("auth_incidents_recent")
        or load_auth_incidents(limit=20),
        "acceptance_isolation": {
            "witness_auth_affects_production_acceptance": False,
            "reason": (
                "Production Acceptance uses live OMS/broker/MT5/Deal evidence only; "
                "witness HTTP 401 is authentication health, not execution failure."
            ),
        },
    }
