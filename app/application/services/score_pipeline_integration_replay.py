"""Replay helper — Score Pipeline Integration over production cycle evidence.

Applies Liquidity v2 + M15/MTF semantics + dedup confidence without mutating
live thresholds or weights. Advisory measurement only.
"""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev
from typing import Any

from app.application.services.score_calibration_audit import (
    CONFIDENCE_WEIGHTS,
    QUALITY_WEIGHTS,
    _histogram,
    _parse_active_obs,
    _parse_bos_choch,
    _parse_open_fvgs,
    _parse_session_quality,
    weighted_total,
)
from app.domain.institutional_trading.m15_semantics_v2 import (
    classify_m15_semantics_from_cycle_evidence,
)
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2
from app.domain.market_structure.enums import TrendDirection

_DIR = {
    "up": TrendDirection.UP,
    "down": TrendDirection.DOWN,
    "range": TrendDirection.RANGE,
    "unknown": TrendDirection.UNKNOWN,
    "—": TrendDirection.UNKNOWN,
}


def _d(value: Any) -> TrendDirection:
    return _DIR.get(str(value or "unknown").lower(), TrendDirection.UNKNOWN)


def integrate_quality_components(
    cycle: dict[str, Any],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Quality after Liquidity v2 + MTF/M15 semantics (weights unchanged)."""
    trend = cycle.get("trend") or {}
    reasons = list((cycle.get("rejection") or {}).get("decision_reasons") or [])
    factors = (cycle.get("confluence") or {}).get("engine_factors") or {}

    h4, h1, m15, m5 = (
        _d(trend.get("h4")),
        _d(trend.get("h1")),
        _d(trend.get("m15")),
        _d(trend.get("m5")),
    )
    latest_bos = None
    for r in reasons:
        m = re.search(r"Latest BOS trend=(\w+)", str(r), re.I)
        if m:
            latest_bos = m.group(1).lower()
            break
    bos_d = _d(latest_bos) if latest_bos else None
    if bos_d is TrendDirection.UNKNOWN:
        bos_d = None

    has_ob = (_parse_active_obs(reasons) or 0) > 0 or int(
        factors.get("order_block") or 0
    ) >= 80
    has_fvg = (_parse_open_fvgs(reasons) or 0) > 0 or int(factors.get("fvg") or 0) >= 70
    has_bos = bos_d is not None or any(
        "structure events" in str(r).lower() for r in reasons
    )

    sem = classify_m15_semantics_from_cycle_evidence(
        h1_direction=h1,
        m15_direction=m15,
        latest_bos_direction=bos_d,
        has_ob=has_ob,
        has_fvg=has_fvg,
        has_bos=has_bos,
    )
    mtf = evaluate_mtf_v2(
        h4=h4,
        h1=h1,
        m15=sem.effective_direction,
        m5=m5,
        scalping=True,
    )
    trend_score = int(mtf.alignment_score)
    if mtf.aligned:
        trend_score = max(trend_score, 75)

    # Liquidity v2: OB/FVG → 65; sweeps would be 85 (not observed in window)
    if has_ob or has_fvg:
        liq = 65
    else:
        liq = 20

    active_ob = _parse_active_obs(reasons)
    ob = 75 if (active_ob and active_ob > 0) or has_ob else 20

    open_fvg = _parse_open_fvgs(reasons)
    if open_fvg is None and has_fvg:
        open_fvg = 2
    if open_fvg and open_fvg >= 2:
        fvg = 85
    elif open_fvg and open_fvg >= 1:
        fvg = 70
    else:
        fvg = 25

    bos, choch = _parse_bos_choch(reasons)
    struct = 30
    if bos is not None or int(factors.get("structure") or 0) >= 75:
        struct += 15
    if bos:
        struct += 25
    if choch:
        struct += 20
    if h1 in {TrendDirection.UP, TrendDirection.DOWN}:
        struct += 10
    struct = min(100, struct)

    session_q = _parse_session_quality(reasons)
    if session_q is None:
        session_q = int(factors.get("session") or 100)
    spread = int(factors.get("spread") or 50)

    scores = {
        "trend": trend_score,
        "liquidity": liq,
        "order_block": ob,
        "fair_value_gap": fvg,
        "market_structure": struct,
        "session": int(session_q),
        "spread": spread,
    }
    meta = {
        "mtf_aligned": mtf.aligned,
        "mtf_score": mtf.alignment_score,
        "m15_raw": m15.value,
        "m15_effective": sem.effective_direction.value,
        "m15_label": sem.new_classification.value,
        "bias": mtf.bias.value,
        "has_ob": has_ob,
        "has_fvg": has_fvg,
        "bos": bos_d.value if bos_d else None,
    }
    return scores, meta


def integrate_confidence_components(
    cycle: dict[str, Any],
    *,
    quality_scores: dict[str, int],
    meta: dict[str, Any],
    quality_total: float,
    quality_passed: bool,
) -> dict[str, int]:
    """Confidence after M15 credit + structural dedup (weights unchanged)."""
    factors = (cycle.get("confluence") or {}).get("engine_factors") or {}
    aligned = bool(meta.get("mtf_aligned"))
    bias = str(meta.get("bias") or "unknown")
    m15_eff = str(meta.get("m15_effective") or "unknown")
    label = str(meta.get("m15_label") or "")

    mtf_score = int(meta.get("mtf_score") or 0)
    if aligned:
        mtf_factor = mtf_score
        m15_factor = 100 if m15_eff == bias else 40
    else:
        mtf_factor = max(0, mtf_score // 2)
        m15_factor = (
            100
            if label
            in {
                "TREND_CONTINUATION",
                "PULLBACK_WITHIN_TREND",
                "CONSOLIDATION",
            }
            and m15_eff == bias
            else 0
        )

    def dedup(q_code: str, observed: int, present: bool, bar: int) -> int:
        q = quality_scores.get(q_code)
        if present and isinstance(q, (int, float)) and int(q) >= bar:
            return int(q)  # single source — no inflation to 100
        return observed

    has_ob = bool(meta.get("has_ob"))
    has_fvg = bool(meta.get("has_fvg"))
    struct_obs = int(factors.get("structure") or 90)
    liq_obs = 65 if (has_ob or has_fvg) else 20
    ob_obs = 85 if has_ob else 20
    fvg_obs = 80 if has_fvg else 25

    return {
        "mtf": int(mtf_factor),
        "m15": int(m15_factor),
        "structure": dedup("market_structure", struct_obs, struct_obs >= 75, 70),
        "liquidity": dedup("liquidity", liq_obs, has_ob or has_fvg, 65),
        "order_block": dedup("order_block", ob_obs, has_ob, 70),
        "fvg": dedup("fair_value_gap", fvg_obs, has_fvg, 70),
        "quality": 100 if quality_passed else int(round(quality_total)),
        "session": int(factors.get("session") or 100),
        "news": int(factors.get("news") or 100),
        "spread": int(factors.get("spread") or 50),
        "volatility": int(factors.get("volatility") or 80),
        "drawdown": int(factors.get("drawdown") or 80),
    }


def replay_score_pipeline_integration(
    cycles: list[dict[str, Any]],
    *,
    min_q: int = 80,
    min_c: int = 80,
) -> dict[str, Any]:
    q_before: list[float] = []
    c_before: list[float] = []
    q_after: list[float] = []
    c_after: list[float] = []
    full_before = full_after = 0
    fp = fn = 0
    evaluated = 0
    m15_zero_after = 0
    samples: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()

    for cycle in cycles:
        factors = (cycle.get("confluence") or {}).get("engine_factors") or {}
        q_log = (cycle.get("quality") or {}).get("score")
        c_log = (cycle.get("confluence") or {}).get("total")
        if q_log is None and c_log is None and not factors:
            continue
        evaluated += 1

        if q_log is not None:
            q_before.append(float(q_log))
        if c_log is not None:
            c_before.append(float(c_log))

        legacy_full = (
            q_log is not None
            and c_log is not None
            and int(q_log) >= min_q
            and int(c_log) >= min_c
        )
        if legacy_full:
            full_before += 1

        q_comp, meta = integrate_quality_components(cycle)
        q_tot = weighted_total(q_comp, QUALITY_WEIGHTS)
        q_pass = q_tot >= min_q
        q_after.append(q_tot)

        c_comp = integrate_confidence_components(
            cycle,
            quality_scores=q_comp,
            meta=meta,
            quality_total=q_tot,
            quality_passed=q_pass,
        )
        c_tot = weighted_total(c_comp, CONFIDENCE_WEIGHTS)
        c_pass = c_tot >= min_c
        c_after.append(c_tot)
        label_counts[str(meta.get("m15_label"))] += 1
        if c_comp.get("m15", 0) == 0:
            m15_zero_after += 1

        integrated_full = bool(
            q_pass
            and c_pass
            and meta.get("mtf_aligned")
            and meta.get("bias") in {"up", "down"}
        )
        if integrated_full:
            full_after += 1

        bos = meta.get("bos")
        h1 = str(((cycle.get("trend") or {}).get("h1") or "")).lower()
        bos_opposes = bool(bos in {"up", "down"} and h1 in {"up", "down"} and bos != h1)
        if integrated_full and bos_opposes:
            fp += 1

        should = (
            h1 in {"up", "down"}
            and bos == h1
            and meta.get("has_ob")
            and meta.get("has_fvg")
            and meta.get("m15_label") != "TRUE_REGIME_REVERSAL"
        )
        if should and not integrated_full:
            fn += 1

        if len(samples) < 8 and (integrated_full or abs(q_tot - float(q_log or 0)) > 5):
            samples.append(
                {
                    "trace_id": cycle.get("trace_id"),
                    "quality_before": q_log,
                    "quality_after": round(q_tot, 2),
                    "confidence_before": c_log,
                    "confidence_after": round(c_tot, 2),
                    "m15": {
                        "raw": meta.get("m15_raw"),
                        "effective": meta.get("m15_effective"),
                        "label": meta.get("m15_label"),
                        "confidence_m15": c_comp.get("m15"),
                    },
                    "mtf_aligned": meta.get("mtf_aligned"),
                    "full_gate_after": integrated_full,
                }
            )

    denom = max(evaluated, 1)
    return {
        "advisory_only": True,
        "thresholds_changed": False,
        "weights_changed": False,
        "weight_inflation": False,
        "min_quality": min_q,
        "min_confidence": min_c,
        "cycles_input": len(cycles),
        "cycles_evaluated": evaluated,
        "averages": {
            "quality_before": round(mean(q_before), 4) if q_before else None,
            "quality_after": round(mean(q_after), 4) if q_after else None,
            "confidence_before": round(mean(c_before), 4) if c_before else None,
            "confidence_after": round(mean(c_after), 4) if c_after else None,
        },
        "distributions": {
            "quality_after": _histogram(q_after) if q_after else {},
            "confidence_after": _histogram(c_after) if c_after else {},
            "quality_after_std": (
                round(pstdev(q_after), 4) if len(q_after) > 1 else None
            ),
            "confidence_after_std": (
                round(pstdev(c_after), 4) if len(c_after) > 1 else None
            ),
        },
        "full_gate": {
            "before": full_before,
            "after": full_after,
            "before_pct": round(100 * full_before / denom, 2),
            "after_pct": round(100 * full_after / denom, 2),
            "expected_broker_submissions": full_after,
            "note": (
                "Full gate = Quality>=80 ∧ Confidence>=80 ∧ MTF H1+M15 aligned "
                "∧ directional bias. Proxy for expected broker submissions."
            ),
        },
        "error_proxies": {
            "false_positives": fp,
            "false_positive_pct": round(100 * fp / denom, 2),
            "false_negatives": fn,
            "false_negative_pct": round(100 * fn / denom, 2),
            "definition_fp": "Full gate while latest BOS opposes H1 bias",
            "definition_fn": (
                "BOS agrees + OB + FVG + H1 directional but full gate still fails"
            ),
        },
        "m15_contribution": {
            "classification_counts": dict(label_counts),
            "m15_factor_zero_after": m15_zero_after,
            "m15_factor_zero_after_pct": round(100 * m15_zero_after / denom, 2),
        },
        "preserved": {
            "quality_weights": dict(QUALITY_WEIGHTS),
            "confidence_weights": dict(CONFIDENCE_WEIGHTS),
            "min_quality": min_q,
            "min_confidence": min_c,
        },
        "samples": samples,
    }
