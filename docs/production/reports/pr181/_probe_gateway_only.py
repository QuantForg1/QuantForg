"""PR #181 gateway-only broker probe (no API owner token required)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PR180_UTC = datetime(2026, 11, 6, 9, 51, tzinfo=UTC)


def _load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def _token() -> str:
    return (os.environ.get("MT5_GATEWAY_TOKEN") or "").strip()


def _get(path: str, token: str) -> object:
    gw = (os.environ.get("MT5_GATEWAY_BASE_URL") or "https://gateway.quantforg.com").rstrip(
        "/"
    )
    req = urllib.request.Request(
        f"{gw}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-PR181/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {
            "error": exc.code,
            "path": path,
            "body": exc.read().decode("utf-8", errors="replace")[:400],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "path": path, "detail": str(exc)[:200]}


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def _parse_ts(raw: object) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            val = float(raw)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=UTC)
        except Exception:
            return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.replace(".", "", 1).isdigit():
            val = float(text)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=UTC)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def summarize_deals(raw: object) -> dict:
    items: list = []
    if isinstance(raw, dict):
        if raw.get("error"):
            return {"error": raw}
        items = raw.get("items") or raw.get("deals") or []
    elif isinstance(raw, list):
        items = raw
    if not isinstance(items, list):
        return {"unexpected": type(raw).__name__}

    by_pos: dict[int, list] = defaultdict(list)
    for deal in items:
        if not isinstance(deal, dict):
            continue
        action = str(deal.get("action") or deal.get("type") or "").upper()
        if "BALANCE" in action or "CREDIT" in action:
            continue
        symbol = str(deal.get("symbol") or "")
        if symbol and "XAU" not in symbol.upper() and "GOLD" not in symbol.upper():
            # Keep empty-symbol rows attached to gold positions via position_id later
            if symbol:
                continue
        pid = int(deal.get("position_id") or deal.get("position") or 0)
        row = {
            "ticket": deal.get("ticket") or deal.get("deal"),
            "position_id": pid,
            "symbol": symbol,
            "side": deal.get("type") or deal.get("action") or deal.get("side"),
            "entry": deal.get("entry") or deal.get("entry_type"),
            "price": deal.get("price"),
            "profit": deal.get("profit"),
            "commission": deal.get("commission"),
            "swap": deal.get("swap"),
            "volume": deal.get("volume"),
            "time": deal.get("time") or deal.get("time_msc") or deal.get("time_done"),
            "comment": str(deal.get("comment") or "")[:100],
            "magic": deal.get("magic"),
        }
        if pid > 0:
            by_pos[pid].append(row)

    closed = []
    for pid, rows in by_pos.items():
        # Prefer positions that touched XAU at least once
        syms = {str(r.get("symbol") or "") for r in rows}
        if syms and not any("XAU" in s.upper() or "GOLD" in s.upper() or s == "" for s in syms):
            continue
        if not any("XAU" in s.upper() or "GOLD" in s.upper() for s in syms):
            # all empty symbols — keep if comment looks like ite/scalp
            comments = " ".join(str(r.get("comment") or "") for r in rows).lower()
            if "ite" not in comments and "scalp" not in comments and "m1" not in comments:
                continue
        profits = sum((_d(r.get("profit")) for r in rows), Decimal("0"))
        commissions = sum((_d(r.get("commission")) for r in rows), Decimal("0"))
        swaps = sum((_d(r.get("swap")) for r in rows), Decimal("0"))
        times = [t for t in (_parse_ts(r.get("time")) for r in rows) if t]
        first = min(times) if times else None
        last = max(times) if times else None
        entries = [r for r in rows if str(r.get("entry") or "").upper() in {"0", "IN", "ENTRY", "DEAL_ENTRY_IN"}]
        exits = [r for r in rows if str(r.get("entry") or "").upper() in {"1", "OUT", "EXIT", "DEAL_ENTRY_OUT"}]
        open_px = entries[0].get("price") if entries else None
        close_px = exits[-1].get("price") if exits else None
        side = None
        if entries:
            side = entries[0].get("side")
        net = profits + commissions + swaps
        closed.append(
            {
                "position_id": pid,
                "deal_count": len(rows),
                "side": side,
                "open_price": open_px,
                "close_price": close_px,
                "net_pnl": float(net),
                "gross_profit": float(profits),
                "commission": float(commissions),
                "swap": float(swaps),
                "first_deal_at": first.isoformat() if first else None,
                "last_deal_at": last.isoformat() if last else None,
                "post_pr180": bool(last and last >= PR180_UTC),
                "comments": sorted({str(r.get("comment") or "") for r in rows if r.get("comment")}),
                "magic": sorted({r.get("magic") for r in rows if r.get("magic") is not None}),
                "looks_reversal_close": any(
                    "revers" in str(c).lower() or "structure" in str(c).lower() or "emerg" in str(c).lower()
                    for c in (r.get("comment") for r in rows)
                ),
            }
        )

    post = [c for c in closed if c.get("post_pr180")]
    wins = [c for c in post if c["net_pnl"] > 0]
    losses = [c for c in post if c["net_pnl"] < 0]
    flat = [c for c in post if c["net_pnl"] == 0]
    gross_win = sum(c["net_pnl"] for c in wins)
    gross_loss = abs(sum(c["net_pnl"] for c in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    return {
        "positions_reconstructed": len(closed),
        "post_pr180_count": len(post),
        "pre_pr180_count": len(closed) - len(post),
        "post_pr180_net_sum": round(sum(c["net_pnl"] for c in post), 4),
        "post_pr180_wins": len(wins),
        "post_pr180_losses": len(losses),
        "post_pr180_flat": len(flat),
        "post_pr180_win_rate": (len(wins) / len(post)) if post else None,
        "post_pr180_avg_win": (sum(c["net_pnl"] for c in wins) / len(wins)) if wins else None,
        "post_pr180_avg_loss": (sum(c["net_pnl"] for c in losses) / len(losses)) if losses else None,
        "post_pr180_profit_factor": pf,
        "post_pr180_expectancy": (sum(c["net_pnl"] for c in post) / len(post)) if post else None,
        "post_pr180_closes": sorted(post, key=lambda c: c.get("last_deal_at") or "", reverse=True),
        "recent_all": sorted(closed, key=lambda c: c.get("last_deal_at") or "", reverse=True)[:40],
    }


def main() -> None:
    _load_env()
    token = _token()
    assert token, "MT5_GATEWAY_TOKEN missing"
    account = _get("/account", token)
    positions = _get("/positions", token)
    deals7 = _get("/history/deals?days=7", token)
    deals2 = _get("/history/deals?days=2", token)
    deals1 = _get("/history/deals?days=1", token)

    login = None
    if isinstance(account, dict) and not account.get("error"):
        login = account.get("login") or (account.get("account_info") or {}).get("login")
        equity = account.get("equity") or (account.get("account_info") or {}).get("equity")
        balance = account.get("balance") or (account.get("account_info") or {}).get("balance")
        server = account.get("server") or (account.get("account_info") or {}).get("server")
        acct = {
            "login_last4": str(login)[-4:] if login else None,
            "login_full_for_split_only": str(login) if login else None,
            "equity": equity,
            "balance": balance,
            "server": server,
            "trade_allowed": account.get("trade_allowed")
            or (account.get("account_info") or {}).get("trade_allowed"),
        }
    else:
        acct = {"error": account}

    pos_items = []
    if isinstance(positions, dict) and not positions.get("error"):
        pos_items = positions.get("items") or positions.get("positions") or []
    elif isinstance(positions, list):
        pos_items = positions
    open_pos = []
    for p in pos_items if isinstance(pos_items, list) else []:
        if not isinstance(p, dict):
            continue
        open_pos.append(
            {
                "ticket": p.get("ticket") or p.get("position_id"),
                "symbol": p.get("symbol"),
                "side": p.get("type") or p.get("side"),
                "volume": p.get("volume"),
                "price_open": p.get("price_open") or p.get("open_price"),
                "sl": p.get("sl"),
                "tp": p.get("tp"),
                "profit": p.get("profit"),
                "magic": p.get("magic"),
                "comment": str(p.get("comment") or "")[:80],
                "has_sl": bool(p.get("sl")) and float(p.get("sl") or 0) != 0,
            }
        )

    payload = {
        "probed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "pr180_cutoff_utc": PR180_UTC.isoformat().replace("+00:00", "Z"),
        "account": {k: v for k, v in acct.items() if k != "login_full_for_split_only"},
        "account_login": acct.get("login_full_for_split_only"),
        "open_positions": {"count": len(open_pos), "positions": open_pos},
        "deals_1d": summarize_deals(deals1),
        "deals_2d": summarize_deals(deals2),
        "deals_7d": summarize_deals(deals7),
        "auth_note": "API owner endpoints not probed — SUPABASE_* empty in local .env",
    }
    path = OUT / "gateway_broker_evidence.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(path)
    print(
        json.dumps(
            {
                "account": payload["account"],
                "open": payload["open_positions"],
                "post_1d": {
                    k: payload["deals_1d"].get(k)
                    for k in (
                        "post_pr180_count",
                        "post_pr180_net_sum",
                        "post_pr180_wins",
                        "post_pr180_losses",
                        "post_pr180_profit_factor",
                        "post_pr180_expectancy",
                        "post_pr180_win_rate",
                    )
                },
                "post_2d": {
                    k: payload["deals_2d"].get(k)
                    for k in (
                        "post_pr180_count",
                        "post_pr180_net_sum",
                        "post_pr180_wins",
                        "post_pr180_losses",
                    )
                },
                "sample_post": (payload["deals_1d"].get("post_pr180_closes") or [])[:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
