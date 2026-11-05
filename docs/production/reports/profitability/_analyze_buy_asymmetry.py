"""BUY/SELL geometry + expectancy from broker history (authoritative)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

CS = 100.0
LOT = 0.01


def main() -> None:
    d = json.loads(
        Path(
            "docs/production/reports/profitability/loss_audit_broker_history.json"
        ).read_text(encoding="utf-8")
    )
    closes = d["deals_30"]["closed_positions"]

    def parse_t(c: dict, key: str) -> datetime:
        return datetime.fromtimestamp(float(c[key]), tz=timezone.utc)

    def side_of(c: dict) -> str:
        return "BUY" if c["sides"][0] == 0 else "SELL"

    def session_utc(t: datetime) -> str:
        h = t.hour
        if 0 <= h < 7:
            return "asia"
        if 7 <= h < 12:
            return "london"
        if 12 <= h < 16:
            return "london_ny_overlap"
        if 16 <= h < 21:
            return "ny"
        return "late_ny_asia"

    rows: list[dict] = []
    for c in closes:
        side = side_of(c)
        entry = float(c["entry_prices"][0])
        exitp = float(c["exit_prices"][0])
        net = float(c["net"])
        ot, ct = parse_t(c, "first_time"), parse_t(c, "last_time")
        hold = (ct - ot).total_seconds()
        cm = c.get("comment") or ""
        is_tp = "[tp" in cm.lower()
        is_sl = "[sl" in cm.lower()
        m = re.search(r"\[(sl|tp)\s+([0-9.]+)\]", cm, re.I)
        level = float(m.group(2)) if m else None
        planned = abs(level - entry) if level is not None else None
        rows.append(
            {
                "side": side,
                "net": net,
                "entry": entry,
                "exit": exitp,
                "hold": hold,
                "session": session_utc(ot),
                "is_tp": is_tp,
                "is_sl": is_sl,
                "planned_dist": planned,
                "ot": ot,
                "ct": ct,
                "comment": cm,
                "pos": c["position_id"],
            }
        )

    def summarize(name: str, rs: list[dict]) -> None:
        print(f"=== {name} n={len(rs)} ===")
        if not rs:
            return
        wins = [r for r in rs if r["net"] > 0]
        losses = [r for r in rs if r["net"] < 0]
        print(
            "WR",
            round(100 * len(wins) / len(rs), 1),
            "net",
            round(sum(r["net"] for r in rs), 2),
        )
        print(
            "avgW",
            round(mean([r["net"] for r in wins]), 3) if wins else None,
            "avgL",
            round(mean([r["net"] for r in losses]), 3) if losses else None,
        )
        tp_d = [r["planned_dist"] for r in rs if r["is_tp"] and r["planned_dist"]]
        sl_d = [r["planned_dist"] for r in rs if r["is_sl"] and r["planned_dist"]]
        print(
            "avg_TP_dist",
            round(mean(tp_d), 3) if tp_d else None,
            "avg_SL_dist",
            round(mean(sl_d), 3) if sl_d else None,
        )
        if tp_d and sl_d and mean(sl_d) > 0:
            print("implied_RR_planned", round(mean(tp_d) / mean(sl_d), 3))
        print("avg_hold_s", round(mean([r["hold"] for r in rs]), 1))
        by: dict[str, list[float]] = defaultdict(list)
        for r in rs:
            by[r["session"]].append(r["net"])
        for s, vs in sorted(by.items(), key=lambda x: sum(x[1])):
            print(
                f"  sess {s}: n={len(vs)} net={round(sum(vs), 2)} "
                f"WR={round(100 * sum(1 for v in vs if v > 0) / len(vs), 1)}"
            )
        chron = sorted(rs, key=lambda r: r["ot"])
        declining = 0
        for i in range(1, len(chron)):
            if (
                chron[i]["entry"] < chron[i - 1]["entry"]
                and chron[i]["net"] < 0
                and chron[i - 1]["net"] < 0
            ):
                declining += 1
        print("consec_lower_entry_both_loss", declining)

    buys = [r for r in rows if r["side"] == "BUY"]
    sells = [r for r in rows if r["side"] == "SELL"]
    summarize("BUY", buys)
    summarize("SELL", sells)

    print("=== EXPECTANCY MATH (full sample) ===")
    avg_w = mean([r["net"] for r in rows if r["net"] > 0])
    avg_l = abs(mean([r["net"] for r in rows if r["net"] < 0]))
    wr = sum(1 for r in rows if r["net"] > 0) / len(rows)
    print("avg_w", round(avg_w, 3), "avg_l", round(avg_l, 3), "wr", round(wr, 3))
    print("breakeven_WR", round(avg_l / (avg_w + avg_l), 3))
    print("exp_at_obs", round(wr * avg_w - (1 - wr) * avg_l, 3))
    print("exp_if_avgL_eq_avgW", round(wr * avg_w - (1 - wr) * avg_w, 3))
    print("req_avgW_for_BE", round(avg_l * (1 - wr) / wr, 3))
    print("realized_RR_from_dollars", round(avg_w / avg_l, 3))

    # BUY SL vs TP dollar buckets
    print("=== BUY TP/SL buckets ===")
    btp = [r for r in buys if r["is_tp"]]
    bsl = [r for r in buys if r["is_sl"]]
    print(
        "BUY_TP",
        len(btp),
        "net",
        round(sum(r["net"] for r in btp), 2),
        "avg",
        round(mean([r["net"] for r in btp]), 3) if btp else None,
    )
    print(
        "BUY_SL",
        len(bsl),
        "net",
        round(sum(r["net"] for r in bsl), 2),
        "avg",
        round(mean([r["net"] for r in bsl]), 3) if bsl else None,
    )

    print("=== BUY DETAIL ===")
    for r in sorted(buys, key=lambda x: x["ot"]):
        tag = "TP" if r["is_tp"] else "SL"
        print(
            f"{r['ot'].strftime('%m-%d %H:%M')} entry={r['entry']:.3f} "
            f"exit={r['exit']:.3f} net={r['net']:+.2f} hold={int(r['hold'])}s "
            f"{r['session']} {tag} dist={r['planned_dist']}"
        )

    out = {
        "n": len(rows),
        "buy_n": len(buys),
        "sell_n": len(sells),
        "buy_net": round(sum(r["net"] for r in buys), 2),
        "sell_net": round(sum(r["net"] for r in sells), 2),
        "expectancy": {
            "avg_win": round(avg_w, 3),
            "avg_loss": round(avg_l, 3),
            "wr": round(wr, 4),
            "breakeven_wr": round(avg_l / (avg_w + avg_l), 4),
            "realized_rr": round(avg_w / avg_l, 4),
            "req_avg_win_for_be": round(avg_l * (1 - wr) / wr, 3),
        },
    }
    Path(
        "docs/production/reports/profitability/buy_asymmetry_analysis.json"
    ).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote buy_asymmetry_analysis.json")


if __name__ == "__main__":
    main()
