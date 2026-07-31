#!/usr/bin/env python3
"""Collect production Strategy Diagnostics cycles for rejection analysis.

Observation only — never mutates thresholds, risk, OMS, or MT5.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

API = os.environ.get(
    "QUANTFORG_API_BASE", "https://quantforg-production.up.railway.app/api/v1"
)
EMAIL = os.environ.get("E2E_EMAIL") or os.environ.get("QUANTFORG_OPS_EMAIL")
PASSWORD = os.environ.get("E2E_PASSWORD") or os.environ.get("QUANTFORG_OPS_PASSWORD")
TARGET = int(os.environ.get("COLLECT_TARGET", "1000"))
POLL_SEC = float(os.environ.get("COLLECT_POLL_SEC", "5"))
OUT = Path(
    os.environ.get(
        "COLLECT_OUT",
        "/opt/cursor/artifacts/ai-decision-rejection-analysis",
    )
)
STORE = Path(
    os.environ.get("COLLECT_STORE", "/tmp/ai-decision-collector/cycles_by_trace.json")
)
META = OUT / "collector_status.json"

FAMILY_MAP = {
    "mtf_not_aligned": "mtf_alignment",
    "quality_below_threshold": "ai_quality",
    "confidence_below_threshold": "confidence",
    "no_liquidity_context": "liquidity",
    "spread_too_wide": "spread",
    "session_blocked": "session",
    "market_window_closed": "session",
    "news_blackout": "news",
    "below_min_lot": "risk_sizing",
    "atr_elevated": "atr_volatility",
    "atr_too_low": "atr_volatility",
    "no_structure_event": "structure_pa",
    "no_smc_zone": "structure_pa",
    "no_active_order_block": "structure_pa",
    "no_open_fvg": "structure_pa",
}


def login() -> str:
    if not EMAIL or not PASSWORD:
        raise RuntimeError("Set E2E_EMAIL/E2E_PASSWORD (or QUANTFORG_OPS_*)")
    req = urllib.request.Request(
        f"{API}/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())["access_token"]


def fetch(token: str) -> dict:
    req = urllib.request.Request(
        f"{API}/ite/ops/strategy-diagnostics?limit=100",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _is_soft(text: str) -> bool:
    low = text.lower()
    return any(
        s in low
        for s in (
            "reject only above",
            "soft score",
            "soft-ok",
            "soft-weighted",
            "riskx=",
            "of price acceptable",
            "news protection disabled",
            "no reliable calendar",
            "m15 structure events",
            "latest bos",
            "active order blocks=",
            "open fvgs=",
        )
    )


def cycle_families(cycle: dict) -> set[str]:
    """Hard-reject families only (soft observations excluded from Pareto)."""
    rejection = cycle.get("rejection") or {}
    fams: set[str] = set()
    for code in rejection.get("all_codes") or []:
        c = str(code)
        if "AI quality gates rejected" in c:
            fams.add("ai_quality")
            continue
        fam = FAMILY_MAP.get(c)
        if fam:
            fams.add(fam)
    for reason in rejection.get("decision_reasons") or []:
        text = str(reason)
        if _is_soft(text):
            continue
        low = text.lower()
        if "mtf" in low or "not aligned" in low:
            fams.add("mtf_alignment")
        if "ai quality gates" in low or ("trade quality" in low and "below" in low):
            fams.add("ai_quality")
        if "confidence" in low and ("<" in low or "below" in low):
            fams.add("confidence")
        if "confluence" in low and ("below" in low or "<" in low):
            fams.add("confluence")
        if "liquidity" in low and ("insufficient" in low or "score" in low or "no_liquidity" in low):
            fams.add("liquidity")
        if "spread" in low and ("reject" in low or "too wide" in low):
            fams.add("spread")
        if ("atr" in low or "volatil" in low) and (
            "too" in low or "invalid" in low or "compress" in low or "reject" in low
        ):
            fams.add("atr_volatility")
        if "session" in low and ("blocked" in low or "closed" in low or "weekend" in low):
            fams.add("session")
        if "news" in low and ("blackout" in low or "blocked" in low):
            fams.add("news")
        if "momentum" in low and ("<" in low or "no confirmation" in low):
            fams.add("momentum")
        if "weak structure" in low or "structure score" in low or "pa confluence" in low:
            fams.add("structure_pa")
        if "below_min_lot" in low or "broker min" in low:
            fams.add("risk_sizing")
    return fams


def summarize(cycles: dict[str, dict]) -> dict:
    prim: Counter[str] = Counter()
    family_hits: Counter[str] = Counter()
    combos: Counter[str] = Counter()
    quals: list[float] = []
    confs: list[float] = []
    mtfs: list[float] = []
    spreads: list[float] = []
    atrs: list[float] = []
    atr_pcts: list[float] = []

    for cycle in cycles.values():
        rejection = cycle.get("rejection") or {}
        primary = str(rejection.get("primary") or "unknown")
        prim[primary] += 1
        fams = cycle_families(cycle)
        for fam in fams:
            family_hits[fam] += 1
        combos["+".join(sorted(fams)) if fams else "NONE"] += 1

        q = (cycle.get("quality") or {}).get("score")
        if q is not None:
            quals.append(float(q))
        cf = (cycle.get("confluence") or {}).get("total")
        if cf is not None:
            confs.append(float(cf))
        mtf = (cycle.get("trend") or {}).get("score")
        if mtf is not None:
            mtfs.append(float(mtf))
        atr = (cycle.get("sizing") or {}).get("atr") or cycle.get("atr")
        if atr is not None:
            atrs.append(float(atr))
        for reason in rejection.get("decision_reasons") or []:
            text = str(reason)
            m1 = re.search(r"Spread\s+([\d.]+)", text, re.I)
            if m1:
                spreads.append(float(m1.group(1)))
            m2 = re.search(r"ATR\s+([\d.]+)\s*%", text, re.I)
            if m2:
                atr_pcts.append(float(m2.group(1)))

    n = len(cycles)

    def avg(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 4) if vals else None

    pareto = []
    running = 0
    for code, count in prim.most_common():
        running += count
        pareto.append(
            {
                "code": code,
                "count": count,
                "share_pct": round(100.0 * count / n, 2) if n else 0.0,
                "cumulative_share_pct": round(100.0 * running / n, 2) if n else 0.0,
            }
        )

    return {
        "n": n,
        "target": TARGET,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "avg_quality": avg(quals),
        "avg_confidence": avg(confs),
        "avg_mtf": avg(mtfs),
        "avg_spread": avg(spreads),
        "avg_atr": avg(atrs),
        "avg_atr_pct": avg(atr_pcts),
        "rejection_frequency_by_primary_code": pareto,
        "rejection_frequency_by_filter_family": [
            {
                "family": fam,
                "count": count,
                "share_of_cycles_pct": round(100.0 * count / n, 2) if n else 0.0,
            }
            for fam, count in family_hits.most_common()
        ],
        "rejection_combinations": [
            {
                "combination": combo,
                "count": count,
                "share_pct": round(100.0 * count / n, 2) if n else 0.0,
            }
            for combo, count in combos.most_common(25)
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    cycles: dict[str, dict] = {}
    if STORE.exists():
        cycles = json.loads(STORE.read_text())
    token = login()
    token_at = time.time()
    print(f"collector_start n={len(cycles)}", flush=True)
    while len(cycles) < TARGET:
        try:
            if time.time() - token_at > 1500:
                token = login()
                token_at = time.time()
            payload = fetch(token)
            # Reload disk store each poll so a parallel log miner can co-append.
            if STORE.exists():
                try:
                    cycles.update(json.loads(STORE.read_text()))
                except json.JSONDecodeError:
                    pass
            for cycle in payload.get("cycles") or []:
                tid = str(cycle.get("trace_id") or cycle.get("signal_id") or "")
                if not tid:
                    q = (cycle.get("quality") or {}).get("score")
                    m = (cycle.get("trend") or {}).get("score")
                    tid = f"{cycle.get('recorded_at')}|{q}|{m}"
                # Prefer richer API diagnostics records over log-mined stubs.
                prev = cycles.get(tid)
                if prev is None or cycle.get("confluence") or cycle.get("explain"):
                    cycles[tid] = cycle
            STORE.write_text(json.dumps(cycles))
            status = summarize(cycles)
            META.write_text(json.dumps(status, indent=2))
            print(
                json.dumps(
                    {
                        "n": status["n"],
                        "avg_q": status["avg_quality"],
                        "avg_conf": status["avg_confidence"],
                        "avg_mtf": status["avg_mtf"],
                        "top": (status["rejection_frequency_by_primary_code"] or [])[:3],
                    }
                ),
                flush=True,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"err {type(exc).__name__}: {exc}", flush=True)
            try:
                token = login()
                token_at = time.time()
            except Exception as relogin_exc:  # noqa: BLE001
                print(f"relogin_fail {relogin_exc}", flush=True)
        time.sleep(POLL_SEC)

    status = summarize(cycles)
    META.write_text(json.dumps(status, indent=2))
    (OUT / "collected_cycles.json").write_text(json.dumps(list(cycles.values())))
    (OUT / "interim_pareto.json").write_text(json.dumps(status, indent=2))
    print(f"DONE n={len(cycles)}", flush=True)


if __name__ == "__main__":
    main()
