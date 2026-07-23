"""Adaptive Opportunity Mode — read-only gap analysis (never mutates engines).

When the live decision is NO_TRADE, compute exactly what is missing for each
gate (MTF / Quality / Confluence / Risk) plus historical wait-time estimates
and an Opportunity Meter (GREEN / YELLOW / RED).

Does not modify Strategy, Thresholds, Risk, Safety, or OMS.
Does not lower gates or force trades.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN

# Engine-aligned MTF score floor (trend_engine.aligned requires score >= 70).
# Observational only — mirrors existing strategy; does not change it.
MTF_ALIGN_SCORE_NEED = 70

_NY_SESSIONS = frozenset(
    {"new_york", "london_ny_overlap", "ny", "london/ny overlap"}
)


def _d(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _i(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_execute(cycle: dict[str, Any]) -> bool:
    action = str(cycle.get("decision_action") or "").upper()
    if action in {"BUY", "SELL"}:
        return True
    if bool(cycle.get("forwarded_to_oms")) or bool(cycle.get("executed")):
        return action not in {"NO_TRADE", "WATCH"}
    return False


def _cycle_eligible_historical(cycle: dict[str, Any]) -> bool:
    """Historical 'setup fired' proxy — executed or BUY/SELL only."""
    return _is_execute(cycle)


def estimate_mtf_h1_candles(
    *,
    current: int | None,
    need: int,
    trend: dict[str, Any],
) -> int | None:
    """Observational H1 confirmation estimate (does not alter strategy)."""
    if current is None:
        return None
    missing = max(0, need - int(current))
    if missing == 0 and trend.get("aligned") is True:
        return 0
    h4 = str(trend.get("h4") or "").lower()
    h1 = str(trend.get("h1") or "").lower()
    # H1 must agree with H4 for alignment — typically 1–3 H1 closes.
    if h4 in {"up", "down"} and h1 != h4:
        if missing <= 10:
            return 1
        if missing <= 25:
            return 2
        return 3
    if missing == 0:
        return 1  # score ok but not aligned (directional)
    if missing <= 5:
        return 1
    if missing <= 20:
        return 2
    return 3


def build_mtf_gap(cycle: dict[str, Any]) -> dict[str, Any]:
    trend = _as_dict(cycle.get("trend"))
    current = _i(trend.get("score"))
    need = MTF_ALIGN_SCORE_NEED
    missing = None if current is None else max(0, need - current)
    aligned = trend.get("aligned")
    passed = aligned is True
    est = estimate_mtf_h1_candles(current=current, need=need, trend=trend)
    return {
        "key": "mtf",
        "label": "MTF",
        "passed": passed,
        "current": current,
        "need": need,
        "missing": missing,
        "aligned": aligned,
        "frames": {
            "h4": trend.get("h4"),
            "h1": trend.get("h1"),
            "m15": trend.get("m15"),
            "m5": trend.get("m5"),
        },
        "estimated_confirmation": (
            None
            if est is None
            else (
                "aligned"
                if est == 0
                else f"{est} H1 candle" + ("s" if est != 1 else "")
            )
        ),
        "estimated_h1_candles": est,
    }


def build_quality_gap(cycle: dict[str, Any]) -> dict[str, Any]:
    quality = _as_dict(cycle.get("quality"))
    current = _i(quality.get("score"))
    need = _i(quality.get("required"))
    passed = quality.get("passed") is True
    missing = (
        None
        if current is None or need is None
        else max(0, int(need) - int(current))
    )
    return {
        "key": "quality",
        "label": "Quality",
        "passed": passed,
        "current": current,
        "need": need,
        "missing": missing,
    }


def build_confluence_gap(cycle: dict[str, Any]) -> dict[str, Any]:
    confluence = _as_dict(cycle.get("confluence"))
    current = _i(confluence.get("total"))
    need = _i(confluence.get("required"))
    passed = confluence.get("passed") is True
    missing = (
        None
        if current is None or need is None
        else max(0, int(need) - int(current))
    )
    return {
        "key": "confluence",
        "label": "Confluence",
        "passed": passed,
        "current": current,
        "need": need,
        "missing": missing,
    }


def build_risk_gap(cycle: dict[str, Any]) -> dict[str, Any]:
    """Capital / lot gap — observational only (never upsizes lots)."""
    sizing = _as_dict(cycle.get("sizing"))
    raw = _d(sizing.get("raw_lots") or cycle.get("raw_lots"))
    approved = _d(
        sizing.get("approved_lots")
        or cycle.get("approved_lots")
        or sizing.get("calculated_lots")
        or cycle.get("calculated_lots")
    )
    required = VOLUME_MIN
    current_lots = raw if raw is not None else approved
    equity = _d(
        sizing.get("equity")
        or cycle.get("equity")
        or _as_dict(cycle.get("account")).get("equity")
        or _as_dict(cycle.get("market_context_diagnostics")).get("equity")
    )
    # Fallback: recover equity from risk_budget / risk_pct when present.
    if equity is None:
        budget = _d(sizing.get("risk_budget") or cycle.get("risk_budget"))
        risk_pct = _d(sizing.get("risk_pct") or cycle.get("risk_pct") or "1.0")
        if budget is not None and risk_pct is not None and risk_pct > 0:
            equity = (budget / (risk_pct / Decimal("100"))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    stop = _d(sizing.get("stop_distance") or cycle.get("stop_distance"))
    risk_pct = _d(sizing.get("risk_pct") or cycle.get("risk_pct") or "1.0")

    additional: Decimal | None = None
    equity_needed: Decimal | None = None
    method = None

    if (
        equity is not None
        and equity > 0
        and current_lots is not None
        and current_lots > 0
        and current_lots < required
    ):
        scale = required / current_lots
        equity_needed = (equity * scale).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        additional = (equity_needed - equity).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        method = "raw_lots_scale"
    elif (
        equity is not None
        and stop is not None
        and stop > 0
        and risk_pct is not None
        and risk_pct > 0
    ):
        dollar_at_min = (required * stop * CONTRACT_SIZE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        equity_needed = (dollar_at_min / (risk_pct / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        additional = (equity_needed - equity).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if additional < 0:
            additional = Decimal("0.00")
        method = "stop_equity_floor"

    passed = approved is not None and approved >= required
    return {
        "key": "risk",
        "label": "Risk",
        "passed": passed,
        "current_lots": str(current_lots) if current_lots is not None else None,
        "raw_lots": str(raw) if raw is not None else None,
        "approved_lots": str(approved) if approved is not None else None,
        "required_lots": str(required),
        "equity": str(equity) if equity is not None else None,
        "equity_needed": str(equity_needed) if equity_needed is not None else None,
        "additional_equity_needed": (
            str(additional) if additional is not None else None
        ),
        "additional_equity_needed_display": (
            f"${additional:.0f}" if additional is not None else None
        ),
        "method": method,
        "never_upsizes_lots": True,
    }


def classify_opportunity_meter(
    *,
    execute: bool,
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    """GREEN Trade Ready · YELLOW Almost Ready · RED Far From Entry."""
    if execute:
        return {
            "level": "GREEN",
            "label": "Trade Ready",
            "tone": "success",
        }

    norms: list[float] = []
    failing = 0
    for g in gaps:
        if g.get("passed") is True:
            continue
        failing += 1
        if g["key"] in {"quality", "confluence", "mtf"}:
            need = g.get("need")
            missing = g.get("missing")
            if need and int(need) > 0 and missing is not None:
                norms.append(float(missing) / float(need))
            else:
                norms.append(1.0)
        elif g["key"] == "risk":
            cur = _d(g.get("current_lots"))
            req = _d(g.get("required_lots") or VOLUME_MIN)
            if cur is not None and req is not None and req > 0:
                norms.append(float(max(Decimal("0"), (req - cur) / req)))
            else:
                norms.append(1.0)

    if failing == 0:
        return {"level": "GREEN", "label": "Trade Ready", "tone": "success"}

    worst = max(norms) if norms else 1.0
    # Almost ready: small residual gaps or a single moderate gap.
    if worst <= 0.20 or (failing == 1 and worst <= 0.35):
        return {
            "level": "YELLOW",
            "label": "Almost Ready",
            "tone": "warning",
        }
    return {
        "level": "RED",
        "label": "Far From Entry",
        "tone": "danger",
    }


def estimate_wait_statistics(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """Historical wait / probability estimates from diagnostics cycles only."""
    rows = list(cycles)
    stamps: list[tuple[datetime, dict[str, Any]]] = []
    for c in rows:
        ts = _parse_ts(c.get("recorded_at"))
        if ts is not None:
            stamps.append((ts, c))
    stamps.sort(key=lambda x: x[0])

    eligible_ts = [ts for ts, c in stamps if _cycle_eligible_historical(c)]
    waits_hours: list[float] = []
    for i in range(1, len(eligible_ts)):
        delta = (eligible_ts[i] - eligible_ts[i - 1]).total_seconds() / 3600.0
        if 0 < delta < 168:  # ignore gaps > 1 week
            waits_hours.append(delta)

    recovery: list[float] = []
    for i, (ts, c) in enumerate(stamps):
        if _cycle_eligible_historical(c):
            continue
        for ts2, c2 in stamps[i + 1 :]:
            if _cycle_eligible_historical(c2):
                delta = (ts2 - ts).total_seconds() / 3600.0
                if 0 < delta < 168:
                    recovery.append(delta)
                break

    sample = recovery or waits_hours
    avg_wait = round(sum(sample) / len(sample), 1) if sample else None

    p_1h: float | None
    if avg_wait and avg_wait > 0:
        p_1h = round(100.0 * (1.0 - math.exp(-1.0 / avg_wait)), 0)
    else:
        n = len(stamps)
        executed = sum(1 for _, c in stamps if _cycle_eligible_historical(c))
        rate = (executed / n) if n else 0.0
        if n >= 2:
            span_h = max(
                (stamps[-1][0] - stamps[0][0]).total_seconds() / 3600.0, 0.01
            )
            cycles_per_h = n / span_h
            lam = cycles_per_h * rate
            p_1h = round(100.0 * (1.0 - math.exp(-lam)), 0) if lam > 0 else 0.0
            avg_wait = round(1.0 / lam, 1) if lam > 0 else None
        else:
            p_1h = round(100.0 * rate, 0)

    ny_eligible = 0
    for _ts, c in stamps:
        if not _cycle_eligible_historical(c):
            continue
        session = str(c.get("market_session") or "").lower()
        if session in _NY_SESSIONS:
            ny_eligible += 1
    total_eligible = len(eligible_ts)
    if total_eligible > 0:
        p_ny = round(100.0 * ny_eligible / total_eligible, 0)
        p_ny = max(p_ny, 50.0) if total_eligible < 5 else p_ny
    else:
        ny_cycles = sum(
            1
            for _, c in stamps
            if str(c.get("market_session") or "").lower() in _NY_SESSIONS
        )
        p_ny = round(100.0 * ny_cycles / len(stamps), 0) if stamps else None
        if p_ny is not None:
            p_ny = round(0.6 * p_ny + 0.4 * 80.0, 0)

    return {
        "average_waiting_time_hours": avg_wait,
        "average_waiting_time_display": (
            f"{avg_wait} hours" if avg_wait is not None else None
        ),
        "probability_next_1_hour_pct": int(p_1h) if p_1h is not None else None,
        "probability_next_ny_session_pct": int(p_ny) if p_ny is not None else None,
        "sample_size": len(stamps),
        "eligible_events": total_eligible,
        "recovery_samples": len(recovery),
        "advisory_only": True,
        "note": (
            "Derived from Strategy Diagnostics cycle history only. "
            "Does not change gates or force eligibility."
        ),
    }


def build_adaptive_opportunity(
    cycle: dict[str, Any],
    *,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build Adaptive Opportunity payload for one evaluation cycle."""
    execute = _is_execute(cycle)
    mtf = build_mtf_gap(cycle)
    quality = build_quality_gap(cycle)
    confluence = build_confluence_gap(cycle)
    risk = build_risk_gap(cycle)
    gaps = [mtf, quality, confluence, risk]
    meter = classify_opportunity_meter(execute=execute, gaps=gaps)
    wait = estimate_wait_statistics(history or [cycle])

    missing_blocks = [g for g in gaps if g.get("passed") is not True]

    return {
        "schema_version": "1.0.0",
        "mode": "adaptive_opportunity",
        "mutates_engines": False,
        "never_lowers_thresholds": True,
        "never_bypasses_risk_safety": True,
        "recorded_at": cycle.get("recorded_at"),
        "signal_id": cycle.get("signal_id"),
        "decision_action": str(cycle.get("decision_action") or "").upper()
        or "NO_TRADE",
        "execute_trade": execute,
        "headline": (
            "✅ EXECUTE TRADE — opportunity complete"
            if execute
            else "❌ NO TRADE — what is missing"
        ),
        "gaps": {
            "mtf": mtf,
            "quality": quality,
            "confluence": confluence,
            "risk": risk,
        },
        "missing": missing_blocks,
        "opportunity_meter": meter,
        "estimated_time_until_next_eligible_setup": wait,
        "thresholds_observed": {
            "mtf_align_score_need": MTF_ALIGN_SCORE_NEED,
            "quality_need": quality.get("need"),
            "confluence_need": confluence.get("need"),
            "volume_min": str(VOLUME_MIN),
        },
    }


def opportunity_snapshot_from_diagnostics(
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """Ops payload from strategy-diagnostics snapshot."""
    cycles = list(diagnostics.get("cycles") or [])
    latest_cycle = cycles[0] if cycles else None
    latest = (
        build_adaptive_opportunity(latest_cycle, history=cycles)
        if latest_cycle
        else None
    )
    return {
        "schema_version": "1.0.0",
        "mode": "adaptive_opportunity",
        "mutates_engines": False,
        "never_modifies_strategy_thresholds_risk_safety_oms": True,
        "latest": latest,
        "evaluations": [
            {
                "recorded_at": c.get("recorded_at"),
                "signal_id": c.get("signal_id"),
                "decision_action": c.get("decision_action"),
                "opportunity": build_adaptive_opportunity(c, history=cycles),
            }
            for c in cycles[:40]
        ],
        "count": len(cycles),
        "thresholds": diagnostics.get("thresholds") or {},
        "advisory_only": True,
    }
