"""Fetch broker deals/orders/positions via gateway for P&L baseline."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def _token() -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("MT5_GATEWAY_TOKEN="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no token")


def _get(path: str, token: str) -> object:
    req = urllib.request.Request(
        f"https://gateway.quantforg.com{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-LossAudit/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return {"error": exc.code, "body": body, "path": path}


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def main() -> None:
    token = _token()
    account = _get("/account", token)
    positions = _get("/positions", token)
    deals30 = _get("/history/deals?days=30", token)
    deals7 = _get("/history/deals?days=7", token)
    orders = _get("/history/orders?days=7", token)

    out: dict = {
        "account": account,
        "positions": positions,
        "deals_30_raw_type": type(deals30).__name__,
        "deals_7_raw_type": type(deals7).__name__,
        "orders_raw_type": type(orders).__name__,
    }

    for label, raw in (("deals_30", deals30), ("deals_7", deals7)):
        if isinstance(raw, dict) and raw.get("error"):
            out[label] = raw
            continue
        items = []
        if isinstance(raw, dict):
            items = raw.get("items") or raw.get("deals") or []
        elif isinstance(raw, list):
            items = raw
        out[f"{label}_count"] = len(items) if isinstance(items, list) else None
        if not isinstance(items, list):
            out[label] = {"unexpected": str(type(raw))}
            continue

        balance_deals = []
        trade_deals = []
        by_pos: dict[int, list] = defaultdict(list)
        for d in items:
            if not isinstance(d, dict):
                continue
            dtype = str(d.get("deal_type") or d.get("type") or "").lower()
            sym = str(d.get("symbol") or "").upper()
            comment = str(d.get("comment") or "")
            if dtype in {"balance", "credit"} or sym in {"", "BALANCE"} and (
                "deposit" in comment.lower() or dtype in {"balance", "credit"}
            ):
                balance_deals.append(d)
                continue
            if sym and sym != "BALANCE":
                trade_deals.append(d)
                pid = int(d.get("position_id") or d.get("position") or 0)
                if pid:
                    by_pos[pid].append(d)

        # Reconstruct closed positions: entry+exit deals
        closed = []
        for pid, rows in by_pos.items():
            rows_sorted = sorted(rows, key=lambda r: str(r.get("time") or ""))
            profit = sum((_d(r.get("profit")) for r in rows_sorted), Decimal("0"))
            commission = sum(
                (_d(r.get("commission")) for r in rows_sorted), Decimal("0")
            )
            swap = sum((_d(r.get("swap")) for r in rows_sorted), Decimal("0"))
            net = profit + commission + swap
            entries = [
                r
                for r in rows_sorted
                if str(r.get("entry") or r.get("entry_type") or "").lower()
                in {"in", "0", "deal_entry_in", ""}
                or str(r.get("deal_type") or "").lower() in {"buy", "sell"}
            ]
            # Prefer explicit entry/exit if present
            entry_rows = [
                r
                for r in rows_sorted
                if "in" == str(r.get("entry") or "").lower()
                or str(r.get("entry_type") or "").lower() in {"in", "deal_entry_in"}
            ]
            exit_rows = [
                r
                for r in rows_sorted
                if "out" == str(r.get("entry") or "").lower()
                or str(r.get("entry_type") or "").lower() in {"out", "deal_entry_out"}
            ]
            closed.append(
                {
                    "position_id": pid,
                    "symbol": rows_sorted[-1].get("symbol"),
                    "magic": rows_sorted[-1].get("magic"),
                    "comment": rows_sorted[-1].get("comment"),
                    "deal_count": len(rows_sorted),
                    "profit": str(profit),
                    "commission": str(commission),
                    "swap": str(swap),
                    "net": str(net),
                    "first_time": rows_sorted[0].get("time"),
                    "last_time": rows_sorted[-1].get("time"),
                    "entry_prices": [r.get("price") for r in (entry_rows or rows_sorted[:1])],
                    "exit_prices": [r.get("price") for r in (exit_rows or rows_sorted[-1:])],
                    "sides": [r.get("side") or r.get("type") for r in rows_sorted],
                    "volumes": [r.get("volume") for r in rows_sorted],
                }
            )

        nets = [_d(c["net"]) for c in closed]
        wins = [n for n in nets if n > 0]
        losses = [n for n in nets if n < 0]
        gross_win = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        metrics = {
            "n_positions": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(nets) - len(wins) - len(losses),
            "win_rate": float(len(wins) / len(nets) * 100) if nets else None,
            "gross_profit": str(gross_win),
            "gross_loss": str(gross_loss),
            "net": str(sum(nets, Decimal("0"))),
            "profit_factor": (
                str((gross_win / gross_loss).quantize(Decimal("0.0001")))
                if gross_loss > 0
                else None
            ),
            "avg_win": str((sum(wins, Decimal("0")) / len(wins)).quantize(Decimal("0.01")))
            if wins
            else None,
            "avg_loss": str((sum(losses, Decimal("0")) / len(losses)).quantize(Decimal("0.01")))
            if losses
            else None,
            "expectancy": (
                str((sum(nets, Decimal("0")) / len(nets)).quantize(Decimal("0.01")))
                if nets
                else None
            ),
            "total_commission": str(
                sum((_d(c["commission"]) for c in closed), Decimal("0"))
            ),
            "total_swap": str(sum((_d(c["swap"]) for c in closed), Decimal("0"))),
        }
        out[label] = {
            "balance_deals": balance_deals[-10:],
            "trade_deal_count": len(trade_deals),
            "closed_positions": sorted(
                closed, key=lambda c: str(c.get("last_time") or "")
            ),
            "metrics": metrics,
            "sample_deal_keys": list(trade_deals[0].keys()) if trade_deals else [],
            "sample_deal": trade_deals[0] if trade_deals else None,
        }

    out["orders"] = orders
    path = Path("docs/production/reports/profitability/loss_audit_broker_history.json")
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"account": account, "positions": positions}, indent=2, default=str)[:1500])
    for key in ("deals_7", "deals_30"):
        block = out.get(key)
        if isinstance(block, dict) and "metrics" in block:
            print(key, json.dumps(block["metrics"], indent=2))
            print("closed_n", len(block.get("closed_positions") or []))
            for c in (block.get("closed_positions") or [])[-12:]:
                print(
                    c["position_id"],
                    c.get("symbol"),
                    "net",
                    c["net"],
                    "comment",
                    c.get("comment"),
                    "magic",
                    c.get("magic"),
                    c.get("first_time"),
                    "->",
                    c.get("last_time"),
                )
        else:
            print(key, block)


if __name__ == "__main__":
    main()
