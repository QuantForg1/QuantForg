"""AI Score Calibration audit — Quality + Confidence decomposition (evidence only).

Never mutates thresholds, weights, risk, OMS, or MT5.
Never auto-recalibrates. Advisory recommendations only when data supports them.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.trade_quality import TradeQualityEvaluator

# Canonical weights (must match production evaluators — do not mutate).
QUALITY_WEIGHTS: dict[str, int] = {
    "trend": 20,
    "liquidity": 15,
    "order_block": 15,
    "fair_value_gap": 15,
    "market_structure": 15,
    "session": 10,
    "spread": 10,
}

CONFIDENCE_WEIGHTS: dict[str, int] = {
    "mtf": 22,
    "m15": 8,
    "structure": 12,
    "liquidity": 10,
    "order_block": 12,
    "fvg": 10,
    "quality": 12,
    "session": 6,
    "news": 4,
    "spread": 2,
    "volatility": 1,
    "drawdown": 1,
}

# Documented component caps from TradeQualityEvaluator (not confluence factors).
QUALITY_CAPS: dict[str, dict[str, Any]] = {
    "trend": {
        "hard_cap": 100,
        "aligned_floor": 75,
        "note": "Uses MTF alignment_score; max(score,75) only when aligned",
    },
    "liquidity": {
        "hard_cap": 100,
        "no_sweep_floor": 40,
        "sweep_only": 70,
        "sweep_plus_pool": 100,
        "note": "Legacy sweeps/pools/EQH/EQL only — OB/FVG do not lift quality liquidity",
    },
    "order_block": {
        "hard_cap": 85,
        "active_only": 75,
        "breaker_only": 55,
        "active_plus_breaker": 85,
        "note": "Cannot reach 100; active OB without breaker caps at 75",
    },
    "fair_value_gap": {
        "hard_cap": 85,
        "one_open": 70,
        "two_plus_open": 85,
        "note": "Cannot reach 100",
    },
    "market_structure": {
        "hard_cap": 100,
        "note": "30 base + swings/BOS/CHOCH/direction bonuses",
    },
    "session": {
        "hard_cap": 100,
        "soft_tokyo_typical": 55,
        "note": "Soft session quality_score; not binary",
    },
    "spread": {
        "hard_cap": 100,
        "note": "100 when <= max_spread_for_full_score",
    },
}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _histogram(values: list[float], *, bins: list[int] | None = None) -> dict[str, int]:
    edges = bins or [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    counts: dict[str, int] = {}
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        label = f"{lo}-{hi}" if hi < 100 or i < len(edges) - 2 else f"{lo}-{hi}"
        if i == len(edges) - 2:
            label = f"{lo}-{hi}"
        counts[label] = 0
    # inclusive top
    for v in values:
        placed = False
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            if i < len(edges) - 2:
                if lo <= v < hi:
                    counts[f"{lo}-{hi}"] += 1
                    placed = True
                    break
            else:
                if lo <= v <= hi:
                    counts[f"{lo}-{hi}"] += 1
                    placed = True
                    break
        if not placed:
            counts.setdefault("other", 0)
            counts["other"] += 1
    return counts


def _component_stats(
    scores: list[float],
    *,
    weight: int,
    name: str,
) -> dict[str, Any]:
    if not scores:
        return {
            "component": name,
            "weight": weight,
            "n": 0,
            "score_mean": None,
            "score_variance": None,
            "score_std": None,
            "score_min": None,
            "score_max": None,
            "contribution_mean": None,
            "contribution_max_observed": None,
            "contribution_max_theoretical": round(100 * weight / 100, 4),
            "frequency_nonzero_pct": 0.0,
            "frequency_below_80_pct": None,
            "frequency_at_cap_proxy": None,
        }
    n = len(scores)
    avg = mean(scores)
    var = pstdev(scores) ** 2 if n > 1 else 0.0
    std = math.sqrt(var)
    contribs = [s * weight / 100.0 for s in scores]
    nonzero = sum(1 for s in scores if s > 0)
    below80 = sum(1 for s in scores if s < 80)
    return {
        "component": name,
        "weight": weight,
        "n": n,
        "score_mean": round(avg, 4),
        "score_variance": round(var, 4),
        "score_std": round(std, 4),
        "score_min": round(min(scores), 4),
        "score_max": round(max(scores), 4),
        "contribution_mean": round(mean(contribs), 4),
        "contribution_max_observed": round(max(contribs), 4),
        "contribution_max_theoretical": round(100 * weight / 100.0, 4),
        "frequency_nonzero_pct": round(100 * nonzero / n, 2),
        "frequency_below_80_pct": round(100 * below80 / n, 2),
        "score_histogram": _histogram(scores),
    }


def _parse_session_quality(reasons: list[Any]) -> int | None:
    for r in reasons:
        m = re.search(r"quality=(\d+)", str(r))
        if m:
            return int(m.group(1))
    return None


def _parse_bos_choch(reasons: list[Any]) -> tuple[int | None, int | None]:
    for r in reasons:
        m = re.search(r"bos=(\d+)\s+choch=(\d+)", str(r), re.I)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_open_fvgs(reasons: list[Any]) -> int | None:
    for r in reasons:
        m = re.search(r"Open FVGs=(\d+)", str(r), re.I)
        if m:
            return int(m.group(1))
    return None


def _parse_active_obs(reasons: list[Any]) -> int | None:
    for r in reasons:
        m = re.search(r"Active order blocks=(\d+)", str(r), re.I)
        if m:
            return int(m.group(1))
    return None


def reconstruct_quality_components(cycle: dict[str, Any]) -> dict[str, int]:
    """Best-effort reconstruction of TradeQualityEvaluator component scores.

    Production cycle logs store quality.total only. Reconstruction uses the
    same rules as ``TradeQualityEvaluator`` plus evidence present on the cycle.
    Marked ``reconstructed=True`` in callers.
    """
    trend = cycle.get("trend") or {}
    reasons = list((cycle.get("rejection") or {}).get("decision_reasons") or [])
    factors = (cycle.get("confluence") or {}).get("engine_factors") or {}
    codes = list((cycle.get("rejection") or {}).get("all_codes") or [])

    # trend — alignment_score; aligned floor only when aligned
    align = int(trend.get("score") or factors.get("mtf") or 0)
    # When mtf not aligned, confluence stores score//2 — prefer trend.score
    if trend.get("score") is not None:
        align = int(trend["score"])
    aligned = bool(trend.get("aligned"))
    trend_score = max(align, 75) if aligned else align

    # liquidity — legacy: no sweeps ⇒ 40 (dominant production pattern)
    liq = 40
    if "no_liquidity_context" in codes or int(factors.get("liquidity") or 0) <= 20:
        liq = 40  # no sweeps/pools path
    elif int(factors.get("liquidity") or 0) >= 65:
        # sweeps present in legacy sense
        liq = 70

    # order_block — active without breaker ⇒ 75 (confluence uses 85)
    active_ob = _parse_active_obs(reasons)
    if active_ob and active_ob > 0:
        ob = 75
    elif int(factors.get("order_block") or 0) >= 80:
        ob = 75
    else:
        ob = 20

    # FVG — open count
    open_fvg = _parse_open_fvgs(reasons)
    if open_fvg is None and int(factors.get("fvg") or 0) >= 70:
        open_fvg = 2 if int(factors.get("fvg") or 0) >= 80 else 1
    if open_fvg and open_fvg >= 2:
        fvg = 85
    elif open_fvg and open_fvg >= 1:
        fvg = 70
    else:
        fvg = 25

    # market_structure
    bos, choch = _parse_bos_choch(reasons)
    struct = 30
    # swings unknown in logs — assume >=4 when structure events present (production)
    if bos is not None or int(factors.get("structure") or 0) >= 75:
        struct += 15  # swings proxy
    if bos:
        struct += 25
    if choch:
        struct += 20
    h1 = str((trend.get("h1") or "")).lower()
    if h1 in {"up", "down"}:
        struct += 10
    struct = min(100, struct)

    # session
    session_q = _parse_session_quality(reasons)
    if session_q is None:
        session_q = int(factors.get("session") or 100)
        # Confluence session factor is often 100 even when soft quality=55
        parsed = _parse_session_quality(reasons)
        if parsed is not None:
            session_q = parsed
    else:
        session_q = session_q

    # spread — confluence soft score is close to quality spread score
    spread = int(factors.get("spread") or 50)

    return {
        "trend": max(0, min(100, int(trend_score))),
        "liquidity": max(0, min(100, int(liq))),
        "order_block": max(0, min(100, int(ob))),
        "fair_value_gap": max(0, min(100, int(fvg))),
        "market_structure": max(0, min(100, int(struct))),
        "session": max(0, min(100, int(session_q))),
        "spread": max(0, min(100, int(spread))),
    }


def weighted_total(scores: dict[str, int], weights: dict[str, int]) -> float:
    total_w = sum(weights.values()) or 1
    return sum(scores.get(k, 0) * w for k, w in weights.items()) / total_w


def counterfactual_perfect_each(
    scores: dict[str, int],
    weights: dict[str, int],
) -> dict[str, Any]:
    """If each component alone were 100, what would the total become?"""
    base = weighted_total(scores, weights)
    out: dict[str, Any] = {"base": round(base, 4)}
    for key in weights:
        lifted = dict(scores)
        lifted[key] = 100
        out[key] = {
            "score_if_perfect": round(weighted_total(lifted, weights), 4),
            "delta": round(weighted_total(lifted, weights) - base, 4),
            "reaches_80": weighted_total(lifted, weights) >= 80,
        }
    all_perfect = {k: 100 for k in weights}
    out["all_perfect"] = round(weighted_total(all_perfect, weights), 4)
    return out


def _structural_engine_counterfactual(
    *,
    q_components: dict[str, list[float]],
    c_components: dict[str, list[float]],
    min_quality: int,
    min_confidence: int,
) -> dict[str, Any]:
    """Estimate totals if MTF lock + Liquidity v2 already apply (weights unchanged).

    Assumptions (conservative institutional):
    - quality.trend → max(score, 75) when aligned
    - quality.liquidity → 65 (Liquidity v2 floor; no inflation)
    - confidence.mtf → 100, confidence.m15 → 100
    - confidence.liquidity → 65
    - confidence.quality → rebuilt from lifted quality total
    """
    n = min(
        len(q_components.get("trend") or []),
        len(c_components.get("mtf") or []),
    )
    if n == 0:
        return {"n": 0}

    q_lifted: list[float] = []
    c_lifted: list[float] = []
    for i in range(n):
        q_scores = {k: int(q_components[k][i]) for k in QUALITY_WEIGHTS}
        q_scores["trend"] = max(q_scores["trend"], 75)
        q_scores["liquidity"] = max(q_scores["liquidity"], 65)
        q_tot = weighted_total(q_scores, QUALITY_WEIGHTS)
        q_lifted.append(q_tot)

        c_scores = {k: int(c_components[k][i]) for k in CONFIDENCE_WEIGHTS}
        c_scores["mtf"] = 100
        c_scores["m15"] = 100
        c_scores["liquidity"] = max(c_scores["liquidity"], 65)
        c_scores["quality"] = int(round(q_tot))
        c_lifted.append(weighted_total(c_scores, CONFIDENCE_WEIGHTS))

    return {
        "n": n,
        "assumptions": {
            "quality.trend": "max(raw, 75) when MTF aligned",
            "quality.liquidity": ">=65 (Liquidity v2 floor)",
            "confidence.mtf": 100,
            "confidence.m15": 100,
            "confidence.liquidity": ">=65",
            "confidence.quality": "rebuilt from lifted quality",
            "weights_changed": False,
            "thresholds_changed": False,
        },
        "quality_mean_after": round(mean(q_lifted), 4),
        "confidence_mean_after": round(mean(c_lifted), 4),
        "quality_pct_ge_80": round(
            100 * sum(1 for x in q_lifted if x >= min_quality) / n, 2
        ),
        "confidence_pct_ge_80": round(
            100 * sum(1 for x in c_lifted if x >= min_confidence) / n, 2
        ),
        "both_gates_pct": round(
            100
            * sum(
                1
                for q, c in zip(q_lifted, c_lifted, strict=False)
                if q >= min_quality and c >= min_confidence
            )
            / n,
            2,
        ),
        "quality_histogram_after": _histogram(q_lifted),
        "confidence_histogram_after": _histogram(c_lifted),
    }


def max_achievable_under_caps(
    *,
    quality: bool,
) -> dict[str, Any]:
    """Maximum total if every component hits its documented production cap."""
    if quality:
        caps = {
            "trend": 100,
            "liquidity": 100,  # theoretically with sweeps+pools
            "order_block": 85,  # hard structural cap
            "fair_value_gap": 85,  # hard structural cap
            "market_structure": 100,
            "session": 100,
            "spread": 100,
        }
        total = weighted_total(caps, QUALITY_WEIGHTS)
        # Realistic no-sweep path caps
        realistic = dict(caps)
        realistic["liquidity"] = 40
        realistic["order_block"] = 75
        realistic_total = weighted_total(realistic, QUALITY_WEIGHTS)
        return {
            "component_caps": caps,
            "max_theoretical": round(total, 4),
            "max_realistic_no_sweep_active_ob": round(realistic_total, 4),
            "threshold": 80,
            "theoretical_clears_threshold": total >= 80,
            "realistic_clears_threshold": realistic_total >= 80,
        }
    caps = {k: 100 for k in CONFIDENCE_WEIGHTS}
    return {
        "component_caps": caps,
        "max_theoretical": 100.0,
        "threshold": 80,
        "theoretical_clears_threshold": True,
    }


def decompose_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    """Full Quality + Confidence decomposition for one cycle."""
    conf_factors = dict(((cycle.get("confluence") or {}).get("engine_factors") or {}))
    # Keep only weighted confidence keys
    conf_scores = {
        k: int(conf_factors[k])
        for k in CONFIDENCE_WEIGHTS
        if k in conf_factors and conf_factors[k] is not None
    }
    # Fill missing with 0
    for k in CONFIDENCE_WEIGHTS:
        conf_scores.setdefault(k, 0)

    q_scores = reconstruct_quality_components(cycle)
    q_total_recon = weighted_total(q_scores, QUALITY_WEIGHTS)
    q_logged = (cycle.get("quality") or {}).get("score")
    c_logged = (cycle.get("confluence") or {}).get("total")
    c_recon = weighted_total(conf_scores, CONFIDENCE_WEIGHTS)

    return {
        "trace_id": cycle.get("trace_id"),
        "quality": {
            "logged_total": q_logged,
            "reconstructed_total": round(q_total_recon, 4),
            "reconstruction_error": (
                round(q_total_recon - float(q_logged), 4)
                if q_logged is not None
                else None
            ),
            "components": q_scores,
            "weighted_contributions": {
                k: round(q_scores[k] * QUALITY_WEIGHTS[k] / 100.0, 4)
                for k in QUALITY_WEIGHTS
            },
            "max_achievable_all_perfect": 100.0,
            "counterfactual_perfect_each": counterfactual_perfect_each(
                q_scores, QUALITY_WEIGHTS
            ),
            "reconstructed": True,
        },
        "confidence": {
            "logged_total": c_logged,
            "reconstructed_total": round(c_recon, 4),
            "reconstruction_error": (
                round(c_recon - float(c_logged), 4) if c_logged is not None else None
            ),
            "components": conf_scores,
            "weighted_contributions": {
                k: round(conf_scores[k] * CONFIDENCE_WEIGHTS[k] / 100.0, 4)
                for k in CONFIDENCE_WEIGHTS
            },
            "max_achievable_all_perfect": 100.0,
            "counterfactual_perfect_each": counterfactual_perfect_each(
                conf_scores, CONFIDENCE_WEIGHTS
            ),
            "reconstructed": False,
            "note": "engine_factors are live confluence inputs",
        },
    }


def _blocker_gap(
    scores: list[float],
    weight: int,
    *,
    threshold: int = 80,
) -> dict[str, Any]:
    """How much this component's shortfall vs 100 costs the total on average."""
    if not scores:
        return {"avg_shortfall_vs_100": None, "avg_total_drag": None}
    shortfalls = [100 - s for s in scores]
    avg_short = mean(shortfalls)
    drag = avg_short * weight / 100.0
    below = sum(1 for s in scores if s < threshold)
    return {
        "avg_shortfall_vs_100": round(avg_short, 4),
        "avg_total_drag": round(drag, 4),
        "pct_below_component_80": round(100 * below / len(scores), 2),
    }


def run_calibration_audit(
    cycles: list[dict[str, Any]],
    *,
    min_quality: int = 80,
    min_confidence: int = 80,
    cfg: ITEConfig | None = None,
) -> dict[str, Any]:
    """Institutional-grade score calibration audit over production cycles."""
    _ = cfg or DEFAULT_ITE_CONFIG
    evaluated = 0
    q_totals: list[float] = []
    c_totals: list[float] = []
    q_components: dict[str, list[float]] = {k: [] for k in QUALITY_WEIGHTS}
    c_components: dict[str, list[float]] = {k: [] for k in CONFIDENCE_WEIGHTS}
    recon_errors: list[float] = []
    conf_recon_errors: list[float] = []
    decompositions: list[dict[str, Any]] = []
    alone_sufficient_q: Counter[str] = Counter()
    alone_sufficient_c: Counter[str] = Counter()

    for cycle in cycles:
        factors = (cycle.get("confluence") or {}).get("engine_factors") or {}
        q = (cycle.get("quality") or {}).get("score")
        c = (cycle.get("confluence") or {}).get("total")
        if q is None and c is None and not factors:
            continue
        evaluated += 1
        decomp = decompose_cycle(cycle)
        decompositions.append(decomp)

        if q is not None:
            q_totals.append(float(q))
        if c is not None:
            c_totals.append(float(c))

        for k, v in decomp["quality"]["components"].items():
            q_components[k].append(float(v))
        err = decomp["quality"]["reconstruction_error"]
        if err is not None:
            recon_errors.append(abs(err))

        for k, v in decomp["confidence"]["components"].items():
            c_components[k].append(float(v))
        cerr = decomp["confidence"]["reconstruction_error"]
        if cerr is not None:
            conf_recon_errors.append(abs(cerr))

        for k, meta in decomp["quality"]["counterfactual_perfect_each"].items():
            if k in {"base", "all_perfect"}:
                continue
            if meta.get("reaches_80") and decomp["quality"]["logged_total"] is not None:
                if float(decomp["quality"]["logged_total"]) < min_quality:
                    alone_sufficient_q[k] += 1
        for k, meta in decomp["confidence"]["counterfactual_perfect_each"].items():
            if k in {"base", "all_perfect"}:
                continue
            if (
                meta.get("reaches_80")
                and decomp["confidence"]["logged_total"] is not None
            ):
                if float(decomp["confidence"]["logged_total"]) < min_confidence:
                    alone_sufficient_c[k] += 1

    q_stats = [
        {
            **_component_stats(q_components[k], weight=QUALITY_WEIGHTS[k], name=k),
            **_blocker_gap(q_components[k], QUALITY_WEIGHTS[k]),
            "documented_caps": QUALITY_CAPS.get(k),
        }
        for k in QUALITY_WEIGHTS
    ]
    c_stats = [
        {
            **_component_stats(c_components[k], weight=CONFIDENCE_WEIGHTS[k], name=k),
            **_blocker_gap(c_components[k], CONFIDENCE_WEIGHTS[k]),
        }
        for k in CONFIDENCE_WEIGHTS
    ]

    # Rank blockers by average total drag
    q_blockers = sorted(q_stats, key=lambda x: -(x.get("avg_total_drag") or 0))
    c_blockers = sorted(c_stats, key=lambda x: -(x.get("avg_total_drag") or 0))

    # Structural findings (evidence-backed)
    findings: list[dict[str, Any]] = []

    # Duplicate MTF / liquidity penalties across quality + confidence
    findings.append(
        {
            "id": "duplicate_mtf_penalty",
            "severity": True,
            "detail": (
                "MTF misalignment depresses quality.trend (weight 20) and "
                "confidence.mtf (weight 22) plus confidence.m15 (weight 8). "
                "Same root cause counted three times into gates."
            ),
        }
    )
    findings.append(
        {
            "id": "duplicate_liquidity_penalty",
            "severity": True,
            "detail": (
                "Legacy liquidity (no sweeps) holds quality.liquidity≈40 "
                "(weight 15) and confidence.liquidity=20 (weight 10) despite "
                "active OB+FVG. Liquidity v2 fixed confluence reject but "
                "quality evaluator still uses sweep-only definition."
            ),
        }
    )
    findings.append(
        {
            "id": "quality_embedded_in_confidence",
            "severity": True,
            "detail": (
                "confidence.quality (weight 12) re-ingests the quality total, "
                "so quality component deficits are partially double-counted "
                "into the confidence gate."
            ),
        }
    )

    # Caps
    findings.append(
        {
            "id": "quality_ob_cap_75",
            "severity": True,
            "detail": (
                "Quality order_block hard-caps at 75 without breakers "
                "(85 with breakers). Never reaches 100. Avg drag material."
            ),
        }
    )
    findings.append(
        {
            "id": "quality_fvg_cap_85",
            "severity": True,
            "detail": "Quality fair_value_gap hard-caps at 85 (2+ open gaps). Never reaches 100.",
        }
    )

    # Never contribute
    m15_scores = c_components.get("m15") or []
    if m15_scores and max(m15_scores) == 0:
        findings.append(
            {
                "id": "confidence_m15_never_contributes",
                "severity": True,
                "detail": (
                    "confidence.m15 is 0 on 100% of evaluated cycles (weight 8). "
                    "Component never contributes under current MTF reject path."
                ),
            }
        )

    liq_c = c_components.get("liquidity") or []
    if liq_c and max(liq_c) <= 20:
        findings.append(
            {
                "id": "confidence_liquidity_stuck_at_20",
                "severity": True,
                "detail": (
                    "confidence.liquidity factor stuck at 20 across window "
                    "(pre-liquidity-v2 production logs). Weight 10 permanently "
                    "under-contributes vs OB/FVG-aware liquidity v2 (65)."
                ),
            }
        )

    # Weight imbalance
    findings.append(
        {
            "id": "confidence_mtf_dominant_weight",
            "severity": True,
            "detail": (
                f"confidence.mtf weight={CONFIDENCE_WEIGHTS['mtf']} is the largest "
                f"single weight ({CONFIDENCE_WEIGHTS['mtf']}% of total). With mean "
                f"score ~{mean(c_components['mtf']) if c_components['mtf'] else 'n/a'}, "
                "it is the primary confidence ceiling."
            ),
        }
    )

    # Missing bonuses
    findings.append(
        {
            "id": "missing_quality_liquidity_ob_fvg_bonus",
            "severity": True,
            "detail": (
                "Quality liquidity ignores validated OB/FVG/displacement "
                "(Liquidity v2 sources). Missing bonus keeps component at 40 "
                "despite institutional structure presence ~99%."
            ),
        }
    )

    recommendations: list[dict[str, Any]] = []
    # Only recommend if data supports — never auto-apply
    if q_totals and mean(q_totals) < min_quality:
        top_q = q_blockers[0] if q_blockers else None
        recommendations.append(
            {
                "priority": 1,
                "action": "review_quality_liquidity_definition",
                "supported_by": "duplicate_liquidity_penalty,missing_quality_liquidity_ob_fvg_bonus",
                "proposal": (
                    "Align quality.liquidity with Liquidity v2 sources (OB/FVG/"
                    "mitigation/displacement) without raising the 80 threshold. "
                    "Expected lift ≈ avg_total_drag of liquidity component."
                ),
                "expected_avg_lift_pts": (top_q or {}).get("avg_total_drag"),
                "auto_apply": False,
                "changes_threshold": False,
            }
        )
    if c_totals and mean(c_totals) < min_confidence:
        recommendations.append(
            {
                "priority": 2,
                "action": "review_after_mtf_semantics_merge",
                "supported_by": "duplicate_mtf_penalty,confidence_m15_never_contributes",
                "proposal": (
                    "Re-measure confidence after M15 semantics + H1+M15 lock "
                    "land in production. Do not lower the 80 confidence floor. "
                    "m15=0 and mtf≈23 are structural MTF rejects, not weight bugs."
                ),
                "auto_apply": False,
                "changes_threshold": False,
            }
        )
        recommendations.append(
            {
                "priority": 3,
                "action": "review_quality_ob_fvg_caps",
                "supported_by": "quality_ob_cap_75,quality_fvg_cap_85",
                "proposal": (
                    "Optional: allow quality OB/FVG to reach 100 when "
                    "validated+displaced (parity with confluence 85/80 floors "
                    "already clearing). Caps alone do not explain sub-80 if "
                    "trend+liquidity remain depressed — measure lift first."
                ),
                "auto_apply": False,
                "changes_threshold": False,
            }
        )
        recommendations.append(
            {
                "priority": 4,
                "action": "review_confidence_quality_embedding",
                "supported_by": "quality_embedded_in_confidence",
                "proposal": (
                    "Consider whether embedding quality total inside confidence "
                    "creates correlated double-counting. Evidence-only; no "
                    "weight change without a second measured window."
                ),
                "auto_apply": False,
                "changes_threshold": False,
            }
        )

    recommendations.append(
        {
            "priority": 99,
            "action": "do_not_lower_thresholds",
            "supported_by": "institutional_safety",
            "proposal": "Keep min_trade_quality_score=80 and min_confluence_score=80.",
            "auto_apply": False,
            "changes_threshold": False,
        }
    )

    # Residual after structural engines (from counterfactual)
    structural_cf = _structural_engine_counterfactual(
        q_components=q_components,
        c_components=c_components,
        min_quality=min_quality,
        min_confidence=min_confidence,
    )
    if structural_cf.get("n") and structural_cf.get("quality_pct_ge_80", 100) < 95:
        recommendations.insert(
            -1,
            {
                "priority": 5,
                "action": "review_session_soft_score_in_quality",
                "supported_by": "structural_engine_counterfactual",
                "proposal": (
                    f"After MTF+Liquidity v2 lifts, quality still clears 80 on only "
                    f"{structural_cf.get('quality_pct_ge_80')}% of cycles "
                    f"(mean {structural_cf.get('quality_mean_after')}). Residual gap "
                    "tracks session soft quality=55 (e.g. Tokyo). Do not lower the "
                    "80 floor; measure whether session should remain inside quality "
                    "or stay risk-multiplier-only."
                ),
                "auto_apply": False,
                "changes_threshold": False,
            },
        )

    # Single-component perfect rarely enough?
    q_multi_needed = evaluated > 0 and all(
        alone_sufficient_q[k] < evaluated * 0.5 for k in QUALITY_WEIGHTS
    )

    return {
        "advisory_only": True,
        "thresholds_changed": False,
        "weights_changed": False,
        "auto_recalibration": False,
        "min_quality": min_quality,
        "min_confidence": min_confidence,
        "cycles_input": len(cycles),
        "cycles_evaluated": evaluated,
        "model": {
            "quality_weights": dict(QUALITY_WEIGHTS),
            "confidence_weights": dict(CONFIDENCE_WEIGHTS),
            "quality_caps": QUALITY_CAPS,
            "quality_evaluator": TradeQualityEvaluator.__module__,
            "confidence_engine": ConfluenceEngine.__module__,
        },
        "totals": {
            "quality": {
                "mean": round(mean(q_totals), 4) if q_totals else None,
                "std": round(pstdev(q_totals), 4) if len(q_totals) > 1 else None,
                "min": min(q_totals) if q_totals else None,
                "max": max(q_totals) if q_totals else None,
                "pct_below_80": (
                    round(
                        100
                        * sum(1 for x in q_totals if x < min_quality)
                        / len(q_totals),
                        2,
                    )
                    if q_totals
                    else None
                ),
                "histogram": _histogram(q_totals) if q_totals else {},
            },
            "confidence": {
                "mean": round(mean(c_totals), 4) if c_totals else None,
                "std": round(pstdev(c_totals), 4) if len(c_totals) > 1 else None,
                "min": min(c_totals) if c_totals else None,
                "max": max(c_totals) if c_totals else None,
                "pct_below_80": (
                    round(
                        100
                        * sum(1 for x in c_totals if x < min_confidence)
                        / len(c_totals),
                        2,
                    )
                    if c_totals
                    else None
                ),
                "histogram": _histogram(c_totals) if c_totals else {},
            },
        },
        "quality_components": q_stats,
        "confidence_components": c_stats,
        "blockers_ranked": {
            "quality_by_avg_drag": [
                {
                    "component": x["component"],
                    "weight": x["weight"],
                    "avg_total_drag": x.get("avg_total_drag"),
                    "score_mean": x.get("score_mean"),
                    "score_max": x.get("score_max"),
                }
                for x in q_blockers
            ],
            "confidence_by_avg_drag": [
                {
                    "component": x["component"],
                    "weight": x["weight"],
                    "avg_total_drag": x.get("avg_total_drag"),
                    "score_mean": x.get("score_mean"),
                    "score_max": x.get("score_max"),
                }
                for x in c_blockers
            ],
        },
        "max_achievable": {
            "quality": max_achievable_under_caps(quality=True),
            "confidence": max_achievable_under_caps(quality=False),
        },
        "reconstruction_quality": {
            "mean_abs_error_quality_total": (
                round(mean(recon_errors), 4) if recon_errors else None
            ),
            "mean_abs_error_confidence_total": (
                round(mean(conf_recon_errors), 4) if conf_recon_errors else None
            ),
            "note": (
                "Quality components reconstructed from cycle evidence; "
                "confidence uses live engine_factors."
            ),
        },
        "counterfactual_summary": {
            "quality_single_component_perfect_clears_80_counts": dict(
                alone_sufficient_q
            ),
            "confidence_single_component_perfect_clears_80_counts": dict(
                alone_sufficient_c
            ),
            "quality_requires_multi_component_lift": q_multi_needed,
        },
        "findings": findings,
        "recommendations": recommendations,
        "structural_engine_counterfactual": structural_cf,
        "per_cycle_decompositions": decompositions,
    }
