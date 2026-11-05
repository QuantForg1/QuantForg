"""Chronological BUY-cascade counterfactual on broker closes.

Rule (not curve-fit): after a losing BUY, skip later BUYs whose entry is still
at or below that failed entry (same decline) until price reclaims it or a
BUY wins. SELL path unchanged. DIRECTION_NONE is not involved.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _load() -> list[dict]:
    d = json.loads(
        Path(
            "docs/production/reports/profitability/loss_audit_broker_history.json"
        ).read_text(encoding="utf-8")
    )
    rows = []
    for c in d["deals_30"]["closed_positions"]:
        side = "BUY" if c["sides"][0] == 0 else "SELL"
        rows.append(
            {
                "side": side,
                "net": float(c["net"]),
                "entry": float(c["entry_prices"][0]),
                "ot": datetime.fromtimestamp(float(c["first_time"]), tz=timezone.utc),
            }
        )
    rows.sort(key=lambda r: r["ot"])
    return rows


def apply_rule(rows: list[dict]) -> dict:
    """Skip BUY while entry <= last losing BUY entry. Reset on reclaim or BUY win."""
    anchor: float | None = None
    kept: list[dict] = []
    skipped: list[dict] = []
    for r in rows:
        if r["side"] != "BUY":
            kept.append(r)
            continue
        if anchor is not None and r["entry"] <= anchor:
            skipped.append(r)
            continue
        kept.append(r)
        if r["net"] < 0:
            anchor = r["entry"]
        else:
            anchor = None
    return {"kept": kept, "skipped": skipped}


def metrics(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "net": 0.0, "wr": None, "exp": None, "pf": None, "mdd": 0.0}
    nets = [r["net"] for r in rows]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    eq = peak = 0.0
    mdd = 0.0
    for x in nets:
        eq += x
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    n = len(nets)
    return {
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "net": round(sum(nets), 2),
        "wr": round(100 * len(wins) / n, 1),
        "exp": round(sum(nets) / n, 3),
        "pf": round(gp / gl, 3) if gl else None,
        "mdd": round(mdd, 2),
        "buy_n": sum(1 for r in rows if r["side"] == "BUY"),
        "buy_net": round(sum(r["net"] for r in rows if r["side"] == "BUY"), 2),
        "sell_n": sum(1 for r in rows if r["side"] == "SELL"),
        "sell_net": round(sum(r["net"] for r in rows if r["side"] == "SELL"), 2),
    }


def main() -> None:
    rows = _load()
    base = metrics(rows)
    sim = apply_rule(rows)
    after = metrics(sim["kept"])
    cut = datetime(2026, 11, 5, tzinfo=timezone.utc)
    early = [r for r in rows if r["ot"] < cut]
    late = [r for r in rows if r["ot"] >= cut]
    # Rule parameters fixed a priori; OOS is Nov 5 only.
    oos = apply_rule(late)
    print("BASE", base)
    print("AFTER", after)
    print("SKIPPED", len(sim["skipped"]), "net", round(sum(r["net"] for r in sim["skipped"]), 2))
    print("skipped wins", sum(1 for r in sim["skipped"] if r["net"] > 0))
    print("OOS_BASE", metrics(late))
    print("OOS_AFTER", metrics(oos["kept"]))
    print("OOS_SKIP", len(oos["skipped"]), round(sum(r["net"] for r in oos["skipped"]), 2))
    print("IS_BASE", metrics(early))
    print("IS_AFTER", metrics(apply_rule(early)["kept"]))
    # NY buys only
    def ny(r: dict) -> bool:
        return r["side"] == "BUY" and 16 <= r["ot"].hour < 21

    ny_rows = [r for r in rows if ny(r)]
    print("NY_BUY_BASE", metrics(ny_rows))
    print("NY_BUY_AFTER", metrics([r for r in sim["kept"] if ny(r)]))


if __name__ == "__main__":
    main()
