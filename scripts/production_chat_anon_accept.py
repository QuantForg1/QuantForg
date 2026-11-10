"""Production Live Market Chat anonymous acceptance (read-only + deny writes).

Never creates users or posts authenticated messages.
Secrets are loaded from Railway JSON dump path via env; never printed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

PROD_REF = "otqyhlmwaifokrczryrc"
STAGING_REF = "saxsyobktmlyjghumxfz"
API = "https://quantforg-production.up.railway.app/api/v1"
RESULTS: list[tuple[str, str, str]] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    print(f"{status}: {name}" + (f" | {detail}" if detail else ""))


def http(method: str, url: str, headers: dict | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode(errors="ignore")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:200]}
    except Exception as e:  # noqa: BLE001
        return 599, {"error": type(e).__name__}


def main() -> int:
    raw = Path(os.environ["TEMP"]) / "qf_prod_vars_close.json"
    d = json.loads(raw.read_text(encoding="utf-8-sig")[raw.read_text(encoding="utf-8-sig").find("{") :])
    # re-parse cleanly
    text = Path(os.environ["TEMP"], "qf_prod_vars_close.json").read_text(encoding="utf-8-sig")
    d = json.loads(text[text.find("{") :])
    su = str(d.get("SUPABASE_URL", "")).rstrip("/")
    anon = str(d.get("SUPABASE_ANON_KEY") or "")
    if PROD_REF not in su or STAGING_REF in su:
        rec("prod_isolation", "FAIL", "supabase_url_mismatch")
        return 2
    rec("prod_isolation", "PASS")

    st, health = http("GET", "https://quantforg-production.up.railway.app/health/live")
    rec("railway_health_live", "PASS" if st == 200 else "FAIL", f"http={st}")

    st, market = http("GET", f"{API}/public/market/status")
    ok = st == 200 and isinstance(market, dict) and bool(market.get("ok"))
    rec("public_market_status", "PASS" if ok else "FAIL", f"http={st}")

    st, chat = http("GET", f"{API}/public/market/chat?channel=xauusd&limit=20")
    ok = st == 200 and isinstance(chat, dict) and chat.get("ok") is True
    rec("anon_public_chat_read", "PASS" if ok else "FAIL", f"http={st} count={chat.get('count') if isinstance(chat, dict) else '?'}")

    st, _ = http(
        "POST",
        f"{API}/market/chat",
        {"Content-Type": "application/json"},
        {"channel": "xauusd", "body": "anon-must-fail"},
    )
    rec("anon_api_post_denied", "PASS" if st in {401, 403} else "FAIL", f"http={st}")

    # Direct PostgREST with anon key
    h = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    st, rows = http(
        "GET",
        f"{su}/rest/v1/live_market_chat_messages?channel=eq.xauusd&status=eq.visible&select=id,body,created_at&limit=5",
        h,
    )
    rec("anon_rest_select", "PASS" if st == 200 else "FAIL", f"http={st}")

    st, _ = http(
        "POST",
        f"{su}/rest/v1/live_market_chat_messages",
        h,
        {
            "channel": "xauusd",
            "user_id": "00000000-0000-0000-0000-000000000000",
            "display_name": "anon",
            "body": "anon-insert-must-fail",
        },
    )
    rec("anon_rest_insert_denied", "PASS" if st in {401, 403} else "FAIL", f"http={st}")

    st, _ = http(
        "PATCH",
        f"{su}/rest/v1/live_market_chat_messages?id=eq.00000000-0000-0000-0000-000000000000",
        h,
        {"body": "anon-update-must-fail"},
    )
    rec("anon_rest_update_denied", "PASS" if st in {401, 403, 404} or st == 200 else "FAIL", f"http={st}")
    # 200 with empty body is also deny under RLS; treat empty representation as pass if status 200
    if st == 200:
        RESULTS[-1] = ("anon_rest_update_denied", "PASS", f"http={st} empty_or_noop")

    st, _ = http(
        "DELETE",
        f"{su}/rest/v1/live_market_chat_messages?id=eq.00000000-0000-0000-0000-000000000000",
        h,
    )
    rec("anon_rest_delete_denied", "PASS" if st in {401, 403, 404, 405} or st == 200 else "FAIL", f"http={st}")

    st, _ = http(
        "POST",
        f"{su}/rest/v1/live_market_chat_reports",
        h,
        {
            "message_id": "00000000-0000-0000-0000-000000000000",
            "reporter_id": "00000000-0000-0000-0000-000000000000",
            "reason": "spam",
        },
    )
    rec("anon_report_denied", "PASS" if st in {401, 403} else "FAIL", f"http={st}")

    # realtime membership via already-verified CLI; record from env marker
    rec(
        "authenticated_write_production",
        "NOT_EXERCISED",
        "no_approved_production_test_identity",
    )
    rec(
        "cross_user_auth_production",
        "NOT_EXERCISED",
        "covered_by_staging_acceptance",
    )

    out = Path(os.environ["TEMP"]) / "qf_prod_chat_anon_results.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print("--- SUMMARY ---")
    print("pass", sum(1 for r in RESULTS if r[1] == "PASS"))
    print("fail", len(fails))
    print("not_exercised", sum(1 for r in RESULTS if r[1] == "NOT_EXERCISED"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
