#!/usr/bin/env python3
"""Phase-4 continuous monitor — authenticated robot-health probe.

Requires QUANTFORG_OWNER_TOKEN **or** Supabase Admin magic-link inputs via
Railway-linked env (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) and owner email.

Never prints tokens. Exit codes:
  0 = healthy / expected NO_TRADE selectivity
  1 = alert conditions tripped
  2 = auth or transport failure
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

API_BASE = (
    os.environ.get("QUANTFORG_API_BASE")
    or "https://quantforg-production.up.railway.app/api/v1"
).rstrip("/")
OWNER_EMAIL = os.environ.get("QUANTFORG_OWNER_EMAIL") or "p7provider@gmail.com"


def _http_json(
    method: str, url: str, headers: dict[str, str], body: dict | None = None
) -> tuple[int, Any]:
    data = None
    hdrs = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            return int(resp.status), json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            payload = {"error": raw[:500]}
        return int(exc.code), payload


def obtain_owner_token() -> str:
    existing = (os.environ.get("QUANTFORG_OWNER_TOKEN") or "").strip()
    if existing:
        return existing
    supabase = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    service = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    anon = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not supabase or not service:
        raise RuntimeError(
            "Set QUANTFORG_OWNER_TOKEN or SUPABASE_URL+SUPABASE_SERVICE_ROLE_KEY"
        )
    admin_headers = {
        "apikey": service,
        "Authorization": f"Bearer {service}",
        "Content-Type": "application/json",
    }
    code, link = _http_json(
        "POST",
        f"{supabase}/auth/v1/admin/generate_link",
        admin_headers,
        {"type": "magiclink", "email": OWNER_EMAIL},
    )
    if code >= 400 or not isinstance(link, dict) or not link.get("hashed_token"):
        raise RuntimeError(f"magiclink failed HTTP {code}")
    verify_key = anon or service
    code, session = _http_json(
        "POST",
        f"{supabase}/auth/v1/verify",
        {"apikey": verify_key, "Content-Type": "application/json"},
        {"token_hash": link["hashed_token"], "type": "magiclink"},
    )
    if code >= 400 or not isinstance(session, dict) or not session.get("access_token"):
        raise RuntimeError(f"verify failed HTTP {code}")
    return str(session["access_token"])


def evaluate(health: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    robot = health.get("robot") or {}
    if robot.get("last_error"):
        alerts.append(f"robot_last_error={robot.get('last_error')}")
    if robot.get("market_data_fresh") is False:
        alerts.append("market_data_stale")
    age = robot.get("last_quote_age_seconds")
    if isinstance(age, (int, float)) and age > 30:
        alerts.append(f"quote_age_seconds={age}")
    for s in health.get("strategies") or []:
        st = s.get("operational_status")
        sid = s.get("strategy_id")
        if st in {"DISABLED", "DATA_UNAVAILABLE", "ERROR"}:
            alerts.append(f"strategy_{sid}_{st}")
        if int(s.get("scans") or 0) == 0 and st not in {"DISABLED"}:
            alerts.append(f"strategy_{sid}_no_scans")
    m1 = health.get("m1") or {}
    if m1.get("m1_live_submit") is True:
        alerts.append(
            "advisory:m1_live_submit_ON_confirm_owner_intent_if_expectancy_negative"
        )
    for sid in (health.get("performance") or {}).get("deteriorating_strategy_ids") or []:
        alerts.append(f"deteriorating:{sid}")
    return alerts


def main() -> int:
    try:
        token = obtain_owner_token()
    except Exception as exc:
        print(json.dumps({"ok": False, "stage": "auth", "error": str(exc)}))
        return 2
    code, health = _http_json(
        "GET",
        f"{API_BASE}/ite/ops/robot-health-monitor",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if code == 401:
        print(json.dumps({"ok": False, "stage": "ops", "http": 401, "note": "auth_gate"}))
        return 2
    if code >= 400 or not isinstance(health, dict):
        print(json.dumps({"ok": False, "stage": "ops", "http": code}))
        return 2
    alerts = evaluate(health)
    report = {
        "ok": len([a for a in alerts if not a.startswith("advisory:")]) == 0,
        "as_of": datetime.now(UTC).isoformat(),
        "probe_as_of": health.get("as_of"),
        "soe_version": health.get("orchestration_version"),
        "robot": health.get("robot"),
        "m1": health.get("m1"),
        "strategies": [
            {
                "strategy_id": s.get("strategy_id"),
                "operational_status": s.get("operational_status"),
                "scans": s.get("scans"),
                "accepted": s.get("accepted"),
                "rejected": s.get("rejected"),
                "closed_trades": s.get("closed_trades"),
            }
            for s in (health.get("strategies") or [])
        ],
        "alerts": alerts,
    }
    print(json.dumps(report, indent=2, default=str))
    hard = [a for a in alerts if not a.startswith("advisory:")]
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
