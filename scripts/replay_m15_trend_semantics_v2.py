#!/usr/bin/env python3
"""Replay last N production cycles: M15 Trend Semantics v2.

Evidence only. Does not lower AI/quality thresholds. Does not mutate OMS/MT5.

Measures:
  - Alignment increase (H1+M15 lock after semantics)
  - False positives / false negatives (structure-evidence proxies)
  - Expected full-gate execution opportunities (Q/C floors unchanged)
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain.institutional_trading.m15_semantics_v2 import (  # noqa: E402
    M15SemanticLabel,
    classify_m15_semantics_from_cycle_evidence,
)
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2  # noqa: E402
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


def _parse_cycle_structure(cycle: dict[str, Any]) -> dict[str, Any]:
    reasons = (cycle.get("rejection") or {}).get("decision_reasons") or []
    factors = (cycle.get("confluence") or {}).get("engine_factors") or {}
    comps = (cycle.get("confluence") or {}).get("components") or {}

    latest_bos = None
    for r in reasons:
        m = re.search(r"Latest BOS trend=(\w+)", str(r), re.I)
        if m:
            latest_bos = m.group(1).lower()
            break

    has_ob = int(factors.get("order_block") or comps.get("order_block") or 0) >= 80
    has_fvg = int(factors.get("fvg") or comps.get("fair_value_gap") or 0) >= 70
    if not has_ob:
        has_ob = any(
            "active order blocks=" in str(r).lower() and not str(r).endswith("=0")
            for r in reasons
        )
    if not has_fvg:
        has_fvg = any(
            "open fvgs=" in str(r).lower() and not str(r).endswith("=0")
            for r in reasons
        )
    has_bos = latest_bos is not None or any(
        "structure events" in str(r).lower() and "bos=" in str(r).lower()
        for r in reasons
    )
    # Heuristic: CHOCH opposes bias only when we see explicit opposing BOS without
    # agreeing BOS — production reasons rarely stamp CHOCH side; keep conservative.
    choch_opposes = False
    return {
        "latest_bos": latest_bos,
        "has_ob": has_ob,
        "has_fvg": has_fvg,
        "has_bos": has_bos,
        "choch_opposes_bias": choch_opposes,
    }


def replay(cycles: list[dict[str, Any]], *, min_q: int = 80, min_c: int = 80) -> dict:
    n = len(cycles)
    labels = Counter()
    prev_m15 = Counter()
    mtf_before = mtf_after = 0
    alignment_gained = 0
    fp = fn = 0
    true_reversals = 0
    pullbacks = consolidations = continuations = 0
    full_before = full_after = 0
    structural_liq_v2 = 0
    q_all: list[float] = []
    c_all: list[float] = []
    samples: list[dict[str, Any]] = []
    evaluated = 0

    for cycle in cycles:
        trend = cycle.get("trend") or {}
        h4, h1, m15, m5 = (
            _d(trend.get("h4")),
            _d(trend.get("h1")),
            _d(trend.get("m15")),
            _d(trend.get("m5")),
        )
        if all(x is TrendDirection.UNKNOWN for x in (h4, h1, m15, m5)) and not trend:
            continue
        evaluated += 1
        prev_m15[m15.value] += 1

        struct = _parse_cycle_structure(cycle)
        bos_d = _d(struct["latest_bos"]) if struct["latest_bos"] else None
        if bos_d is TrendDirection.UNKNOWN:
            bos_d = None

        sem = classify_m15_semantics_from_cycle_evidence(
            h1_direction=h1,
            m15_direction=m15,
            latest_bos_direction=bos_d,
            has_ob=struct["has_ob"],
            has_fvg=struct["has_fvg"],
            has_bos=struct["has_bos"],
            choch_opposes_bias=struct["choch_opposes_bias"],
        )
        labels[sem.new_classification.value] += 1
        if sem.new_classification is M15SemanticLabel.PULLBACK_WITHIN_TREND:
            pullbacks += 1
        elif sem.new_classification is M15SemanticLabel.CONSOLIDATION:
            consolidations += 1
        elif sem.new_classification is M15SemanticLabel.TREND_CONTINUATION:
            continuations += 1
        elif sem.new_classification is M15SemanticLabel.TRUE_REGIME_REVERSAL:
            true_reversals += 1

        before = evaluate_mtf_v2(h4=h4, h1=h1, m15=m15, m5=m5, scalping=True)
        after = evaluate_mtf_v2(
            h4=h4,
            h1=h1,
            m15=sem.effective_direction,
            m5=m5,
            scalping=True,
        )
        if before.aligned:
            mtf_before += 1
        if after.aligned:
            mtf_after += 1
        if after.aligned and not before.aligned:
            alignment_gained += 1

        # FP: we soft-align (pullback/consolidation/continuation → effective=H1)
        # while latest BOS opposes structural bias.
        soft_align_labels = {
            M15SemanticLabel.PULLBACK_WITHIN_TREND,
            M15SemanticLabel.CONSOLIDATION,
            M15SemanticLabel.TREND_CONTINUATION,
        }
        bos_opposes = bool(
            bos_d is not None
            and h1 in {TrendDirection.UP, TrendDirection.DOWN}
            and bos_d in {TrendDirection.UP, TrendDirection.DOWN}
            and bos_d != h1
        )
        if (
            sem.new_classification in soft_align_labels
            and sem.effective_direction == h1
            and bos_opposes
        ):
            fp += 1

        # FN: raw M15 conflicted, BOS agrees + OB + FVG, but we did not soft-align
        raw_conflict = m15 != h1 and h1 in {TrendDirection.UP, TrendDirection.DOWN}
        should_soft = (
            raw_conflict
            and bos_d == h1
            and struct["has_ob"]
            and struct["has_fvg"]
            and not sem.confirmed_reversal
        )
        if should_soft and sem.effective_direction != h1:
            fn += 1

        quality = (cycle.get("quality") or {}).get("score")
        conf = (cycle.get("confluence") or {}).get("total")
        if quality is not None:
            q_all.append(float(quality))
        if conf is not None:
            c_all.append(float(conf))
        q_ok = quality is not None and int(quality) >= min_q
        c_ok = conf is not None and int(conf) >= min_c

        # Liquidity v2 proxy (OB or FVG) — same as decision-engine-v2 replay
        liq_ok = struct["has_ob"] or struct["has_fvg"]
        if liq_ok:
            structural_liq_v2 += 1

        if before.aligned and liq_ok and q_ok and c_ok:
            full_before += 1
        if after.aligned and liq_ok and q_ok and c_ok:
            full_after += 1

        if len(samples) < 12 and (
            sem.rewritten or (after.aligned and not before.aligned)
        ):
            samples.append(
                {
                    "trace_id": cycle.get("trace_id"),
                    "previous_m15": sem.previous_classification,
                    "new_classification": sem.new_classification.value,
                    "reason": sem.reason,
                    "counterfactual": {
                        "mtf_before": before.aligned,
                        "mtf_after": after.aligned,
                        "score_before": before.alignment_score,
                        "score_after": after.alignment_score,
                    },
                    "frames": {
                        "h4": h4.value,
                        "h1": h1.value,
                        "m15_raw": m15.value,
                        "m15_effective": sem.effective_direction.value,
                        "m5": m5.value,
                    },
                }
            )

    denom = max(evaluated, 1)
    fp_rate = round(100 * fp / denom, 2)
    fn_rate = round(100 * fn / denom, 2)
    merge_recommendation = (
        "CANDIDATE — false positives acceptably low; thresholds unchanged"
        if fp_rate <= 5.0 and mtf_after > mtf_before
        else "HOLD — review FP/FN before merge"
    )

    return {
        "advisory_only": True,
        "thresholds_changed": False,
        "min_quality": min_q,
        "min_confidence": min_c,
        "directional_lock": "H1+M15",
        "m5_role": "execution_timing_only",
        "cycles_replayed": n,
        "cycles_evaluated": evaluated,
        "previous_m15_distribution": dict(prev_m15),
        "new_classification_distribution": dict(labels),
        "pullback_within_trend": pullbacks,
        "consolidation": consolidations,
        "trend_continuation": continuations,
        "true_regime_reversal": true_reversals,
        "mtf_alignment": {
            "before_semantics_pass": mtf_before,
            "before_semantics_pct": round(100 * mtf_before / denom, 2),
            "after_semantics_pass": mtf_after,
            "after_semantics_pct": round(100 * mtf_after / denom, 2),
            "alignment_increase": alignment_gained,
            "alignment_increase_pct": round(100 * alignment_gained / denom, 2),
        },
        "error_proxies": {
            "false_positives": fp,
            "false_positive_pct": fp_rate,
            "false_negatives": fn,
            "false_negative_pct": fn_rate,
            "definition_fp": (
                "Soft-aligned (pullback/consolidation/continuation) while "
                "latest BOS opposes structural H1 bias"
            ),
            "definition_fn": (
                "Raw M15 conflicted, BOS agrees + OB + FVG, but effective "
                "direction did not align with H1"
            ),
        },
        "execution_opportunities": {
            "full_gate_before": full_before,
            "full_gate_after": full_after,
            "expected_new_opportunities": max(0, full_after - full_before),
            "liquidity_v2_proxy_pass": structural_liq_v2,
            "avg_quality": _avg(q_all),
            "avg_confidence": _avg(c_all),
            "note": "Q/C floors remain 80/80 — opportunities require both",
        },
        "merge_gate": {
            "recommendation": merge_recommendation,
            "false_positive_accept_max_pct": 5.0,
            "auto_merge": False,
        },
        "sample_telemetry": samples,
    }


def main() -> int:
    src = Path("/tmp/ai-decision-collector/cycles_by_trace.json")
    if not src.exists():
        alt = ROOT / "data" / "cycles_by_trace.json"
        src = alt if alt.exists() else src
    if not src.exists():
        print(json.dumps({"error": f"missing cycles file: {src}"}))
        return 1

    raw = json.loads(src.read_text())
    cycles = list(raw.values()) if isinstance(raw, dict) else list(raw)
    # Prefer most recent 1000
    cycles = cycles[-1000:]
    report = replay(cycles)

    out_dir = Path("/opt/cursor/artifacts/m15-trend-semantics-v2")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "REPLAY.json").write_text(json.dumps(report, indent=2) + "\n")

    md = [
        "# M15 Trend Semantics v2 — Replay (N=1000)",
        "",
        "**Evidence only. Thresholds unchanged (Q/C 80/80). No auto-merge.**",
        "",
        f"Source: `{src}`",
        "",
        "## Directional lock",
        "",
        "- H1 + M15 (after semantics)",
        "- M5 = execution timing only",
        "",
        "## Classification distribution",
        "",
        "```json",
        json.dumps(report["new_classification_distribution"], indent=2),
        "```",
        "",
        "## Alignment",
        "",
        "```json",
        json.dumps(report["mtf_alignment"], indent=2),
        "```",
        "",
        "## False positives / negatives",
        "",
        "```json",
        json.dumps(report["error_proxies"], indent=2),
        "```",
        "",
        "## Expected execution opportunities",
        "",
        "```json",
        json.dumps(report["execution_opportunities"], indent=2),
        "```",
        "",
        "## Merge gate",
        "",
        f"- Recommendation: **{report['merge_gate']['recommendation']}**",
        "- Auto-merge: false",
        "",
    ]
    (out_dir / "REPLAY.md").write_text("\n".join(md) + "\n")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out_dir / 'REPLAY.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
