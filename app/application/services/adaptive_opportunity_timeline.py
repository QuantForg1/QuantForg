"""Adaptive Opportunity Timeline — read-only evaluation history (never mutates).

Projects the last N Strategy Diagnostics cycles into a timeline of:
MTF · Quality · Confluence · Risk Lots · Opportunity Meter

Predicts Approaching Trade / Moving Away / Stable from recent score slopes.
Does not modify Strategy, Risk, Safety, Thresholds, or OMS.
"""

from __future__ import annotations

from typing import Any

from app.application.services.adaptive_opportunity import (
    MTF_ALIGN_SCORE_NEED,
    build_adaptive_opportunity,
    build_confluence_gap,
    build_mtf_gap,
    build_quality_gap,
    build_risk_gap,
)


def _i(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_execute(cycle: dict[str, Any]) -> bool:
    action = str(cycle.get("decision_action") or "").upper()
    if action in {"BUY", "SELL"}:
        return True
    if bool(cycle.get("forwarded_to_oms")) or bool(cycle.get("executed")):
        return action not in {"NO_TRADE", "WATCH"}
    return False

TIMELINE_MAX = 100
_PREDICT_WINDOW = 5  # recent points for slope (chronological)


def _meter_rank(level: str) -> int:
    return {"GREEN": 2, "YELLOW": 1, "RED": 0}.get(str(level).upper(), 0)


def _readiness_score(
    *,
    mtf: int | None,
    quality: int | None,
    confluence: int | None,
    risk_lots: float | None,
    q_need: int | None,
    c_need: int | None,
) -> float | None:
    """0–100 composite readiness for Opportunity Trend chart (observational)."""
    parts: list[float] = []
    if mtf is not None:
        parts.append(min(100.0, 100.0 * float(mtf) / float(MTF_ALIGN_SCORE_NEED)))
    if quality is not None and q_need and q_need > 0:
        parts.append(min(100.0, 100.0 * float(quality) / float(q_need)))
    if confluence is not None and c_need and c_need > 0:
        parts.append(min(100.0, 100.0 * float(confluence) / float(c_need)))
    if risk_lots is not None:
        parts.append(min(100.0, 100.0 * float(risk_lots) / 0.01))
    if not parts:
        return None
    return round(sum(parts) / len(parts), 1)


def cycle_to_timeline_point(cycle: dict[str, Any]) -> dict[str, Any]:
    """One stored evaluation row for the Opportunity Timeline."""
    opp = build_adaptive_opportunity(cycle)
    mtf_g = build_mtf_gap(cycle)
    q_g = build_quality_gap(cycle)
    c_g = build_confluence_gap(cycle)
    r_g = build_risk_gap(cycle)
    meter = opp["opportunity_meter"]

    lots_raw = r_g.get("current_lots") or r_g.get("raw_lots") or r_g.get("approved_lots")
    lots_f = float(lots_raw) if lots_raw is not None else None
    mtf_s = mtf_g.get("current")
    q_s = q_g.get("current")
    c_s = c_g.get("current")

    readiness = _readiness_score(
        mtf=_i(mtf_s),
        quality=_i(q_s),
        confluence=_i(c_s),
        risk_lots=lots_f,
        q_need=_i(q_g.get("need")),
        c_need=_i(c_g.get("need")),
    )

    return {
        "recorded_at": cycle.get("recorded_at"),
        "signal_id": cycle.get("signal_id"),
        "decision_action": str(cycle.get("decision_action") or "").upper()
        or "NO_TRADE",
        "execute_trade": _is_execute(cycle),
        "mtf_score": mtf_s,
        "quality": q_s,
        "confluence": c_s,
        "risk_lots": lots_raw,
        "risk_lots_num": lots_f,
        "opportunity_meter": meter.get("level"),
        "opportunity_meter_label": meter.get("label"),
        "opportunity_meter_rank": _meter_rank(str(meter.get("level") or "RED")),
        "readiness_score": readiness,
        "session": cycle.get("market_session"),
    }


def _slope(values: list[float]) -> float | None:
    """Simple least-squares slope vs index 0..n-1."""
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values, strict=True))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


def predict_trajectory(
    points_chrono: list[dict[str, Any]],
) -> dict[str, Any]:
    """Predict Approaching Trade / Moving Away / Stable from recent MTF (+ readiness).

    Uses last ``_PREDICT_WINDOW`` chronological points. Observational only.
    """
    window = points_chrono[-_PREDICT_WINDOW:]
    mtf_vals = [float(p["mtf_score"]) for p in window if p.get("mtf_score") is not None]
    ready_vals = [
        float(p["readiness_score"])
        for p in window
        if p.get("readiness_score") is not None
    ]

    mtf_seq = [int(p["mtf_score"]) for p in window if p.get("mtf_score") is not None]
    mtf_slope = _slope(mtf_vals)
    ready_slope = _slope(ready_vals)

    primary_slope = mtf_slope
    if primary_slope is None:
        primary_slope = ready_slope
    elif ready_slope is not None and abs(primary_slope) < 0.35:
        primary_slope = 0.6 * primary_slope + 0.4 * (ready_slope / 5.0)

    approaching = primary_slope is not None and primary_slope >= 0.8
    weakening = primary_slope is not None and primary_slope <= -0.8

    if len(mtf_seq) >= 3:
        ups = sum(1 for i in range(1, len(mtf_seq)) if mtf_seq[i] > mtf_seq[i - 1])
        downs = sum(1 for i in range(1, len(mtf_seq)) if mtf_seq[i] < mtf_seq[i - 1])
        steps = len(mtf_seq) - 1
        if ups >= steps and mtf_seq[-1] > mtf_seq[0]:
            approaching = True
            weakening = False
        elif downs >= steps and mtf_seq[-1] < mtf_seq[0]:
            weakening = True
            approaching = False

    latest = points_chrono[-1] if points_chrono else None
    near_gate = (
        latest is not None
        and latest.get("mtf_score") is not None
        and int(latest["mtf_score"]) >= MTF_ALIGN_SCORE_NEED - 5
        and approaching
    )

    if approaching:
        direction = "Approaching Trade"
        label = (
            "Likely Trade Soon"
            if near_gate or (mtf_seq and mtf_seq[-1] >= 65)
            else "Approaching Trade"
        )
    elif weakening:
        direction = "Moving Away"
        label = "Setup Weakening"
    else:
        direction = "Stable"
        label = "Stable"

    arrow_path = " → ".join(str(v) for v in mtf_seq) if mtf_seq else None

    return {
        "direction": direction,
        "label": label,
        "mtf_sequence": mtf_seq,
        "mtf_path_display": arrow_path,
        "mtf_slope": round(mtf_slope, 3) if mtf_slope is not None else None,
        "readiness_slope": round(ready_slope, 3) if ready_slope is not None else None,
        "window": len(window),
        "advisory_only": True,
        "note": (
            "Prediction from recent evaluation slopes only. "
            "Does not change gates or force trades."
        ),
    }


def build_series(points_chrono: list[dict[str, Any]]) -> dict[str, Any]:
    """Chart-ready series (oldest → newest)."""

    def _series(key: str, num_key: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, p in enumerate(points_chrono):
            raw = p.get(num_key) if num_key else p.get(key)
            if raw is None and num_key:
                raw = p.get(key)
            if raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            ts = str(p.get("recorded_at") or "")
            label = ts[11:16] if len(ts) >= 16 else str(i)
            out.append({"i": i, "t": p.get("recorded_at"), "v": val, "label": label})
        return out

    return {
        "mtf": _series("mtf_score"),
        "quality": _series("quality"),
        "confluence": _series("confluence"),
        "risk_lots": _series("risk_lots", "risk_lots_num"),
        "opportunity": _series("readiness_score"),
        "opportunity_meter_rank": _series("opportunity_meter_rank"),
    }


def build_opportunity_timeline(
    cycles_newest_first: list[dict[str, Any]],
    *,
    limit: int = TIMELINE_MAX,
) -> dict[str, Any]:
    """Full Opportunity Timeline payload from diagnostics cycles."""
    window = max(1, min(int(limit or TIMELINE_MAX), TIMELINE_MAX))
    recent = list(cycles_newest_first)[:window]
    chrono_cycles = list(reversed(recent))
    points_chrono = [cycle_to_timeline_point(c) for c in chrono_cycles]
    points_newest = list(reversed(points_chrono))
    prediction = predict_trajectory(points_chrono)
    series = build_series(points_chrono)

    return {
        "schema_version": "1.0.0",
        "mode": "adaptive_opportunity_timeline",
        "mutates_engines": False,
        "never_modifies_strategy_risk_safety_thresholds_oms": True,
        "window": window,
        "count": len(points_chrono),
        "points": points_newest,
        "points_chronological": points_chrono,
        "series": series,
        "prediction": prediction,
        "latest": points_newest[0] if points_newest else None,
        "advisory_only": True,
    }


def timeline_snapshot_from_diagnostics(
    diagnostics: dict[str, Any],
    *,
    limit: int = TIMELINE_MAX,
) -> dict[str, Any]:
    cycles = list(diagnostics.get("cycles") or [])
    payload = build_opportunity_timeline(cycles, limit=limit)
    payload["thresholds"] = diagnostics.get("thresholds") or {}
    return payload
