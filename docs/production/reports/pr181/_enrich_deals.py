"""Enrich post-PR180 closes with entry/exit side and planned-risk comparison."""

from __future__ import annotations

import json
import os
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


def _get(path: str, token: str) -> object:
    req = urllib.request.Request(
        f"https://gateway.quantforg.com{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-PR181/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def _ts(raw: object) -> datetime | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)) or str(raw).replace(".", "", 1).isdigit():
            val = float(raw)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=UTC)
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _side_token(raw: object) -> str:
    t = str(raw or "").upper()
    if t in {"0", "BUY", "DEAL_TYPE_BUY", "BUY_ORDER"}:
        return "BUY"
    if t in {"1", "SELL", "DEAL_TYPE_SELL", "SELL_ORDER"}:
        return "SELL"
    return t or "UNKNOWN"


def _entry_kind(raw: object) -> str:
    t = str(raw or "").upper()
    if t in {"0", "IN", "DEAL_ENTRY_IN", "ENTRY"}:
        return "IN"
    if t in {"1", "OUT", "DEAL_ENTRY_OUT", "EXIT"}:
        return "OUT"
    if t in {"2", "INOUT", "DEAL_ENTRY_INOUT"}:
        return "INOUT"
    if t in {"3", "OUT_BY", "DEAL_ENTRY_OUT_BY"}:
        return "OUT"
    return t or "UNKNOWN"


def main() -> None:
    _load_env()
    token = (os.environ.get("MT5_GATEWAY_TOKEN") or "").strip()
    raw = _get("/history/deals?days=2", token)
    items = []
    if isinstance(raw, dict):
        items = raw.get("items") or raw.get("deals") or []
    elif isinstance(raw, list):
        items = raw

    by_pos: dict[int, list] = defaultdict(list)
    for deal in items:
        if not isinstance(deal, dict):
            continue
        symbol = str(deal.get("symbol") or "")
        if symbol and "XAU" not in symbol.upper() and "GOLD" not in symbol.upper():
            continue
        pid = int(deal.get("position_id") or deal.get("position") or 0)
        if pid <= 0:
            continue
        by_pos[pid].append(deal)

    rows = []
    for pid, deals in by_pos.items():
        deals_sorted = sorted(deals, key=lambda d: _ts(d.get("time") or d.get("time_msc")) or datetime.min.replace(tzinfo=UTC))
        times = [_ts(d.get("time") or d.get("time_msc")) for d in deals_sorted]
        times_ok = [t for t in times if t]
        last = max(times_ok) if times_ok else None
        if not last or last < PR180_UTC:
            continue
        ins = [d for d in deals_sorted if _entry_kind(d.get("entry") or d.get("entry_type")) == "IN"]
        outs = [d for d in deals_sorted if _entry_kind(d.get("entry") or d.get("entry_type")) == "OUT"]
        entry = ins[0] if ins else deals_sorted[0]
        exit_d = outs[-1] if outs else deals_sorted[-1]
        entry_side = _side_token(entry.get("type") or entry.get("action") or entry.get("side"))
        # For MT5, exit deal type is opposite of position side
        position_side = entry_side
        open_px = _d(entry.get("price"))
        close_px = _d(exit_d.get("price"))
        net = sum((_d(d.get("profit")) + _d(d.get("commission")) + _d(d.get("swap")) for d in deals_sorted), Decimal("0"))
        comments = [str(d.get("comment") or "") for d in deals_sorted]
        sl_close = any(c.lower().startswith("[sl") or "[sl " in c.lower() for c in comments)
        vol = _d(entry.get("volume"))
        # Approximate risk from SL comment if present
        sl_px = None
        for c in comments:
            if "[sl" in c.lower():
                try:
                    sl_px = Decimal(c.split("sl", 1)[1].strip(" []"))
                except Exception:
                    sl_px = None
        planned_risk = None
        if sl_px is not None and open_px > 0 and vol > 0:
            # XAUUSD contract size typically 100
            move = abs(open_px - sl_px)
            planned_risk = move * vol * Decimal("100")
        hold_s = None
        first = min(times_ok) if times_ok else None
        if first and last:
            hold_s = (last - first).total_seconds()
        rows.append(
            {
                "position_id": pid,
                "side": position_side,
                "volume": str(vol),
                "open_price": str(open_px),
                "close_price": str(close_px),
                "sl_from_comment": str(sl_px) if sl_px is not None else None,
                "approx_planned_risk_usd": str(planned_risk) if planned_risk is not None else None,
                "net_pnl": float(net),
                "loss_vs_planned_ratio": (
                    float(abs(net) / planned_risk) if planned_risk and planned_risk > 0 else None
                ),
                "opened_at": first.isoformat() if first else None,
                "closed_at": last.isoformat() if last else None,
                "hold_seconds": hold_s,
                "sl_broker_close": sl_close,
                "comments": comments,
                "magic": sorted({d.get("magic") for d in deals_sorted if d.get("magic") is not None}),
                "deal_dump": [
                    {
                        "ticket": d.get("ticket") or d.get("deal"),
                        "entry": d.get("entry") or d.get("entry_type"),
                        "type": d.get("type") or d.get("action"),
                        "price": d.get("price"),
                        "profit": d.get("profit"),
                        "commission": d.get("commission"),
                        "volume": d.get("volume"),
                        "time": d.get("time") or d.get("time_msc"),
                        "comment": d.get("comment"),
                    }
                    for d in deals_sorted
                ],
            }
        )

    rows = sorted(rows, key=lambda r: r.get("closed_at") or "")
    wins = [r for r in rows if r["net_pnl"] > 0]
    losses = [r for r in rows if r["net_pnl"] < 0]
    summary = {
        "count": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "net_sum": round(sum(r["net_pnl"] for r in rows), 4),
        "avg_loss": (sum(r["net_pnl"] for r in losses) / len(losses)) if losses else None,
        "avg_hold_seconds": (
            sum(r["hold_seconds"] or 0 for r in rows) / len(rows) if rows else None
        ),
        "all_sl_closes": all(r["sl_broker_close"] for r in rows) if rows else None,
        "sides": {
            "BUY": sum(1 for r in rows if r["side"] == "BUY"),
            "SELL": sum(1 for r in rows if r["side"] == "SELL"),
            "OTHER": sum(1 for r in rows if r["side"] not in {"BUY", "SELL"}),
        },
        "max_loss": min((r["net_pnl"] for r in rows), default=None),
        "consecutive_losses": len(losses),
        "positions": rows,
    }
    path = OUT / "post180_enriched_closes.json"
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(path)
    print(json.dumps({k: summary[k] for k in summary if k != "positions"}, indent=2))
    for r in rows:
        print(
            f"pid={r['position_id']} side={r['side']} net={r['net_pnl']} "
            f"hold={r['hold_seconds']}s planned={r['approx_planned_risk_usd']} "
            f"ratio={r['loss_vs_planned_ratio']} sl={r['sl_broker_close']}"
        )


if __name__ == "__main__":
    main()
