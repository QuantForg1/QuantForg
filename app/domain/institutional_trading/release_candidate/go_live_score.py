"""Go Live Score 0–100 — recommend scale-up only above threshold."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
)


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, n))


def compute_go_live_score(
    *,
    checklist: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    live_stats: dict[str, Any] | None = None,
    smoke: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Weighted composite. Never auto-scales capital or flips production."""
    cfg = DEFAULT_RC1_CONFIG
    components: dict[str, float] = {
        "reliability": 50.0,
        "performance": 50.0,
        "risk": 50.0,
        "profitability": 50.0,
        "execution": 50.0,
        "health": 50.0,
        "calibration": 50.0,
    }

    if checklist:
        counts = checklist.get("counts") or {}
        total = sum(int(counts.get(k, 0)) for k in ("PASS", "WARNING", "FAIL")) or 1
        pass_n = int(counts.get("PASS", 0))
        fail_n = int(counts.get("FAIL", 0))
        components["reliability"] = _clamp(100.0 * pass_n / total - 25.0 * fail_n)
        components["health"] = components["reliability"]

    if smoke:
        sc = smoke.get("counts") or {}
        total = sum(int(sc.get(k, 0)) for k in ("PASS", "WARNING", "FAIL")) or 1
        components["health"] = _clamp(
            0.5 * components["health"]
            + 0.5 * (100.0 * int(sc.get("PASS", 0)) / total - 20.0 * int(sc.get("FAIL", 0)))
        )

    if validation:
        m = validation.get("metrics") or {}
        days = float(m.get("consecutive_successful_trading_days") or 0)
        day_score = _clamp(100.0 * days / max(1, cfg.recommended_evidence_days))
        components["reliability"] = _clamp(0.6 * components["reliability"] + 0.4 * day_score)

        lat = m.get("average_latency_ms")
        if lat is not None:
            # Lower latency → higher score (cap at 500ms = ~0)
            try:
                components["execution"] = _clamp(100.0 - float(lat) / 5.0)
            except (TypeError, ValueError):
                pass
        err = m.get("error_rate")
        if err is not None:
            try:
                components["execution"] = _clamp(
                    0.5 * components["execution"] + 0.5 * (100.0 - float(err) * 100.0)
                )
            except (TypeError, ValueError):
                pass

    stats = (live_stats or {}).get("live_statistics") or {}
    wr = stats.get("win_rate")
    pf = stats.get("profit_factor")
    dd = stats.get("current_drawdown")
    if wr is not None:
        try:
            components["profitability"] = _clamp(float(wr))
            components["performance"] = _clamp(float(wr))
        except (TypeError, ValueError):
            pass
    if pf is not None:
        try:
            # PF 1.0 → 50, PF 2.0 → 100
            components["profitability"] = _clamp(
                0.5 * components["profitability"] + 0.5 * (float(pf) * 50.0)
            )
        except (TypeError, ValueError):
            pass
    if dd is not None:
        try:
            # Lower drawdown better; 0% → 100, 20% → 0
            components["risk"] = _clamp(100.0 - abs(float(dd)) * 5.0)
        except (TypeError, ValueError):
            pass

    cal = stats.get("ai_calibration")
    if isinstance(cal, dict) and cal:
        components["calibration"] = 70.0
        if cal.get("well_calibrated") or cal.get("score"):
            try:
                components["calibration"] = _clamp(float(cal.get("score") or 70.0))
            except (TypeError, ValueError):
                components["calibration"] = 75.0

    weights = {
        "reliability": 0.20,
        "performance": 0.15,
        "risk": 0.15,
        "profitability": 0.15,
        "execution": 0.15,
        "health": 0.10,
        "calibration": 0.10,
    }
    overall = _clamp(sum(components[k] * weights[k] for k in weights))
    threshold = cfg.go_live_score_threshold
    recommend_scale = overall >= threshold

    return {
        "score": round(overall, 1),
        "threshold": threshold,
        "recommend_production_scale_up": recommend_scale,
        "recommendation": (
            "Scale-up eligible (manual approval still required)"
            if recommend_scale
            else "Do not scale capital — continue evidence collection"
        ),
        "components": {k: round(v, 1) for k, v in components.items()},
        "auto_scale_capital": False,
        "affects_production": False,
    }
