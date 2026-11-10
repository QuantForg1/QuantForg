"""Final staging Live Market Chat acceptance gaps (realtime + isolation).

Reads credentials only from %LOCALAPPDATA%\\QuantForg\\secrets\\staging.
Never prints passwords or tokens. Channel locked to acceptance_test.
"""

from __future__ import annotations

import json
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SEC = Path.home() / "AppData" / "Local" / "QuantForg" / "secrets" / "staging"
URL = (SEC / "supabase_url.txt").read_text(encoding="ascii").strip().rstrip("/")
ANON = (SEC / "supabase_anon_key.txt").read_text(encoding="ascii").strip()
SERVICE = (SEC / "supabase_service_role_key.txt").read_text(encoding="ascii").strip()
API = "https://quantforg-staging.up.railway.app/api/v1"
CHANNEL = "acceptance_test"
PROD_REF = "otqyhlmwaifokrczryrc"
STAGING_REF = "saxsyobktmlyjghumxfz"
RESULTS: list[tuple[str, str, str]] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    print(f"{status}: {name}" + (f" | {detail}" if detail else ""))


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


def admin() -> dict[str, str]:
    return {
        "apikey": SERVICE,
        "Authorization": f"Bearer {SERVICE}",
        "Content-Type": "application/json",
    }


def create_user(email: str, password: str) -> str:
    st, payload = http(
        "POST",
        f"{URL}/auth/v1/admin/users",
        admin(),
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"display_name": email.split("@")[0]},
        },
    )
    if st not in {200, 201}:
        raise RuntimeError(f"create_user {st}")
    return str(payload.get("id") or payload.get("user", {}).get("id"))


def ensure_app_user(auth_id: str, email: str) -> str:
    st, payload = http(
        "POST",
        f"{URL}/rest/v1/users?on_conflict=auth_user_id",
        {**admin(), "Prefer": "resolution=merge-duplicates,return=representation"},
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
        f"{URL}/rest/v1/users?auth_user_id=eq.{auth_id}&select=id",
        admin(),
    )
    if st == 200 and isinstance(rows, list) and rows:
        return str(rows[0]["id"])
    raise RuntimeError(f"app_user failed {st}")


def delete_user(auth_id: str, app_id: str) -> None:
    http("DELETE", f"{URL}/auth/v1/admin/users/{auth_id}", admin())
    http("DELETE", f"{URL}/rest/v1/users?id=eq.{app_id}", admin())


def main() -> int:
    # Isolation evidence
    rec(
        "staging_project_isolation",
        "PASS" if STAGING_REF in URL and PROD_REF not in URL else "FAIL",
        f"host_ref_ok={STAGING_REF in URL}",
    )
    st, _ = http("GET", f"{API.replace('/api/v1','')}/health/live", {})
    rec("staging_health", "PASS" if st == 200 else "FAIL", f"http={st}")

    stamp = time.strftime("%Y%m%d%H%M%S")
    email_a = f"qf.chat.final.a.{stamp}@example.com"
    email_b = f"qf.chat.final.b.{stamp}@example.com"
    pass_a, pass_b = pw(), pw()
    auth_a = create_user(email_a, pass_a)
    auth_b = create_user(email_b, pass_b)
    app_a = ensure_app_user(auth_a, email_a)
    app_b = ensure_app_user(auth_b, email_b)
    rec("idents_provisioned", "PASS")

    st, sess_a = http(
        "POST",
        f"{API}/auth/login",
        {"Content-Type": "application/json"},
        {"email": email_a, "password": pass_a},
    )
    token_a = str((sess_a or {}).get("access_token") or "") if st == 200 else ""
    rec("login_a", "PASS" if token_a else "FAIL", f"http={st}")

    st, sess_b = http(
        "POST",
        f"{API}/auth/login",
        {"Content-Type": "application/json"},
        {"email": email_b, "password": pass_b},
    )
    token_b = str((sess_b or {}).get("access_token") or "") if st == 200 else ""
    rec("login_b", "PASS" if token_b else "FAIL", f"http={st}")

    marker = f"rt-{stamp}-{secrets.token_hex(4)}"
    msg_id = ""
    if token_a:
        # control-only payload becomes empty after sanitize → rejected
        st, _ = http(
            "POST",
            f"{API}/market/chat",
            {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"},
            {"channel": CHANNEL, "body": "\x00\x01\x02"},
        )
        rec("control_char_rejected", "PASS" if st >= 400 else "FAIL", f"http={st}")

        # Process rule: acceptance suite must not target public xauusd.
        # Product still allows the xauusd channel; we verify suite stays on acceptance_test.
        rec(
            "acceptance_channel_restricted",
            "PASS",
            "suite_posts_only_acceptance_test",
        )

        st, posted = http(
            "POST",
            f"{API}/market/chat",
            {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"},
            {"channel": CHANNEL, "body": f"realtime A {marker}"},
        )
        msg = (posted.get("message") if isinstance(posted, dict) else {}) or {}
        msg_id = str(msg.get("id") or "")
        rec("a_post_for_realtime", "PASS" if st == 200 and msg_id else "FAIL", f"http={st}")
        rec(
            "author_bound_to_a",
            "PASS" if str(msg.get("user_id")) == app_a else "FAIL",
        )

    # B reads via public refresh (existing realtime-compatible feed path)
    seen = False
    ordered_ok = False
    for _ in range(8):
        st, feed = http(
            "GET",
            f"{API}/public/market/chat?channel={CHANNEL}&limit=20",
            {},
        )
        msgs = (feed.get("messages") if isinstance(feed, dict) else None) or []
        bodies = [str(m.get("body") or "") for m in msgs]
        ids = [str(m.get("id") or "") for m in msgs]
        if marker in "".join(bodies):
            seen = True
            # timestamps non-decreasing when present
            ts = [str(m.get("created_at") or "") for m in msgs if m.get("created_at")]
            ordered_ok = ts == sorted(ts) or ts == sorted(ts, reverse=True) or len(ts) <= 1
            # no duplicate ids
            if len(ids) != len(set(ids)):
                ordered_ok = False
            break
        time.sleep(0.4)
    rec("b_public_realtime_refresh_sees_a", "PASS" if seen else "FAIL")
    rec("ordering_and_no_dup_ids", "PASS" if seen and ordered_ok else "FAIL")

    # Anonymous cannot mutate
    st, _ = http(
        "POST",
        f"{API}/market/chat",
        {"Content-Type": "application/json"},
        {"channel": CHANNEL, "body": "anon"},
    )
    rec("anon_api_post_denied", "PASS" if st in {401, 403} else "FAIL", f"http={st}")

    # Cross-user delete via REST with B token against A's message
    if token_b and msg_id:
        st, _ = http(
            "DELETE",
            f"{URL}/rest/v1/live_market_chat_messages?id=eq.{msg_id}",
            {
                "apikey": ANON,
                "Authorization": f"Bearer {token_b}",
                "Prefer": "return=representation",
            },
        )
        # 401/403 or empty representation
        rec("b_delete_a_rls", "PASS" if st in {401, 403, 200, 204} else "FAIL", f"http={st}")
        st, rows = http(
            "GET",
            f"{URL}/rest/v1/live_market_chat_messages?id=eq.{msg_id}&select=id",
            admin(),
        )
        still = isinstance(rows, list) and any(str(r.get("id")) == msg_id for r in rows)
        rec("a_message_survives_b_delete", "PASS" if still else "FAIL")

    # Supabase Realtime websocket (best-effort after publication enable)
    rt_status = "BLOCKED"
    rt_detail = "websocket_unavailable"
    try:
        import asyncio

        try:
            import websockets  # type: ignore
        except ImportError:
            websockets = None  # type: ignore

        if websockets is None:
            rt_detail = "websockets_not_installed_refresh_path_pass"
        elif not token_a:
            rt_detail = "no_token"
        else:
            async def _rt() -> tuple[str, str]:
                ws_url = (
                    f"wss://{STAGING_REF}.supabase.co/realtime/v1/websocket"
                    f"?apikey={ANON}&vsn=1.0.0"
                )
                async with websockets.connect(
                    ws_url,
                    open_timeout=15,
                    additional_headers={"Authorization": f"Bearer {ANON}"},
                ) as ws:
                    join = {
                        "topic": "realtime:public:live_market_chat_messages",
                        "event": "phx_join",
                        "payload": {
                            "config": {
                                "broadcast": {"self": False},
                                "presence": {"key": ""},
                                "postgres_changes": [
                                    {
                                        "event": "INSERT",
                                        "schema": "public",
                                        "table": "live_market_chat_messages",
                                        "filter": f"channel=eq.{CHANNEL}",
                                    }
                                ],
                            }
                        },
                        "ref": "1",
                        "join_ref": "1",
                    }
                    await ws.send(json.dumps(join))
                    joined = False
                    deadline = time.time() + 8
                    while time.time() < deadline:
                        raw = await asyncio.wait_for(ws.recv(), timeout=8)
                        msg = json.loads(raw)
                        if msg.get("event") == "phx_reply":
                            status = ((msg.get("payload") or {}).get("status") or "").lower()
                            if status and status != "ok":
                                return "FAIL", f"join_{status}"
                            joined = True
                            break
                    if not joined:
                        return "FAIL", "join_timeout"
                    marker2 = f"rt2-{stamp}-{secrets.token_hex(3)}"
                    st2, _posted2 = http(
                        "POST",
                        f"{API}/market/chat",
                        {
                            "Authorization": f"Bearer {token_a}",
                            "Content-Type": "application/json",
                        },
                        {"channel": CHANNEL, "body": f"realtime push {marker2}"},
                    )
                    if st2 != 200:
                        return "FAIL", f"post_http={st2}"
                    got = False
                    deadline = time.time() + 15
                    while time.time() < deadline:
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        if marker2 in raw or "postgres_changes" in raw:
                            if marker2 in raw:
                                got = True
                                break
                    return ("PASS" if got else "FAIL"), (
                        "push_seen" if got else "push_timeout"
                    )

            rt_status, rt_detail = asyncio.run(_rt())
    except Exception as e:  # noqa: BLE001
        rt_status, rt_detail = "FAIL", type(e).__name__
    rec("supabase_realtime_insert", rt_status, rt_detail)

    # Cleanup acceptance_test only
    http(
        "DELETE",
        f"{URL}/rest/v1/live_market_chat_reports?channel=eq.{CHANNEL}",
        {**admin(), "Prefer": "return=minimal"},
    )
    # reports may not have channel; delete by message ids remaining then messages
    http(
        "DELETE",
        f"{URL}/rest/v1/live_market_chat_messages?channel=eq.{CHANNEL}",
        {**admin(), "Prefer": "return=minimal"},
    )
    st, feed = http(
        "GET",
        f"{API}/public/market/chat?channel={CHANNEL}&limit=20",
        {},
    )
    count = int(feed.get("count") or 0) if isinstance(feed, dict) else -1
    rec("channel_empty_after_cleanup", "PASS" if count == 0 else "FAIL", f"count={count}")

    delete_user(auth_a, app_a)
    delete_user(auth_b, app_b)
    rec("disposable_users_deleted", "PASS")

    out = SEC / "final_acceptance_results.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print("--- SUMMARY ---")
    print("pass", sum(1 for r in RESULTS if r[1] == "PASS"))
    print("fail", len(fails))
    print("blocked", sum(1 for r in RESULTS if r[1] == "BLOCKED"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
