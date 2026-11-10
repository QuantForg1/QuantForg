"""Production Live Market smoke (no secrets printed)."""

from __future__ import annotations

import json
import urllib.request


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def main() -> int:
    st, status = get(
        "https://quantforg-production.up.railway.app/api/v1/public/market/status"
    )
    print(
        "market",
        st,
        status.get("ok"),
        status.get("as_of"),
        "twelvedata",
        status.get("twelvedata_configured"),
    )
    st, chat = get(
        "https://quantforg-production.up.railway.app/api/v1/public/market/chat?channel=xauusd&limit=5"
    )
    print(
        "chat",
        st,
        {
            k: chat.get(k)
            for k in ("ok", "channel", "count", "auth_required_to_post")
        },
    )
    with urllib.request.urlopen(
        "https://quantforg-production.up.railway.app/health/ready", timeout=30
    ) as r:
        print("ready", r.status, r.read().decode()[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
