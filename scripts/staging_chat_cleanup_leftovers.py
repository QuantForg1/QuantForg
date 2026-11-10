"""Remove leftover staging acceptance identities/messages. Staging project only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

SEC = Path.home() / "AppData" / "Local" / "QuantForg" / "secrets" / "staging"
URL = (SEC / "supabase_url.txt").read_text(encoding="ascii").strip().rstrip("/")
SERVICE = (SEC / "supabase_service_role_key.txt").read_text(encoding="ascii").strip()
STAGING = "saxsyobktmlyjghumxfz"
PROD = "otqyhlmwaifokrczryrc"


def http(method: str, url: str):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "apikey": SERVICE,
            "Authorization": f"Bearer {SERVICE}",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode(errors="ignore")
            return r.status, json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, raw[:200]


def main() -> int:
    if STAGING not in URL or PROD in URL:
        print("REFUSE: not staging project")
        return 2
    st, rows = http(
        "DELETE",
        f"{URL}/rest/v1/live_market_chat_messages?channel=eq.acceptance_test",
    )
    print("del_acceptance_test", st, "n", len(rows) if isinstance(rows, list) else rows)
    st, rows = http(
        "DELETE",
        f"{URL}/rest/v1/live_market_chat_messages?body=like.*ACCEPTANCE_MUST_NOT_LAND*",
    )
    print("del_accidental_marker", st, "n", len(rows) if isinstance(rows, list) else rows)
    st, users = http("GET", f"{URL}/auth/v1/admin/users?page=1&per_page=100")
    ulist = (users.get("users") if isinstance(users, dict) else users) or []
    leftover = [
        u
        for u in ulist
        if str(u.get("email", "")).startswith(("qf.chat.", "qf-chat-accept", "qf.chat.final"))
    ]
    print("leftover_auth", len(leftover))
    for u in leftover:
        st, _ = http("DELETE", f"{URL}/auth/v1/admin/users/{u['id']}")
        print("deleted", str(u.get("email", "")).split("@")[0], st)
    st, app = http(
        "GET",
        f"{URL}/rest/v1/users?or=(email.like.qf.chat.*,email.like.qf-chat-accept*)&select=id,email",
    )
    if isinstance(app, list):
        for row in app:
            http("DELETE", f"{URL}/rest/v1/users?id=eq.{row['id']}")
        print("deleted_app_users", len(app))
    print("cleanup_done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
