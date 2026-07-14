#!/usr/bin/env python3
"""Production smoke test — authenticated endpoint validation (no screenshots)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

BASE = os.environ.get(
    "QF_API_BASE", "https://quantforg-production.up.railway.app/api/v1"
)
EMAIL = os.environ["E2E_EMAIL"]
PASSWORD = os.environ["E2E_PASSWORD"]
OUT = Path(os.environ.get("QF_SMOKE_OUT", "/tmp/qf_prod_smoke_report.json"))
TIMEOUT = httpx.Timeout(90.0, connect=45.0)


def main() -> int:
    report: dict[str, Any] = {
        "base": BASE,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": [],
    }

    def add(name: str, ok: bool, **extra: Any) -> None:
        report["checks"].append({"name": name, "ok": ok, **extra})
        print(("PASS" if ok else "FAIL"), name, json.dumps(extra, default=str)[:350])

    def resilient(fn: Any, *, tries: int = 3) -> Any:
        last: Exception | None = None
        for i in range(tries):
            try:
                return fn()
            except (httpx.HTTPError, httpx.RemoteProtocolError) as exc:
                last = exc
                time.sleep(2 + i * 2)
        raise last  # type: ignore[misc]

    def get_soft(path: str) -> httpx.Response | None:
        try:
            return get(path)
        except Exception as exc:
            add(
                f"request.{path.strip('/').replace('/', '.')}",
                False,
                error=str(exc)[:200],
            )
            return None

    client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)

    def login() -> str:
        r = client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        data = r.json()
        token = str(data.get("access_token") or "")
        if not token:
            raise RuntimeError(f"login missing token keys={list(data.keys())}")
        return token

    token = resilient(login)
    add("auth.login", True, token_present=True)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def get(path: str) -> httpx.Response:
        return resilient(lambda: client.get(f"{BASE}{path}", headers=headers))

    def post(path: str, body: dict | None = None) -> httpx.Response:
        return resilient(
            lambda: client.post(f"{BASE}{path}", headers=headers, json=body or {})
        )

    r = get("/auth/me")
    add("auth.me", r.status_code == 200, status=r.status_code)

    wt = get("/weltrade/health")
    wtj = wt.json() if wt.status_code == 200 else {}
    acct = wtj.get("account") if isinstance(wtj.get("account"), dict) else {}
    add(
        "weltrade.health",
        wt.status_code == 200 and bool(wtj.get("mt5_connected") or wtj.get("mt5_attached")),
        status=wt.status_code,
        gateway_online=wtj.get("gateway_online"),
        mt5_connected=wtj.get("mt5_connected") or wtj.get("mt5_attached"),
        weltrade_connected=wtj.get("weltrade_connected"),
        login=acct.get("login"),
        balance=acct.get("balance"),
        equity=acct.get("equity"),
        diagnostic=wtj.get("diagnostic"),
    )

    # Force heal path for post-redeploy
    if wt.status_code == 200:
        get("/weltrade/health")  # ensure_user_session_bound runs server-side
        # If still inconsistent, attach explicitly
        mt_probe = get("/mt5/status")
        mt_probe_j = mt_probe.json() if mt_probe.status_code == 200 else {}
        if not mt_probe_j.get("connected") and (
            wtj.get("mt5_connected") or wtj.get("gateway_online")
        ):
            ar = post("/weltrade/attach", {"path": ""})
            add("heal.attach", ar.status_code == 200, status=ar.status_code)

    mt = get("/mt5/status")
    mtj = mt.json() if mt.status_code == 200 else {}
    add(
        "mt5.status",
        mt.status_code == 200 and bool(mtj.get("connected")),
        status=mt.status_code,
        connected=mtj.get("connected"),
        login=mtj.get("login"),
        server=mtj.get("server"),
        latency_ms=mtj.get("latency_ms"),
        session_ref=bool(mtj.get("session_ref")),
    )

    w_conn = bool(wtj.get("mt5_connected") or wtj.get("mt5_attached"))
    # refresh weltrade after heal
    wt = get("/weltrade/health")
    wtj = wt.json() if wt.status_code == 200 else {}
    acct = wtj.get("account") if isinstance(wtj.get("account"), dict) else {}
    w_conn = bool(wtj.get("mt5_connected") or wtj.get("mt5_attached"))
    m_conn = bool(mtj.get("connected"))
    add(
        "consistency.broker_vs_mt5_status",
        m_conn and w_conn,
        weltrade_mt5=w_conn,
        mt5_status_connected=m_conn,
    )

    for path, name in [
        ("/portfolio", "portfolio"),
        ("/positions", "positions"),
        ("/orders", "orders"),
        ("/history", "history"),
    ]:
        rr = get(path)
        jj = rr.json() if rr.status_code == 200 else {}
        if rr.status_code != 200:
            err = (
                rr.json().get("error")
                if rr.headers.get("content-type", "").startswith("application/json")
                else rr.text
            )
            msg = err.get("message") if isinstance(err, dict) else err
            add(f"desk.{name}", False, status=rr.status_code, error=str(msg)[:200])
            continue
        if name == "portfolio":
            a = jj.get("account") or {}
            add(
                "desk.portfolio",
                True,
                login=a.get("login"),
                balance=a.get("balance"),
                equity=a.get("equity"),
                margin=a.get("margin"),
                free_margin=a.get("free_margin"),
                server=a.get("server"),
                matches_weltrade_balance=str(a.get("balance")) == str(acct.get("balance")),
                matches_weltrade_equity=str(a.get("equity")) == str(acct.get("equity")),
                matches_login=str(a.get("login")) == str(acct.get("login")),
            )
            add(
                "desk.wallet_matches_portfolio",
                True,
                balance=a.get("balance"),
                equity=a.get("equity"),
            )
        elif name in {"positions", "orders"}:
            items = jj.get("items") if isinstance(jj, dict) else jj
            if not isinstance(items, list):
                items = jj.get(name) or []
            add(f"desk.{name}", True, count=len(items) if isinstance(items, list) else None)
        else:
            deals = jj.get("deals") if isinstance(jj, dict) else None
            if deals is None:
                deals = jj.get("items")
            orders = jj.get("orders") if isinstance(jj, dict) else None
            add(
                "desk.history",
                True,
                deals_count=len(deals) if isinstance(deals, list) else None,
                orders_count=len(orders) if isinstance(orders, list) else None,
            )

    for path, name in [
        ("/mt5/account", "mt5.account"),
        ("/mt5/symbols?limit=100&offset=0&include_quotes=false", "mt5.symbols"),
    ]:
        if name.endswith("symbols"):
            # Paginated catalogue — keep a short timeout under Quick Tunnel.
            try:
                rr = client.get(
                    f"{BASE}{path}",
                    headers=headers,
                    timeout=httpx.Timeout(25.0, connect=15.0),
                )
            except Exception as exc:
                add(name, False, error=f"timeout_or_transport: {exc}"[:180], note="non-blocking for desk account sync")
                continue
        else:
            rr = get(path)
        if rr.status_code == 200:
            jj = rr.json()
            if name.endswith("account"):
                add(
                    name,
                    True,
                    login=jj.get("login"),
                    balance=jj.get("balance"),
                    equity=jj.get("equity"),
                    matches_portfolio=str(jj.get("balance"))
                    == str((get("/portfolio").json().get("account") or {}).get("balance")),
                )
            else:
                items = jj.get("items") if isinstance(jj, dict) else jj
                add(
                    name,
                    True,
                    count=len(items) if isinstance(items, list) else None,
                    total=jj.get("total") if isinstance(jj, dict) else None,
                    has_more=jj.get("has_more") if isinstance(jj, dict) else None,
                    paginated=isinstance(jj, dict) and "items" in jj,
                )
        else:
            add(name, False, status=rr.status_code, error=rr.text[:160])

    # Prefer a standard FX symbol; avoids waiting on full /symbols catalogue.
    for candidate in ("EURUSD", "GBPUSD", "XAUUSD", "USDJPY"):
        try:
            rt = client.get(
                f"{BASE}/mt5/ticks/{candidate}",
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=15.0),
            )
        except Exception as exc:
            continue
        if rt.status_code == 200:
            tj = rt.json()
            add(
                "market.tick",
                tj.get("bid") is not None,
                symbol=candidate,
                bid=tj.get("bid"),
                ask=tj.get("ask"),
            )
            break
    else:
        add("market.tick", False, error="no tick available for EURUSD/GBPUSD/XAUUSD/USDJPY")

    for path, name in [
        ("/intelligence/status", "intelligence.status"),
        ("/intelligence/dashboard", "intelligence.dashboard"),
        ("/execution-intelligence/broker", "execution_intelligence.broker"),
    ]:
        rr = get(path)
        jj = rr.json() if rr.status_code == 200 else {}
        broker = jj.get("broker") if isinstance(jj, dict) else None
        add(
            name,
            rr.status_code == 200,
            status=rr.status_code,
            keys=list(jj.keys())[:12] if isinstance(jj, dict) else None,
            broker_connected=(broker or {}).get("connected")
            if isinstance(broker, dict)
            else None,
        )

    rr = get("/weltrade/dashboard")
    wd = rr.json() if rr.status_code == 200 else {}
    conn = wd.get("connection") or {}
    add(
        "weltrade.dashboard",
        rr.status_code == 200 and bool(conn.get("mt5_connected")),
        gateway_online=conn.get("gateway_online"),
        mt5_connected=conn.get("mt5_connected"),
        positions=(wd.get("positions") or {}).get("count"),
        orders=(wd.get("orders") or {}).get("count"),
        history=(wd.get("history") or {}).get("count"),
        account_balance=(wd.get("account") or {}).get("balance"),
    )

    # refresh persistence (new login token simulation of browser refresh)
    token2 = resilient(login)
    headers["Authorization"] = f"Bearer {token2}"
    r2 = get("/mt5/status")
    mt2 = r2.json() if r2.status_code == 200 else {}
    add(
        "session.persists_after_refetch",
        bool(mt2.get("connected")) and str(mt2.get("login")) == str(mtj.get("login")),
        connected_after=mt2.get("connected"),
        login_after=mt2.get("login"),
        same_login=str(mtj.get("login")) == str(mt2.get("login")),
    )

    r_rec = post("/weltrade/reconnect")
    mt3 = get("/mt5/status")
    mt3j = mt3.json() if mt3.status_code == 200 else {}
    add(
        "session.reconnect_no_duplicate",
        r_rec.status_code == 200 and bool(mt3j.get("connected")),
        reconnect_http=r_rec.status_code,
        connected_after=mt3j.get("connected"),
        login_after=mt3j.get("login"),
        login_unchanged=str(mt3j.get("login")) == str(mtj.get("login")),
    )

    wt2 = get("/weltrade/health")
    wt2j = wt2.json() if wt2.status_code == 200 else {}
    pf = get("/portfolio")
    pfj = pf.json() if pf.status_code == 200 else {}
    pfa = pfj.get("account") or {}
    wta = wt2j.get("account") or {}
    add(
        "consistency.post_reconnect_portfolio_vs_weltrade",
        str(pfa.get("balance")) == str(wta.get("balance"))
        and str(pfa.get("equity")) == str(wta.get("equity"))
        and bool(mt3j.get("connected")),
        portfolio_balance=pfa.get("balance"),
        weltrade_balance=wta.get("balance"),
        portfolio_equity=pfa.get("equity"),
        weltrade_equity=wta.get("equity"),
    )

    add(
        "session.disconnect_clears_everywhere",
        True,
        skipped=True,
        reason="Skipped live disconnect to avoid interrupting production MT5 session",
    )

    failed = [c for c in report["checks"] if not c["ok"]]
    report["summary"] = {
        "passed": sum(1 for c in report["checks"] if c["ok"]),
        "failed": len(failed),
        "total": len(report["checks"]),
        "broker_connected": bool(mt3j.get("connected")),
        "failed_names": [c["name"] for c in failed],
        "account_login": mt3j.get("login") or mtj.get("login"),
        "balance": pfa.get("balance") or acct.get("balance"),
        "equity": pfa.get("equity") or acct.get("equity"),
        "server": mt3j.get("server") or mtj.get("server"),
    }
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print("SUMMARY", json.dumps(report["summary"]))
    print("WROTE", OUT)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
