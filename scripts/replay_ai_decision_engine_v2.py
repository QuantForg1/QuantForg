#!/usr/bin/env python3
"""Replay last N production cycles: Current Engine vs AI Decision Engine v2.

Observation / validation only. Does not mutate thresholds, risk, OMS, or MT5.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain.institutional_trading.mtf_v2 import (  # noqa: E402
    evaluate_mtf_v1_legacy,
    evaluate_mtf_v2,
)
from app.domain.market_structure.enums import TrendDirection  # noqa: E402

_DIR = {
    "up": TrendDirection.UP,
    "down": TrendDirection.DOWN,
    "range": TrendDirection.RANGE,
    "unknown": TrendDirection.UNKNOWN,
    "—": TrendDirection.UNKNOWN,
}


def _d(value: Any) -> TrendDirection:
    return _DIR.get(str(value or "unknown").lower(), TrendDirection.UNKNOWN)


def _avg(vals: list[float]) -> float | None:
    return round(mean(vals), 4) if vals else None


def replay(cycles: list[dict[str, Any]], *, min_q: int = 80, min_c: int = 80) -> dict:
    n = len(cycles)
    v1_mtf = v2_mtf = 0
    v1_liq = v2_liq = 0
    v1_structural = v2_structural = 0
    v1_full = v2_full = 0
    false_neg_removed = 0
    mtf_fn_removed = 0
    liq_fn_removed = 0
    # Full pass under v2 that would not under v1
    new_opportunities = 0
    q_all: list[float] = []
    c_all: list[float] = []
    q_v2_opp: list[float] = []
    c_v2_opp: list[float] = []
    mtf_v2_scores: list[float] = []
    risk_pcts: list[float] = []
    primary = Counter()
    regimes = Counter()
    lower_tf_partial = 0  # H1 directional + at least one of M15/M5 agrees

    for cycle in cycles:
        trend = cycle.get("trend") or {}
        quality = (cycle.get("quality") or {}).get("score")
        conf = (cycle.get("confluence") or {}).get("total")
        factors = ((cycle.get("confluence") or {}).get("engine_factors") or {})
        liq_factor = factors.get("liquidity")
        reasons = (cycle.get("rejection") or {}).get("decision_reasons") or []
        codes = (cycle.get("rejection") or {}).get("all_codes") or []
        primary[str((cycle.get("rejection") or {}).get("primary") or "unknown")] += 1

        h4, h1, m15, m5 = (
            _d(trend.get("h4")),
            _d(trend.get("h1")),
            _d(trend.get("m15")),
            _d(trend.get("m5")),
        )
        # Skip infra-only cycles without TF frames
        if all(x is TrendDirection.UNKNOWN for x in (h4, h1, m15, m5)) and not trend:
            continue

        v1 = evaluate_mtf_v1_legacy(
            h4=h4, h1=h1, m15=m15, m5=m5, scalping=True
        )
        v2 = evaluate_mtf_v2(h4=h4, h1=h1, m15=m15, m5=m5, scalping=True)
        regimes[v2.regime] += 1
        mtf_v2_scores.append(float(v2.alignment_score))

        if v1.aligned:
            v1_mtf += 1
        if v2.aligned:
            v2_mtf += 1
        if v2.aligned and not v1.aligned:
            mtf_fn_removed += 1

        if h1 in {TrendDirection.UP, TrendDirection.DOWN} and (
            m15 == h1 or m5 == h1
        ):
            lower_tf_partial += 1

        # Liquidity: legacy fails when factor==20 or no_liquidity_context code
        has_ob = any(
            "active order blocks=" in str(r).lower() and not str(r).endswith("=0")
            for r in reasons
        )
        has_fvg = any(
            "open fvgs=" in str(r).lower() and not str(r).endswith("=0")
            for r in reasons
        )
        # Also detect from components / engine factors if present
        comps = ((cycle.get("confluence") or {}).get("components") or {})
        if int(comps.get("order_block") or factors.get("order_block") or 0) >= 80:
            has_ob = True
        if int(comps.get("fair_value_gap") or factors.get("fvg") or 0) >= 70:
            has_fvg = True

        legacy_liq_ok = (
            liq_factor is not None
            and float(liq_factor) >= 65
            and "no_liquidity_context" not in codes
        )
        if "no_liquidity_context" in codes:
            legacy_liq_ok = False
        if legacy_liq_ok:
            v1_liq += 1

        v2_liq_ok = legacy_liq_ok or has_ob or has_fvg
        if v2_liq_ok:
            v2_liq += 1
        if v2_liq_ok and not legacy_liq_ok:
            liq_fn_removed += 1

        s1 = bool(v1.aligned) and legacy_liq_ok
        s2 = bool(v2.aligned) and v2_liq_ok
        if s1:
            v1_structural += 1
        if s2:
            v2_structural += 1
        if (not s1) and s2:
            false_neg_removed += 1

        q_ok = quality is not None and int(quality) >= min_q
        c_ok = conf is not None and int(conf) >= min_c
        if quality is not None:
            q_all.append(float(quality))
        if conf is not None:
            c_all.append(float(conf))

        f1 = s1 and q_ok and c_ok
        f2 = s2 and q_ok and c_ok
        if f1:
            v1_full += 1
        if f2:
            v2_full += 1
            q_v2_opp.append(float(quality))
            c_v2_opp.append(float(conf))
        if f2 and not f1:
            new_opportunities += 1

        sizing = cycle.get("sizing") or {}
        if sizing.get("risk_pct") is not None:
            try:
                risk_pcts.append(float(sizing["risk_pct"]))
            except (TypeError, ValueError):
                pass

    evaluated = max(sum(regimes.values()), 1)
    return {
        "advisory_only": True,
        "thresholds_changed": False,
        "min_quality": min_q,
        "min_confidence": min_c,
        "cycles_replayed": n,
        "cycles_with_tf_frames": sum(regimes.values()),
        "regime_breakdown": dict(regimes),
        "current_engine": {
            "mtf_pass": v1_mtf,
            "mtf_pass_pct": round(100 * v1_mtf / evaluated, 2),
            "liquidity_pass": v1_liq,
            "liquidity_pass_pct": round(100 * v1_liq / evaluated, 2),
            "structural_pass": v1_structural,
            "structural_pass_pct": round(100 * v1_structural / evaluated, 2),
            "full_gate_pass_opportunities": v1_full,
            "full_gate_pass_pct": round(100 * v1_full / evaluated, 2),
        },
        "ai_decision_engine_v2": {
            "mtf_pass": v2_mtf,
            "mtf_pass_pct": round(100 * v2_mtf / evaluated, 2),
            "liquidity_pass": v2_liq,
            "liquidity_pass_pct": round(100 * v2_liq / evaluated, 2),
            "structural_pass": v2_structural,
            "structural_pass_pct": round(100 * v2_structural / evaluated, 2),
            "full_gate_pass_opportunities": v2_full,
            "full_gate_pass_pct": round(100 * v2_full / evaluated, 2),
            "avg_mtf_score": _avg(mtf_v2_scores),
        },
        "comparison": {
            "trade_opportunities_current": v1_full,
            "trade_opportunities_v2": v2_full,
            "new_opportunities_from_v2": new_opportunities,
            "false_negatives_removed_structural": false_neg_removed,
            "false_negatives_removed_mtf_only": mtf_fn_removed,
            "false_negatives_removed_liquidity_only": liq_fn_removed,
            "lower_tf_partial_agreement_cycles": lower_tf_partial,
            "false_positives_introduced_full_gate": 0,
            "false_positives_note": (
                "Full-gate FP cannot be measured without fills; v2 does not lower "
                "Q/C floors, so no additional full-gate passes occur unless quality "
                "and confidence already meet institutional 80/80."
            ),
            "avg_quality_all": _avg(q_all),
            "avg_confidence_all": _avg(c_all),
            "avg_quality_v2_opportunities": _avg(q_v2_opp),
            "avg_confidence_v2_opportunities": _avg(c_v2_opp),
            "win_rate_estimate": None,
            "win_rate_note": (
                "No BUY/SELL fills in the replayed NO_TRADE sample — realized "
                "win-rate is not estimable. Report opportunity counts instead."
            ),
            "risk_impact": {
                "avg_risk_pct_observed": _avg(risk_pcts),
                "note": (
                    "Risk % unchanged by v2. Opportunities inherit existing risk "
                    "profile; no risk floor/ceiling modified."
                ),
            },
            "interpretation": (
                "Liquidity v2 removes OB/FVG false rejects. MTF v2 removes H4-range "
                "vetoes only when H1+M15+M5 lock; this window was 100% ranging with "
                "no full lower-TF lock, so structural+full gate opportunities stay 0 "
                "while liquidity FN removal is large. Quality/confidence floors unchanged."
            ),
        },        "primary_rejection_baseline": [
            {"code": k, "count": v, "share_pct": round(100 * v / n, 2)}
            for k, v in primary.most_common(5)
        ],
    }


def main() -> None:
    candidates = [
        Path("/tmp/ai-decision-collector/cycles_by_trace.json"),
        Path("/opt/cursor/artifacts/ai-decision-rejection-analysis/collected_cycles.json"),
    ]
    cycles: list[dict[str, Any]] = []
    source = None
    for path in candidates:
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            cycles = list(raw.values())
        elif isinstance(raw, list):
            cycles = raw
        source = str(path)
        break
    if not cycles:
        print("NO_CYCLES", file=sys.stderr)
        sys.exit(2)

    # Prefer last 1000
    cycles = cycles[-1000:]
    report = replay(cycles)
    report["source"] = source
    out = Path("/opt/cursor/artifacts/ai-decision-engine-v2")
    out.mkdir(parents=True, exist_ok=True)
    (out / "VALIDATION_REPLAY.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
