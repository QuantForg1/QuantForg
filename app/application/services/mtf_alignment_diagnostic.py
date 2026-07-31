"""MTF Alignment Diagnostic — evidence only (no threshold / engine mutations).

Analyses production Strategy Diagnostics cycles to explain why H1/M15/M5
almost never fully lock under ranging-H4 policy.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal

BlockerTF = Literal["H1", "M15", "M5", "none", "multi", "no_bias"]
RootCause = Literal[
    "market_structure",
    "execution_timing",
    "trend_detection",
    "noise_filtering",
    "mixed",
    "infra",
]


def _avg(vals: list[float]) -> float | None:
    return round(mean(vals), 4) if vals else None


def _norm_dir(value: Any) -> str:
    s = str(value or "unknown").strip().lower()
    if s in {"up", "bull", "bullish", "long"}:
        return "up"
    if s in {"down", "bear", "bearish", "short"}:
        return "down"
    if s in {"range", "ranging", "sideways"}:
        return "range"
    if s in {"—", "-", "none", "", "null"}:
        return "unknown"
    return s if s in {"up", "down", "range", "unknown"} else "unknown"


def _parse_bos_choch(reasons: list[str]) -> tuple[int | None, int | None, str | None]:
    bos = choch = None
    latest_bos_trend = None
    for raw in reasons:
        text = str(raw)
        m = re.search(r"bos=(\d+)\s+choch=(\d+)", text, re.I)
        if m:
            bos = int(m.group(1))
            choch = int(m.group(2))
        m2 = re.search(r"Latest BOS trend=(\w+)", text, re.I)
        if m2:
            latest_bos_trend = _norm_dir(m2.group(1))
    return bos, choch, latest_bos_trend


def _parse_ob_fvg(reasons: list[str]) -> tuple[int | None, int | None]:
    ob = fvg = None
    for raw in reasons:
        text = str(raw)
        m = re.search(r"Active order blocks=(\d+)", text, re.I)
        if m:
            ob = int(m.group(1))
        m2 = re.search(r"Open FVGs=(\d+)", text, re.I)
        if m2:
            fvg = int(m2.group(1))
    return ob, fvg


@dataclass(frozen=True, slots=True)
class CycleMtfRecord:
    trace_id: str | None
    h4: str
    h1: str
    m15: str
    m5: str
    trend_strength: int | None
    bos: int | None
    choch: int | None
    latest_bos_trend: str | None
    order_block: int | None
    fvg: int | None
    liquidity_factor: int | None
    liquidity_component: int | None
    execution_trigger: str
    quality: int | None
    confidence: int | None
    primary_rejection: str | None
    fully_aligned: bool
    bias: str | None
    blockers: tuple[str, ...]
    conflict_signature: str
    root_cause: RootCause
    structure_vs_m15_conflict: bool
    structure_vs_m5_conflict: bool


def _execution_trigger(cycle: dict[str, Any], h1: str, m15: str, m5: str) -> str:
    """Classify the apparent execution-trigger state (observe-only)."""
    if h1 in {"up", "down"} and m15 == h1 and m5 == h1:
        return "full_lower_tf_lock"
    if h1 in {"up", "down"} and m15 == "range" and m5 == "range":
        return "compression_no_trigger"
    if h1 in {"up", "down"} and m15 == "range" and m5 == h1:
        return "m15_range_wait_m5_agrees"
    if h1 in {"up", "down"} and m15 == "range" and m5 != h1:
        return "m15_range_and_m5_conflict"
    if h1 in {"up", "down"} and m5 == "range" and m15 == h1:
        return "m5_range_wait_m15_agrees"
    if h1 in {"up", "down"} and m5 == "range" and m15 != h1:
        return "m15_conflict_and_m5_range"
    if h1 in {"up", "down"} and m15 == h1 and m5 != h1:
        return "m5_entry_conflict"
    if h1 in {"up", "down"} and m5 == h1 and m15 != h1:
        return "m15_confirmation_conflict"
    if h1 in {"up", "down"} and m15 not in {h1, "unknown", "range"} and m5 not in {
        h1,
        "unknown",
        "range",
    }:
        if m15 == m5:
            return "lower_tfs_united_against_h1"
        return "triple_disagreement"
    if h1 == "range":
        return "no_h1_structure_bias"
    return "indeterminate"


def _blockers(h1: str, m15: str, m5: str) -> tuple[str, ...]:
    if h1 not in {"up", "down"}:
        return ("H1",)
    missing: list[str] = []
    if m15 != h1:
        missing.append("M15")
    if m5 != h1:
        missing.append("M5")
    return tuple(missing) if missing else ("none",)


def _root_cause(rec_inputs: dict[str, Any]) -> RootCause:
    """Heuristic root-cause class from artefacts (evidence taxonomy)."""
    h1 = rec_inputs["h1"]
    m15 = rec_inputs["m15"]
    m5 = rec_inputs["m5"]
    bos = rec_inputs.get("bos")
    choch = rec_inputs.get("choch")
    latest_bos = rec_inputs.get("latest_bos_trend")
    primary = str(rec_inputs.get("primary_rejection") or "")

    if primary in {"NO_SNAPSHOT", "NO_MARKET_CONTEXT", "SAFETY_BLOCKED"}:
        return "infra"

    # Quiet tape on both confirmation and entry TFs
    if h1 in {"up", "down"} and m15 == "range" and m5 == "range":
        return "noise_filtering"

    # Structure events exist and latest BOS agrees with H1, but M15/M5 disagree
    # → often execution timing / pullback on lower TF
    structure_rich = (bos or 0) > 0 or (choch or 0) > 0
    if (
        h1 in {"up", "down"}
        and structure_rich
        and latest_bos == h1
        and m15 != h1
        and m5 != h1
    ):
        if m15 == "range" or m5 == "range":
            return "execution_timing"
        return "execution_timing"

    if h1 in {"up", "down"} and m15 == h1 and m5 != h1:
        # Classic entry-TF noise / premature trigger
        if m5 == "range":
            return "noise_filtering"
        return "execution_timing"

    if h1 in {"up", "down"} and m5 == h1 and m15 != h1:
        # Mid TF opposes while micro agrees — structure conflict on confirmation TF
        return "market_structure"

    if h1 in {"up", "down"} and m15 != h1 and m5 != h1 and m15 == m5:
        return "market_structure"

    if h1 in {"up", "down"} and (m15 == "range" or m5 == "range"):
        return "noise_filtering"

    if h1 == "range":
        return "trend_detection"

    # H1 vs lower TFs with BOS trend opposite H1 → trend detection inconsistency
    if latest_bos and h1 in {"up", "down"} and latest_bos != h1:
        return "trend_detection"

    if structure_rich and h1 in {"up", "down"} and (m15 != h1 or m5 != h1):
        return "mixed"

    return "mixed"


def analyze_cycle(cycle: dict[str, Any]) -> CycleMtfRecord | None:
    trend = cycle.get("trend") if isinstance(cycle.get("trend"), dict) else {}
    if not trend and (cycle.get("rejection") or {}).get("primary") in {
        "NO_SNAPSHOT",
        "NO_MARKET_CONTEXT",
    }:
        return CycleMtfRecord(
            trace_id=str(cycle.get("trace_id") or "") or None,
            h4="unknown",
            h1="unknown",
            m15="unknown",
            m5="unknown",
            trend_strength=None,
            bos=None,
            choch=None,
            latest_bos_trend=None,
            order_block=None,
            fvg=None,
            liquidity_factor=None,
            liquidity_component=None,
            execution_trigger="infra",
            quality=None,
            confidence=None,
            primary_rejection=str((cycle.get("rejection") or {}).get("primary")),
            fully_aligned=False,
            bias=None,
            blockers=("H1", "M15", "M5"),
            conflict_signature="INFRA",
            root_cause="infra",
            structure_vs_m15_conflict=False,
            structure_vs_m5_conflict=False,
        )

    h4 = _norm_dir(trend.get("h4"))
    h1 = _norm_dir(trend.get("h1"))
    m15 = _norm_dir(trend.get("m15"))
    m5 = _norm_dir(trend.get("m5"))
    strength = trend.get("score")
    try:
        strength_i = int(strength) if strength is not None else None
    except (TypeError, ValueError):
        strength_i = None

    rejection = cycle.get("rejection") if isinstance(cycle.get("rejection"), dict) else {}
    reasons = [str(r) for r in (rejection.get("decision_reasons") or [])]
    bos, choch, latest_bos = _parse_bos_choch(reasons)
    ob, fvg = _parse_ob_fvg(reasons)

    conf = cycle.get("confluence") if isinstance(cycle.get("confluence"), dict) else {}
    components = conf.get("components") if isinstance(conf.get("components"), dict) else {}
    factors = (
        conf.get("engine_factors") if isinstance(conf.get("engine_factors"), dict) else {}
    )
    if ob is None and components.get("order_block") is not None:
        try:
            ob = 1 if int(components["order_block"]) >= 80 else 0
        except (TypeError, ValueError):
            pass
    if fvg is None and components.get("fair_value_gap") is not None:
        try:
            fvg = 1 if int(components["fair_value_gap"]) >= 70 else 0
        except (TypeError, ValueError):
            pass
    if bos is None and components.get("bos") is not None:
        try:
            bos = 1 if int(components["bos"]) >= 80 else 0
        except (TypeError, ValueError):
            pass
    if choch is None and components.get("choch") is not None:
        try:
            choch = 1 if int(components["choch"]) >= 80 else 0
        except (TypeError, ValueError):
            pass

    liq_factor = factors.get("liquidity")
    liq_comp = components.get("liquidity_sweep")
    try:
        liq_factor_i = int(liq_factor) if liq_factor is not None else None
    except (TypeError, ValueError):
        liq_factor_i = None
    try:
        liq_comp_i = int(liq_comp) if liq_comp is not None else None
    except (TypeError, ValueError):
        liq_comp_i = None

    q = (cycle.get("quality") or {}).get("score") if isinstance(cycle.get("quality"), dict) else None
    c = conf.get("total")
    try:
        q_i = int(q) if q is not None else None
    except (TypeError, ValueError):
        q_i = None
    try:
        c_i = int(c) if c is not None else None
    except (TypeError, ValueError):
        c_i = None

    bias = h1 if h1 in {"up", "down"} else None
    fully = bool(bias and m15 == bias and m5 == bias)
    blockers = _blockers(h1, m15, m5)
    trigger = _execution_trigger(cycle, h1, m15, m5)
    signature = f"H1={h1}|M15={m15}|M5={m5}"
    root = _root_cause(
        {
            "h1": h1,
            "m15": m15,
            "m5": m5,
            "bos": bos,
            "choch": choch,
            "latest_bos_trend": latest_bos,
            "primary_rejection": rejection.get("primary"),
        }
    )
    return CycleMtfRecord(
        trace_id=str(cycle.get("trace_id") or "") or None,
        h4=h4,
        h1=h1,
        m15=m15,
        m5=m5,
        trend_strength=strength_i,
        bos=bos,
        choch=choch,
        latest_bos_trend=latest_bos,
        order_block=ob,
        fvg=fvg,
        liquidity_factor=liq_factor_i,
        liquidity_component=liq_comp_i,
        execution_trigger=trigger,
        quality=q_i,
        confidence=c_i,
        primary_rejection=(
            str(rejection.get("primary")) if rejection.get("primary") else None
        ),
        fully_aligned=fully,
        bias=bias,
        blockers=blockers,
        conflict_signature=signature,
        root_cause=root,
        structure_vs_m15_conflict=bool(
            bias and latest_bos == bias and m15 not in {bias, "unknown"}
        ),
        structure_vs_m5_conflict=bool(
            bias and latest_bos == bias and m5 not in {bias, "unknown"}
        ),
    )


def diagnose_mtf_alignment(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate MTF alignment diagnostics for a cycle sample."""
    records = [r for r in (analyze_cycle(c) for c in cycles) if r is not None]
    n = len(records)
    if n == 0:
        return {
            "advisory_only": True,
            "thresholds_changed": False,
            "cycles_analyzed": 0,
        }

    full = sum(1 for r in records if r.fully_aligned)
    blocker_counts: Counter[str] = Counter()
    single_blocker: Counter[str] = Counter()
    combo_blocker: Counter[str] = Counter()
    signatures: Counter[str] = Counter()
    triggers: Counter[str] = Counter()
    roots: Counter[str] = Counter()
    h1_dirs: Counter[str] = Counter()
    m15_dirs: Counter[str] = Counter()
    m5_dirs: Counter[str] = Counter()
    strengths: list[float] = []
    examples: dict[str, list[dict[str, Any]]] = {}

    struct_m15 = struct_m5 = 0
    bos_vals: list[float] = []
    choch_vals: list[float] = []
    ob_present = fvg_present = 0
    liq_low = 0

    for r in records:
        h1_dirs[r.h1] += 1
        m15_dirs[r.m15] += 1
        m5_dirs[r.m5] += 1
        signatures[r.conflict_signature] += 1
        triggers[r.execution_trigger] += 1
        roots[r.root_cause] += 1
        if r.trend_strength is not None:
            strengths.append(float(r.trend_strength))
        if r.bos is not None:
            bos_vals.append(float(r.bos))
        if r.choch is not None:
            choch_vals.append(float(r.choch))
        if (r.order_block or 0) > 0:
            ob_present += 1
        if (r.fvg or 0) > 0:
            fvg_present += 1
        if r.liquidity_factor is not None and r.liquidity_factor <= 20:
            liq_low += 1
        if r.structure_vs_m15_conflict:
            struct_m15 += 1
        if r.structure_vs_m5_conflict:
            struct_m5 += 1

        if r.fully_aligned:
            blocker_counts["none"] += 1
            continue

        for b in r.blockers:
            blocker_counts[b] += 1
        if r.blockers == ("M15",):
            single_blocker["M15_only"] += 1
        elif r.blockers == ("M5",):
            single_blocker["M5_only"] += 1
        elif r.blockers == ("H1",):
            single_blocker["H1_only"] += 1
        elif set(r.blockers) == {"M15", "M5"}:
            combo_blocker["M15+M5"] += 1
        elif "H1" in r.blockers and len(r.blockers) > 1:
            combo_blocker["H1+others"] += 1

        key = "+".join(r.blockers) if r.blockers else "unknown"
        bucket = examples.setdefault(key, [])
        if len(bucket) < 3:
            bucket.append(
                {
                    "trace_id": r.trace_id,
                    "H1": r.h1,
                    "M15": r.m15,
                    "M5": r.m5,
                    "trend_strength": r.trend_strength,
                    "bos": r.bos,
                    "choch": r.choch,
                    "latest_bos_trend": r.latest_bos_trend,
                    "order_block": r.order_block,
                    "fvg": r.fvg,
                    "liquidity_factor": r.liquidity_factor,
                    "execution_trigger": r.execution_trigger,
                    "root_cause": r.root_cause,
                    "outcome": "Reject",
                }
            )

    # Which TF prevented alignment most often among non-full locks
    non_full = n - full
    prevented_by = {
        "M15_involved": sum(
            1 for r in records if (not r.fully_aligned) and "M15" in r.blockers
        ),
        "M5_involved": sum(
            1 for r in records if (not r.fully_aligned) and "M5" in r.blockers
        ),
        "H1_involved": sum(
            1 for r in records if (not r.fully_aligned) and "H1" in r.blockers
        ),
        "M15_only": single_blocker.get("M15_only", 0),
        "M5_only": single_blocker.get("M5_only", 0),
        "M15_and_M5": combo_blocker.get("M15+M5", 0),
    }

    top_conflicts = [
        {
            "combination": sig,
            "count": cnt,
            "share_pct": round(100.0 * cnt / n, 2),
            "example_path": _example_path(sig),
        }
        for sig, cnt in signatures.most_common(15)
    ]

    return {
        "advisory_only": True,
        "mutates_engines": False,
        "thresholds_changed": False,
        "cycles_analyzed": n,
        "full_h1_m15_m5_alignment": {
            "count": full,
            "share_pct": round(100.0 * full / n, 2),
        },
        "direction_frequency": {
            "H1": dict(h1_dirs),
            "M15": dict(m15_dirs),
            "M5": dict(m5_dirs),
        },
        "averages": {
            "trend_strength": _avg(strengths),
            "bos_count_or_score": _avg(bos_vals),
            "choch_count_or_score": _avg(choch_vals),
            "quality": _avg(
                [float(r.quality) for r in records if r.quality is not None]
            ),
            "confidence": _avg(
                [float(r.confidence) for r in records if r.confidence is not None]
            ),
        },
        "structure_presence": {
            "order_block_present_share_pct": round(100.0 * ob_present / n, 2),
            "fvg_present_share_pct": round(100.0 * fvg_present / n, 2),
            "legacy_liquidity_factor_le_20_share_pct": round(100.0 * liq_low / n, 2),
            "latest_bos_agrees_h1_but_m15_conflicts_share_pct": round(
                100.0 * struct_m15 / n, 2
            ),
            "latest_bos_agrees_h1_but_m5_conflicts_share_pct": round(
                100.0 * struct_m5 / n, 2
            ),
        },
        "which_timeframe_prevented_alignment": {
            **prevented_by,
            "non_full_alignment_cycles": non_full,
            "M15_involved_share_of_non_full_pct": round(
                100.0 * prevented_by["M15_involved"] / max(non_full, 1), 2
            ),
            "M5_involved_share_of_non_full_pct": round(
                100.0 * prevented_by["M5_involved"] / max(non_full, 1), 2
            ),
            "H1_involved_share_of_non_full_pct": round(
                100.0 * prevented_by["H1_involved"] / max(non_full, 1), 2
            ),
            "M15_only_share_of_non_full_pct": round(
                100.0 * prevented_by["M15_only"] / max(non_full, 1), 2
            ),
            "M5_only_share_of_non_full_pct": round(
                100.0 * prevented_by["M5_only"] / max(non_full, 1), 2
            ),
            "M15_and_M5_share_of_non_full_pct": round(
                100.0 * prevented_by["M15_and_M5"] / max(non_full, 1), 2
            ),
        },
        "most_common_conflicting_combinations": top_conflicts,
        "execution_trigger_frequency": [
            {
                "trigger": k,
                "count": v,
                "share_pct": round(100.0 * v / n, 2),
            }
            for k, v in triggers.most_common()
        ],
        "root_cause_classification": [
            {
                "cause": k,
                "count": v,
                "share_pct": round(100.0 * v / n, 2),
            }
            for k, v in roots.most_common()
        ],
        "examples_by_blocker": examples,
        "blocker_hit_counts": dict(blocker_counts),
    }


def _example_path(signature: str) -> str:
    # H1=up|M15=down|M5=up → narrative
    parts = {}
    for chunk in signature.split("|"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k] = v
    h1 = parts.get("H1", "?")
    m15 = parts.get("M15", "?")
    m5 = parts.get("M5", "?")
    if h1 in {"up", "down"} and m15 == h1 and m5 == h1:
        return f"H1 {h1} · M15 {m15} · M5 {m5} → Align"
    return f"H1 {h1} · M15 {m15} · M5 {m5} → Reject"


def load_cycles(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return list(raw.values())
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    return []


def propose_improvements(report: dict[str, Any]) -> list[dict[str, str]]:
    """Safety-preserving proposals — no threshold cuts."""
    prevented = report.get("which_timeframe_prevented_alignment") or {}
    roots = {
        row["cause"]: row["share_pct"]
        for row in (report.get("root_cause_classification") or [])
    }
    proposals: list[dict[str, str]] = []

    m15_only = float(prevented.get("M15_only_share_of_non_full_pct") or 0)
    m5_only = float(prevented.get("M5_only_share_of_non_full_pct") or 0)
    both = float(prevented.get("M15_and_M5_share_of_non_full_pct") or 0)

    if both >= 40:
        proposals.append(
            {
                "id": "P1_structure_mid_tf_sync",
                "title": "Sync M15 trend detection with H1 BOS/CHOCH",
                "rationale": (
                    f"M15+M5 jointly block {both}% of non-alignments. Often H1 BOS "
                    "agrees with H1 bias while M15 prints opposite/range — investigate "
                    "whether M15 trend state lags structure events (trend_detection / "
                    "market_structure), not gate floors."
                ),
                "safety": "No Q/C threshold change. Align detector semantics only.",
            }
        )
    if m5_only >= 15:
        proposals.append(
            {
                "id": "P2_m5_execution_confirm_window",
                "title": "M5 confirmation window (timing, not floor cut)",
                "rationale": (
                    f"M5-only blocks {m5_only}% of non-alignments. Allow a short "
                    "confirmation lookback (e.g. last closed M5 must agree, or 2-of-3 "
                    "closed M5 bars) instead of single-bar veto — reduces execution "
                    "timing false conflicts."
                ),
                "safety": "Still requires directional agreement; does not lower 80/80.",
            }
        )
    if m15_only >= 15:
        proposals.append(
            {
                "id": "P3_m15_pullback_state",
                "title": "Distinguish M15 pullback vs regime flip",
                "rationale": (
                    f"M15-only blocks {m15_only}%. When H1 BOS agrees and M15 is a "
                    "shallow opposite print inside H1 structure, classify as pullback "
                    "confirm-wait rather than hard opposite bias."
                ),
                "safety": "Quality/confidence floors unchanged; adds state taxonomy.",
            }
        )
    if float(roots.get("noise_filtering") or 0) >= 20:
        proposals.append(
            {
                "id": "P4_range_hysteresis",
                "title": "RANGE hysteresis on M15/M5",
                "rationale": (
                    "Large share classified as noise_filtering (range prints). Require "
                    "N closed bars or ATR excursion before flipping M15/M5 out of prior "
                    "directional state."
                ),
                "safety": "Filters noise; does not relax confluence/quality gates.",
            }
        )
    if float(roots.get("execution_timing") or 0) >= 20:
        proposals.append(
            {
                "id": "P5_entry_trigger_decouple",
                "title": "Decouple alignment lock from entry trigger",
                "rationale": (
                    "Keep H1+M15 as alignment lock; use M5 only as entry trigger "
                    "once lock exists (M5 opposite delays entry, does not destroy "
                    "alignment). Reduces structural conflicts from micro noise."
                ),
                "safety": "Institutional H1+M15 agreement retained; Q/C floors intact.",
            }
        )
    if not proposals:
        proposals.append(
            {
                "id": "P0_continue_observe",
                "title": "Continue observation across London/NY",
                "rationale": "Current window may be Tokyo-dominated ranging; expand sessions.",
                "safety": "Evidence only.",
            }
        )
    proposals.append(
        {
            "id": "P_SAFE",
            "title": "Do not lower quality/confidence thresholds",
            "rationale": "Avg quality/confidence remain below 80 in this sample; floor cuts would not create high-quality trades.",
            "safety": "Mandatory — no automatic merge of threshold changes.",
        }
    )
    return proposals
