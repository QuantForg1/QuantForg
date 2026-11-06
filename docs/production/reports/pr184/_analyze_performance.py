"""PR #184 — account/period-separated broker performance analysis (read-only)."""

from __future__ import annotations

import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

# Deploy cutoffs (UTC) from PR lineage
PR180_UTC = datetime(2026, 11, 6, 9, 51, tzinfo=UTC)
PR182_UTC = datetime(2026, 11, 6, 11, 11, tzinfo=UTC)  # Railway sell-cascade restore window


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
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
            "User-Agent": "QuantForg-PR184/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
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
    return t or "UNKNOWN"


def _engine_from_comment(comment: str) -> str:
    c = (comment or "").lower()
    if c.startswith("m1:") or "m1:" in c:
        return "m1_micro"
    if c.startswith("ite:") or "ite:" in c:
        return "ite_primary"
    if "[sl" in c or "[tp" in c:
        return "exit_tag"
    return "unknown"


def _period(closed_at: datetime | None) -> str:
    if closed_at is None:
        return "unknown_time"
    if closed_at >= PR182_UTC:
        return "post_pr182"
    if closed_at >= PR180_UTC:
        return "post_pr180_pre_pr182"
    return "pre_pr180"


def pair_positions(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pos: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for deal in deals:
        try:
            pid = int(deal.get("position_id") or deal.get("position") or 0)
        except Exception:
            pid = 0
        if pid <= 0:
            continue
        sym = str(deal.get("symbol") or "").upper()
        if "XAU" not in sym and "GOLD" not in sym:
            continue
        by_pos[pid].append(deal)

    rows: list[dict[str, Any]] = []
    for pid, group in sorted(by_pos.items()):
        group_sorted = sorted(
            group,
            key=lambda d: _ts(d.get("time") or d.get("time_msc"))
            or datetime.min.replace(tzinfo=UTC),
        )
        ins = [
            d
            for d in group_sorted
            if _entry_kind(d.get("entry") or d.get("entry_type")) == "IN"
        ]
        outs = [
            d
            for d in group_sorted
            if _entry_kind(d.get("entry") or d.get("entry_type")) == "OUT"
        ]
        if not outs and not ins:
            # Gateway sometimes omits entry flags — chronological first/last.
            if len(group_sorted) < 2:
                continue
            ins = [group_sorted[0]]
            outs = [group_sorted[-1]]
        elif not outs:
            outs = [d for d in group_sorted if _d(d.get("profit")) != 0] or [
                group_sorted[-1]
            ]
            if not ins:
                ins = [group_sorted[0]]
        entry = ins[0] if ins else group_sorted[0]
        exit_d = outs[-1] if outs else group_sorted[-1]
        opened = _ts(entry.get("time") or entry.get("time_msc"))
        closed = _ts(exit_d.get("time") or exit_d.get("time_msc"))
        profit = sum((_d(d.get("profit")) for d in group_sorted), Decimal("0"))
        commission = sum((_d(d.get("commission")) for d in group_sorted), Decimal("0"))
        swap = sum((_d(d.get("swap")) for d in group_sorted), Decimal("0"))
        net = profit + commission + swap
        # Position side = entry deal type (MT5). ite:v1:S/H is scalp/hold, not side.
        side = _side_token(entry.get("type") or entry.get("action") or entry.get("side"))
        open_price = _d(entry.get("price"))
        close_price = _d(exit_d.get("price"))
        # When gateway omits entry type, infer from price move + net sign.
        if side not in {"BUY", "SELL"} and open_price > 0 and close_price > 0:
            move = close_price - open_price
            signed = profit + commission + swap
            if move != 0 and signed != 0:
                if (move > 0 and signed < 0) or (move < 0 and signed > 0):
                    side = "SELL"
                elif (move < 0 and signed < 0) or (move > 0 and signed > 0):
                    side = "BUY"
        comments = [str(d.get("comment") or "") for d in group_sorted if d.get("comment")]
        engines = {_engine_from_comment(c) for c in comments}
        engines.discard("exit_tag")
        engine = sorted(engines)[0] if engines else "unknown"
        sl = any("[sl" in c.lower() for c in comments)
        tp = any("[tp" in c.lower() for c in comments)
        reversal = any(
            tok in " ".join(comments).lower()
            for tok in ("reversal", "structure", "emergency", "choch", "bos")
        )
        volume = _d(entry.get("volume"))
        hold = None
        if opened and closed:
            hold = (closed - opened).total_seconds()
        mgmt = "unknown"
        joined = " ".join(comments).lower()
        if "ite:v1:s:" in joined:
            mgmt = "scalp"
        elif "ite:v1:h:" in joined:
            mgmt = "hold"
        rows.append(
            {
                "position_id": pid,
                "side": side,
                "management_profile": mgmt,
                "volume": str(volume),
                "open_price": str(open_price) if open_price is not None else None,
                "close_price": str(close_price) if close_price is not None else None,
                "net_pnl": float(net),
                "profit": float(profit),
                "commission": float(commission),
                "swap": float(swap),
                "opened_at": opened.isoformat() if opened else None,
                "closed_at": closed.isoformat() if closed else None,
                "hold_seconds": hold,
                "engine_tag": engine,
                "strategy_id": None,  # never invent five-pack IDs
                "sl_close": sl,
                "tp_close": tp,
                "looks_reversal_close": reversal,
                "period": _period(closed),
                "comments": comments,
                "magic": sorted(
                    {
                        int(d.get("magic"))
                        for d in group_sorted
                        if str(d.get("magic") or "").isdigit()
                    }
                ),
            }
        )
    return rows


def scorecard(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not rows:
        return {
            "label": label,
            "n": 0,
            "classification": "Insufficient data",
            "note": "no closed trades in bucket",
        }
    wins = [r for r in rows if r["net_pnl"] > 0]
    losses = [r for r in rows if r["net_pnl"] < 0]
    flats = [r for r in rows if r["net_pnl"] == 0]
    gross_profit = sum(r["net_pnl"] for r in wins)
    gross_loss = sum(r["net_pnl"] for r in losses)  # negative
    net = sum(r["net_pnl"] for r in rows)
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    win_rate = len(wins) / len(rows) if rows else 0.0
    pf = (gross_profit / abs(gross_loss)) if gross_loss < 0 else (math.inf if gross_profit > 0 else 0.0)
    expectancy = net / len(rows)
    # Break-even win rate after costs: BE = |avg_loss| / (avg_win + |avg_loss|)
    be = None
    if avg_win > 0 and avg_loss < 0:
        be = abs(avg_loss) / (avg_win + abs(avg_loss))
    # Max consecutive losses (chronological)
    ordered = sorted(rows, key=lambda r: r.get("closed_at") or "")
    max_cl = 0
    cur = 0
    for r in ordered:
        if r["net_pnl"] < 0:
            cur += 1
            max_cl = max(max_cl, cur)
        else:
            cur = 0
    # Equity curve drawdown (trade-by-trade, start 0)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in ordered:
        equity += r["net_pnl"]
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    by_side = {
        side: {
            "n": len([r for r in rows if r["side"] == side]),
            "net": sum(r["net_pnl"] for r in rows if r["side"] == side),
            "wins": len([r for r in rows if r["side"] == side and r["net_pnl"] > 0]),
            "losses": len([r for r in rows if r["side"] == side and r["net_pnl"] < 0]),
        }
        for side in ("BUY", "SELL", "UNKNOWN")
    }
    classification = "Insufficient data"
    if len(rows) < 20:
        if net > 0 and pf > 1.0:
            classification = "Promising but insufficient sample"
        elif net < 0:
            classification = "Negative expectancy (small sample — provisional)"
        else:
            classification = "Insufficient data"
    else:
        if expectancy > 0 and pf > 1.0:
            classification = "Demonstrated positive expectancy"
        elif expectancy < 0:
            classification = "Negative expectancy"
        else:
            classification = "Insufficient data"
    if all(r.get("strategy_id") is None for r in rows) and label.startswith("strategy:"):
        classification = "Unreliable attribution"

    return {
        "label": label,
        "n": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len(flats),
        "win_rate": round(win_rate, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "net_profit": round(net, 4),
        "profit_factor": (round(pf, 4) if math.isfinite(pf) else "inf"),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
        "breakeven_win_rate": round(be, 4) if be is not None else None,
        "max_consecutive_losses": max_cl,
        "max_drawdown_trade_curve": round(max_dd, 4),
        "sl_closes": sum(1 for r in rows if r["sl_close"]),
        "tp_closes": sum(1 for r in rows if r["tp_close"]),
        "reversal_like_closes": sum(1 for r in rows if r["looks_reversal_close"]),
        "by_side": by_side,
        "classification": classification,
    }


def main() -> None:
    _load_env()
    token = (os.environ.get("MT5_GATEWAY_TOKEN") or "").strip()
    if not token:
        raise SystemExit("MT5_GATEWAY_TOKEN missing")

    account = _get("/account", token)
    positions = _get("/positions", token)
    history = _get("/history/deals?days=30", token)

    deals: list[dict[str, Any]] = []
    if isinstance(history, dict):
        deals = list(history.get("items") or history.get("deals") or [])
    elif isinstance(history, list):
        deals = history

    login = None
    if isinstance(account, dict) and not account.get("error"):
        try:
            login = int(account.get("login") or 0) or None
        except Exception:
            login = None

    rows = pair_positions(deals)
    # Only current account — do not invent 12260878 rows from this gateway
    buckets = {
        "all_current_gateway_account": rows,
        "pre_pr180": [r for r in rows if r["period"] == "pre_pr180"],
        "post_pr180_pre_pr182": [r for r in rows if r["period"] == "post_pr180_pre_pr182"],
        "post_pr182": [r for r in rows if r["period"] == "post_pr182"],
        "engine:ite_primary": [r for r in rows if r["engine_tag"] == "ite_primary"],
        "engine:m1_micro": [r for r in rows if r["engine_tag"] == "m1_micro"],
        "engine:unknown": [r for r in rows if r["engine_tag"] == "unknown"],
        "side:BUY": [r for r in rows if r["side"] == "BUY"],
        "side:SELL": [r for r in rows if r["side"] == "SELL"],
    }

    cards = {name: scorecard(rs, name) for name, rs in buckets.items()}

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "broker_login": login,
        "account_snapshot": {
            "login": login,
            "balance": (account or {}).get("balance") if isinstance(account, dict) else None,
            "equity": (account or {}).get("equity") if isinstance(account, dict) else None,
            "server": (account or {}).get("server") if isinstance(account, dict) else None,
            "trade_allowed": (account or {}).get("trade_allowed")
            if isinstance(account, dict)
            else None,
        },
        "open_positions_count": (
            len(positions.get("items") or positions)
            if isinstance(positions, dict)
            else len(positions)
            if isinstance(positions, list)
            else None
        ),
        "deal_count_raw": len(deals),
        "closed_xau_positions": len(rows),
        "cutoffs": {
            "pr180_utc": PR180_UTC.isoformat(),
            "pr182_utc": PR182_UTC.isoformat(),
        },
        "scorecards": cards,
        "positions": rows,
        "account_12260878_note": (
            "Not present on current gateway session. Do not merge with 12479147. "
            "Historical 12260878 figures, if any, must come from preserved prior evidence only."
        ),
        "five_pack_attribution_note": (
            "Broker comments carry ite:/m1: engine tags only. Five-pack strategy_id is "
            "not recoverable from MT5 history — left null; classification uses engine_tag."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "performance_analysis.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"login": login, "n": len(rows), "cards": {k: cards[k]["classification"] for k in cards}, "path": str(out_path)}, indent=2))
    for key in (
        "all_current_gateway_account",
        "pre_pr180",
        "post_pr180_pre_pr182",
        "post_pr182",
        "side:BUY",
        "side:SELL",
        "engine:ite_primary",
        "engine:m1_micro",
    ):
        c = cards[key]
        print(
            f"{key}: n={c.get('n')} net={c.get('net_profit')} wr={c.get('win_rate')} "
            f"exp={c.get('expectancy')} be={c.get('breakeven_win_rate')} class={c.get('classification')}"
        )


if __name__ == "__main__":
    main()
