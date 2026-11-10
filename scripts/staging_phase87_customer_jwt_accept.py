"""Phase 8.7 — staging customer JWT acceptance for multi-account dispatch/status.

Uses disposable staging identities only. Never prints JWT/token values.
Loads deploy/mt5_worker_agent/local.env for optional staging customer JWTs.

Required env (staging only — never production):
  QF_STAGING_CUSTOMER_A_JWT
  QF_STAGING_CUSTOMER_B_JWT  (for cross-customer isolation)

Forces QUANTFORG_API_BASE_URL to staging Railway.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "deploy" / "mt5_worker_agent" / "local.env"
STAGING_API = "https://quantforg-staging.up.railway.app"
RESULTS: list[tuple[str, str, str]] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    print(f"{status}: {name}" + (f" | {detail}" if detail else ""))


def load_env() -> None:
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key == "QUANTFORG_API_BASE_URL":
                continue
            os.environ.setdefault(key, value.strip())
    os.environ["QUANTFORG_API_BASE_URL"] = STAGING_API


def _redact(text: str) -> str:
    out = text
    for key in (
        "QF_STAGING_CUSTOMER_A_JWT",
        "QF_STAGING_CUSTOMER_B_JWT",
        "WORKER_SERVICE_TOKEN",
    ):
        val = (os.environ.get(key) or "").strip()
        if val and len(val) > 8:
            out = out.replace(val, "[REDACTED]")
    return out


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict | None = None,
) -> tuple[int, object]:
    base = os.environ["QUANTFORG_API_BASE_URL"].rstrip("/")
    url = f"{base}/api/v1{path}"
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:200]}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"_raw": _redact(raw[:200])}
        return int(exc.code), payload
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": _redact(str(exc))}


def _assert_no_secrets(payload: object) -> bool:
    blob = json.dumps(payload, default=str).lower()
    if "bearer " in blob:
        return False
    for key in ("password", "secret", "sealed_envelope", "service_token", "worker_token"):
        needle = f'"{key}":'
        if needle not in blob:
            continue
        if f'"{key}": null' in blob or f'"{key}":null' in blob:
            continue
        if f'"{key}": ""' in blob or f'"{key}":""' in blob:
            continue
        return False
    for env_key in ("QF_STAGING_CUSTOMER_A_JWT", "QF_STAGING_CUSTOMER_B_JWT", "WORKER_SERVICE_TOKEN"):
        val = (os.environ.get(env_key) or "").strip()
        if val and val in json.dumps(payload, default=str):
            return False
    return True


def main() -> int:
    load_env()
    jwt_a = (os.environ.get("QF_STAGING_CUSTOMER_A_JWT") or "").strip()
    jwt_b = (os.environ.get("QF_STAGING_CUSTOMER_B_JWT") or "").strip()

    # 1) No JWT → 401
    code, _ = _request("GET", "/multi-account/dispatch/status")
    if code == 401:
        rec("no_jwt_401", "PASS", f"status={code}")
    else:
        rec("no_jwt_401", "FAIL", f"status={code}")

    # 2) Invalid JWT → 401
    code, _ = _request(
        "GET",
        "/multi-account/dispatch/status",
        token="invalid.staging.jwt",
    )
    if code == 401:
        rec("invalid_jwt_401", "PASS", f"status={code}")
    else:
        rec("invalid_jwt_401", "FAIL", f"status={code}")

    if not jwt_a or not jwt_b:
        rec(
            "customer_jwt_isolation",
            "NOT_EXERCISED",
            "set QF_STAGING_CUSTOMER_A_JWT and QF_STAGING_CUSTOMER_B_JWT in local.env "
            "(staging disposable users only)",
        )
        rec(
            "valid_jwt_own_data",
            "NOT_EXERCISED",
            "requires staging customer JWTs",
        )
        rec(
            "forged_ids_rejected",
            "NOT_EXERCISED",
            "requires staging customer JWTs",
        )
    else:
        code_a, body_a = _request(
            "GET", "/multi-account/dispatch/status", token=jwt_a
        )
        code_b, body_b = _request(
            "GET", "/multi-account/dispatch/status", token=jwt_b
        )
        if code_a == 200 and isinstance(body_a, dict):
            if not _assert_no_secrets(body_a):
                rec("valid_jwt_own_data", "FAIL", "secret leakage in A payload")
            elif body_a.get("live_submit_allowed") is not False:
                rec("valid_jwt_own_data", "FAIL", "live_submit_allowed must be false")
            elif body_a.get("credentials_exposed") is not False:
                rec("valid_jwt_own_data", "FAIL", "credentials_exposed must be false")
            else:
                rec(
                    "valid_jwt_own_data",
                    "PASS",
                    f"user={body_a.get('user_id')} jobs={body_a.get('job_count')}",
                )
        else:
            rec("valid_jwt_own_data", "FAIL", f"status={code_a}")

        if (
            code_a == 200
            and code_b == 200
            and isinstance(body_a, dict)
            and isinstance(body_b, dict)
        ):
            uid_a = str(body_a.get("user_id") or "")
            uid_b = str(body_b.get("user_id") or "")
            jobs_a = body_a.get("jobs") if isinstance(body_a.get("jobs"), list) else []
            jobs_b = body_b.get("jobs") if isinstance(body_b.get("jobs"), list) else []
            leak_a = any(str(j.get("user_id")) == uid_b for j in jobs_a if isinstance(j, dict))
            leak_b = any(str(j.get("user_id")) == uid_a for j in jobs_b if isinstance(j, dict))
            if not uid_a or not uid_b or uid_a == uid_b:
                rec(
                    "customer_jwt_isolation",
                    "FAIL",
                    "A/B must be distinct staging user ids",
                )
            elif leak_a or leak_b:
                rec("customer_jwt_isolation", "FAIL", "cross-customer job visibility")
            elif not _assert_no_secrets(body_b):
                rec("customer_jwt_isolation", "FAIL", "secret leakage in B payload")
            else:
                rec(
                    "customer_jwt_isolation",
                    "PASS",
                    "A and B see only own user_id / jobs",
                )
        else:
            rec(
                "customer_jwt_isolation",
                "FAIL",
                f"status_a={code_a} status_b={code_b}",
            )

        # Forged account query — customer status has no account_id query param;
        # confirm response user_id always matches token subject, never forged header.
        code_f, body_f = _request(
            "GET",
            "/multi-account/dispatch/status?user_id=00000000-0000-0000-0000-000000000099",
            token=jwt_a,
        )
        if (
            code_f == 200
            and isinstance(body_f, dict)
            and str(body_f.get("user_id")) == str(body_a.get("user_id") if isinstance(body_a, dict) else "")
        ):
            rec(
                "forged_ids_rejected",
                "PASS",
                "query user_id ignored; session identity wins",
            )
        elif code_f in {400, 401, 403}:
            rec("forged_ids_rejected", "PASS", f"status={code_f}")
        else:
            rec("forged_ids_rejected", "FAIL", f"status={code_f}")

    # Owner ops must not be reachable with customer JWT when present
    if jwt_a:
        code_o, _ = _request("GET", "/multi-account/ops/summary", token=jwt_a)
        if code_o in {401, 403}:
            rec("customer_denied_owner_ops", "PASS", f"status={code_o}")
        else:
            rec("customer_denied_owner_ops", "FAIL", f"status={code_o}")
    else:
        rec("customer_denied_owner_ops", "NOT_EXERCISED", "requires JWT A")

    failed = sum(1 for r in RESULTS if r[1] == "FAIL")
    blocked = sum(1 for r in RESULTS if r[1] in {"BLOCKED", "NOT_EXERCISED"})
    passed = sum(1 for r in RESULTS if r[1] == "PASS")
    print(
        f"\nPhase 8.7 customer JWT: {passed} PASS, {failed} FAIL, "
        f"{blocked} NOT_EXERCISED/BLOCKED"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
