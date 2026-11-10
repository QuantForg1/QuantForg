"""Provision disposable staging customers, run Phase 8.7 JWT accept, cleanup.

Reads staging Supabase admin secrets only from:
  %LOCALAPPDATA%\\QuantForg\\secrets\\staging

Never prints JWTs, passwords, or service-role keys.
Writes QF_STAGING_CUSTOMER_*_JWT into gitignored deploy/mt5_worker_agent/local.env,
runs staging_phase87_customer_jwt_accept.py, then deletes disposable identities.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "deploy" / "mt5_worker_agent" / "local.env"
EXAMPLE = ROOT / "deploy" / "mt5_worker_agent" / "local.env.example"
SEC = Path.home() / "AppData" / "Local" / "QuantForg" / "secrets" / "staging"
API = "https://quantforg-staging.up.railway.app/api/v1"
STAGING_REF = "saxsyobktmlyjghumxfz"
PROD_REF = "otqyhlmwaifokrczryrc"
RESULTS: list[tuple[str, str, str]] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    print(f"{status}: {name}" + (f" | {detail}" if detail else ""))


def _read(name: str) -> str:
    return (SEC / name).read_text(encoding="ascii").strip()


def pw(n: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def http(method: str, url: str, headers: dict | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode(errors="ignore")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:240]}
    except TimeoutError:
        return 599, {"error": "timeout"}


def admin(service: str) -> dict[str, str]:
    return {
        "apikey": service,
        "Authorization": f"Bearer {service}",
        "Content-Type": "application/json",
    }


def create_user(url: str, service: str, email: str, password: str) -> str:
    st, payload = http(
        "POST",
        f"{url}/auth/v1/admin/users",
        admin(service),
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"display_name": email.split("@")[0]},
        },
    )
    if st not in {200, 201}:
        raise RuntimeError(f"create_user http={st}")
    return str(payload.get("id") or payload.get("user", {}).get("id"))


def ensure_app_user(url: str, service: str, auth_id: str, email: str) -> str:
    st, payload = http(
        "POST",
        f"{url}/rest/v1/users?on_conflict=auth_user_id",
        {**admin(service), "Prefer": "resolution=merge-duplicates,return=representation"},
        {
            "auth_user_id": auth_id,
            "email": email,
            "display_name": email.split("@")[0][:32],
            "role": "trader",
            "status": "active",
            "password_hash": "",
        },
    )
    if st in {200, 201} and isinstance(payload, list) and payload:
        return str(payload[0]["id"])
    st, rows = http(
        "GET",
        f"{url}/rest/v1/users?auth_user_id=eq.{auth_id}&select=id",
        admin(service),
    )
    if st == 200 and isinstance(rows, list) and rows:
        return str(rows[0]["id"])
    raise RuntimeError(f"app_user failed http={st}")


def delete_user(url: str, service: str, auth_id: str, app_id: str) -> None:
    http("DELETE", f"{url}/auth/v1/admin/users/{auth_id}", admin(service))
    http("DELETE", f"{url}/rest/v1/users?id=eq.{app_id}", admin(service))


def upsert_env(updates: dict[str, str]) -> None:
    if not ENV_PATH.is_file():
        if EXAMPLE.is_file():
            ENV_PATH.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            ENV_PATH.write_text("", encoding="utf-8")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    keys = set(updates)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        raw = line.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key = raw.split("=", 1)[0].strip()
            if key in keys:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def clear_env_keys(keys: list[str]) -> None:
    if not ENV_PATH.is_file():
        return
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        raw = line.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key = raw.split("=", 1)[0].strip()
            if key in keys:
                continue
        out.append(line)
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def login(email: str, password: str) -> str:
    st, sess = http(
        "POST",
        f"{API}/auth/login",
        {"Content-Type": "application/json"},
        {"email": email, "password": password},
    )
    if st != 200 or not isinstance(sess, dict):
        return ""
    return str(sess.get("access_token") or "")


def main() -> int:
    if not SEC.is_dir():
        rec("staging_secrets", "BLOCKED", "missing LOCALAPPDATA QuantForg/secrets/staging")
        return 2

    url = _read("supabase_url.txt").rstrip("/")
    service = _read("supabase_service_role_key.txt")
    rec(
        "staging_project_isolation",
        "PASS" if STAGING_REF in url and PROD_REF not in url else "FAIL",
        "staging_ref_ok" if STAGING_REF in url else "wrong_project",
    )
    if STAGING_REF not in url or PROD_REF in url:
        return 1

    st, _ = http("GET", "https://quantforg-staging.up.railway.app/api/v1/health/live", {})
    rec("staging_health", "PASS" if st == 200 else "FAIL", f"http={st}")
    if st != 200:
        return 1

    stamp = time.strftime("%Y%m%d%H%M%S")
    email_a = f"qf.ma.a.{stamp}@example.com"
    email_b = f"qf.ma.b.{stamp}@example.com"
    pass_a, pass_b = pw(), pw()
    auth_a = auth_b = app_a = app_b = ""
    try:
        auth_a = create_user(url, service, email_a, pass_a)
        auth_b = create_user(url, service, email_b, pass_b)
        app_a = ensure_app_user(url, service, auth_a, email_a)
        app_b = ensure_app_user(url, service, auth_b, email_b)
        rec("idents_provisioned", "PASS")

        token_a = login(email_a, pass_a)
        token_b = login(email_b, pass_b)
        rec("login_a", "PASS" if token_a else "FAIL")
        rec("login_b", "PASS" if token_b else "FAIL")
        if not token_a or not token_b:
            return 1

        upsert_env(
            {
                "QUANTFORG_API_BASE_URL": "https://quantforg-staging.up.railway.app",
                "QF_STAGING_CUSTOMER_A_JWT": token_a,
                "QF_STAGING_CUSTOMER_B_JWT": token_b,
            }
        )
        # Confirm keys present without printing values.
        blob = ENV_PATH.read_text(encoding="utf-8")
        has_a = bool(re.search(r"^QF_STAGING_CUSTOMER_A_JWT=.+$", blob, re.M))
        has_b = bool(re.search(r"^QF_STAGING_CUSTOMER_B_JWT=.+$", blob, re.M))
        rec(
            "jwts_stored_local_env",
            "PASS" if has_a and has_b else "FAIL",
            "gitignored local.env updated",
        )

        # Expired/revoked where testable: delete A auth session by rotating password
        # then attempt status with old token after optional revoke via admin ban.
        # Primary acceptance is the dedicated harness.
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "staging_phase87_customer_jwt_accept.py")],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        # Redact any accidental token fragments from captured output before print.
        out = (proc.stdout or "") + (proc.stderr or "")
        for tok in (token_a, token_b, service, pass_a, pass_b):
            if tok:
                out = out.replace(tok, "[REDACTED]")
        print(out.rstrip())
        rec(
            "jwt_accept_harness",
            "PASS" if proc.returncode == 0 else "FAIL",
            f"exit={proc.returncode}",
        )

        # Revoked token probe: ban user A, old JWT must fail
        http(
            "PUT",
            f"{url}/auth/v1/admin/users/{auth_a}",
            admin(service),
            {"ban_duration": "8760h"},
        )
        st_ban, _ = http(
            "GET",
            f"{API}/multi-account/dispatch/status",
            {"Authorization": f"Bearer {token_a}", "Accept": "application/json"},
        )
        rec(
            "revoked_or_banned_jwt_rejected",
            "PASS" if st_ban in {401, 403} else "FAIL",
            f"http={st_ban}",
        )
        return 0 if proc.returncode == 0 and st_ban in {401, 403} else 1
    finally:
        try:
            if auth_a and app_a:
                delete_user(url, service, auth_a, app_a)
            if auth_b and app_b:
                delete_user(url, service, auth_b, app_b)
            clear_env_keys(
                ["QF_STAGING_CUSTOMER_A_JWT", "QF_STAGING_CUSTOMER_B_JWT"]
            )
            rec("cleanup_disposable_idents", "PASS")
        except Exception as exc:  # noqa: BLE001
            rec("cleanup_disposable_idents", "FAIL", type(exc).__name__)

        failed = sum(1 for r in RESULTS if r[1] == "FAIL")
        blocked = sum(1 for r in RESULTS if r[1] in {"BLOCKED", "NOT_EXERCISED"})
        passed = sum(1 for r in RESULTS if r[1] == "PASS")
        print(
            f"\nPhase 8.7 provision+accept: {passed} PASS, {failed} FAIL, "
            f"{blocked} BLOCKED/NOT_EXERCISED"
        )


if __name__ == "__main__":
    raise SystemExit(main())
