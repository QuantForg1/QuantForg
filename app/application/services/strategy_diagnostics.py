"""Strategy Diagnostics — read-only NO_TRADE observation (never mutates engines).

Records per-cycle quality, confluence components, MTF trend, and rejection
reasons for Operations → Strategy Diagnostics. Does not alter strategy, risk,
safety, OMS, or MT5 execution paths.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import TradeDecision
from app.domain.institutional_trading.models import MarketAnalysisSnapshot

# Human labels for Ops desk (diagnosis only — not decision codes).
_REASON_LABELS: dict[str, str] = {
    "quality_below_threshold": "Quality below threshold",
    "confidence_below_threshold": "Confluence below threshold",
    "mtf_not_aligned": "MTF misalignment",
    "m15_not_confirming": "M15 not confirming",
    "no_structure_event": "No BOS/CHOCH structure event",
    "no_liquidity_context": "No liquidity context",
    "no_active_order_block": "No active order block",
    "no_open_fvg": "No open fair value gap",
    "no_smc_zone": "No SMC zone (OB + FVG)",
    "session_blocked": "Market window closed (weekend/off-hours)",
    "market_window_closed": "Market window closed (weekend/off-hours)",
    "news_blackout": "News blackout",
    "spread_too_wide": "Spread too wide",
    "atr_elevated": "ATR elevated",
    "atr_too_low": "ATR too low",
    "drawdown_elevated": "Drawdown elevated",
    "below_min_lot": "Lot size below broker minimum",
    "MIN_LOT_CONSTRAINT": (
        "VALID_SIGNAL blocked: calculated volume below broker volume_min"
    ),
    "SAFETY_BLOCKED": "Auto-trade safety gate blocked",
    "NO_SNAPSHOT": "No market snapshot",
    "NO_MARKET_CONTEXT": "No market context",
    "WAIT_NO_SNIPER_TRIGGER": "WAIT — no liquidity event or structure confirmation",
    "WAIT_INSUFFICIENT_RR": "WAIT — RR too low",
    "WAIT_CHASE": "WAIT — chase detected",
    "WAIT_NO_INVALIDATION": "WAIT — invalidation invalid",
    "WAIT_CONFLICT": "WAIT — BUY/SELL conflict",
    "WAIT_ABNORMAL_SPREAD": "WAIT — abnormal spread",
    "WAIT_STALE_DATA": "WAIT — stale data",
    "OPPORTUNITY_SCORE_BELOW_THRESHOLD": "WAIT — opportunity score below threshold",
    "SETUP_NOT_READY": "WAIT — opportunity score below threshold",
}

_REASON_PRIORITY: tuple[str, ...] = (
    "SAFETY_BLOCKED",
    "market_window_closed",
    "session_blocked",
    "news_blackout",
    "spread_too_wide",
    "below_min_lot",
    "MIN_LOT_CONSTRAINT",
    "mtf_not_aligned",
    "quality_below_threshold",
    "confidence_below_threshold",
    "no_smc_zone",
    "m15_not_confirming",
    "no_structure_event",
    "no_liquidity_context",
    "no_active_order_block",
    "no_open_fvg",
    "atr_elevated",
    "atr_too_low",
    "drawdown_elevated",
    "NO_SNAPSHOT",
    "NO_MARKET_CONTEXT",
    "WAIT_NO_SNIPER_TRIGGER",
    "OPPORTUNITY_SCORE_BELOW_THRESHOLD",
)


def reason_label(code: str) -> str:
    if code in _REASON_LABELS:
        return _REASON_LABELS[code]
    cleaned = code.replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Unknown"


def _trend_value(obj: Any) -> str:
    if obj is None:
        return "—"
    val = getattr(obj, "value", None)
    return str(val) if val is not None else str(obj)


def _volume_score(volume: Any) -> int | None:
    """Advisory volume presence score — not a confluence factor."""
    if volume is None or volume == "":
        return None
    try:
        v = float(volume)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return 0
    if v < 10:
        return 40
    if v < 50:
        return 70
    return 100


def _structure_component_scores(
    snapshot: MarketAnalysisSnapshot,
) -> tuple[int, int, int]:
    """Derive BOS / CHOCH / SMC display scores from snapshot (read-only)."""
    structure = snapshot.primary_structure
    bos_n = len(structure.breaks_of_structure) if structure else 0
    choch_n = len(structure.changes_of_character) if structure else 0
    bos = 90 if bos_n else 0
    choch = 90 if choch_n else 0

    ob = snapshot.order_blocks
    active_ob = 0
    if ob:
        from app.domain.order_block.enums import OrderBlockState

        active_ob = sum(
            1
            for b in ob.order_blocks
            if b.state in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
        )
    fvg = snapshot.fair_value_gaps
    open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
    ob_score = 85 if active_ob else 20
    fvg_score = 80 if open_fvg else 25
    smc = round((ob_score + fvg_score) / 2)
    if active_ob == 0 and open_fvg == 0:
        smc = min(smc, 20)
    return bos, choch, smc


def _rank_rejection_codes(codes: list[str]) -> list[str]:
    seen: list[str] = []
    for code in codes:
        c = str(code).strip()
        if c and c not in seen:
            seen.append(c)
    priority_index = {k: i for i, k in enumerate(_REASON_PRIORITY)}
    seen.sort(key=lambda c: (priority_index.get(c, 999), c))
    return seen


def extract_cycle_diagnostics(
    *,
    snapshot: MarketAnalysisSnapshot | None,
    decision: TradeDecision | None,
    cycle_outcome: str,
    decision_action: str | None,
    abort_reason: str | None = None,
    decision_reasons: tuple[str, ...] | list[str] = (),
    market_context_diagnostics: dict[str, Any] | None = None,
    signal_id: str | None = None,
    forwarded_to_oms: bool = False,
    trace_id: str | None = None,
    config: ITEConfig | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Build one diagnostic cycle record from existing decision artefacts."""
    cfg = config or DEFAULT_ITE_CONFIG
    diag = dict(market_context_diagnostics or {})
    now = as_of or datetime.now(UTC)

    required_quality = int(cfg.min_trade_quality_score)
    required_confluence = int(cfg.min_confluence_score)

    session = "—"
    session_allowed: bool | None = None
    trend: dict[str, Any] = {
        "h4": "—",
        "h1": "—",
        "m15": "—",
        "m5": "—",
        "aligned": None,
        "score": None,
    }
    quality_total: int | None = None
    confluence_total: int | None = None
    factors_raw: dict[str, int] = {}
    rejected_codes: list[str] = []

    if snapshot is not None:
        session = snapshot.session.session.value
        session_allowed = bool(snapshot.session.allowed)
        t = snapshot.trend
        trend = {
            "h4": _trend_value(t.macro_bias),
            "h1": _trend_value(t.primary),
            "m15": _trend_value(t.entry),
            "m5": _trend_value(t.execution),
            "aligned": bool(t.aligned),
            "score": int(t.alignment_score),
            "market_regime": getattr(t, "market_regime", "unknown"),
            "mtf_policy": getattr(t, "mtf_policy", "v1"),
            "mtf_contributions": dict(getattr(t, "mtf_contributions", {}) or {}),
            "h4_is_context": bool(getattr(t, "h4_is_context", False)),
            "trade_bias": (
                t.trade_bias.value
                if getattr(t, "trade_bias", None) is not None
                else None
            ),
            "m15_semantics": dict(getattr(t, "m15_semantics", {}) or {}),
        }
        quality_total = int(snapshot.trade_quality.total)
        bos_s, choch_s, smc_s = _structure_component_scores(snapshot)
    else:
        bos_s = choch_s = smc_s = 0
        session = str(diag.get("trading_session") or diag.get("session") or "—")
        if "session_allowed" in diag:
            session_allowed = bool(diag["session_allowed"])

    if decision is not None:
        confluence_total = int(decision.confidence)
        quality_total = int(decision.quality)
        factors_raw = dict(decision.confluence.factors or {})
        rejected_codes.extend(str(r) for r in decision.confluence.rejected_rules)
        rejected_codes.extend(str(r) for r in decision.eligibility.rejection_reasons)
        if not signal_id:
            signal_id = str(decision.id)
        if not decision_action:
            decision_action = decision.action.value

    # Component board for Ops (maps engine factors + derived BOS/CHOCH/SMC/volume).
    volume_raw = diag.get("volume")
    vol_score = _volume_score(volume_raw)
    if factors_raw:
        ob_f = int(factors_raw.get("order_block", 0))
        fvg_f = int(factors_raw.get("fvg", 0))
        smc_display = round((ob_f + fvg_f) / 2)
    else:
        smc_display = int(smc_s)
    components = {
        "smc": smc_display,
        "liquidity_sweep": int(factors_raw.get("liquidity", 0)),
        "bos": int(bos_s),
        "choch": int(choch_s),
        "order_block": int(factors_raw.get("order_block", 0)),
        "fair_value_gap": int(factors_raw.get("fvg", 0)),
        "trend_alignment": int(factors_raw.get("mtf", trend.get("score") or 0)),
        "volume": vol_score,
        "news_filter": int(
            factors_raw.get(
                "news",
                (100 if snapshot is not None and not snapshot.news.blocked else 0),
            )
        ),
    }
    if snapshot is not None and not factors_raw:
        components["order_block"] = 85 if smc_s >= 50 else 20
        components["fair_value_gap"] = 80 if smc_s >= 50 else 25
        components["liquidity_sweep"] = 0
        components["trend_alignment"] = int(trend.get("score") or 0)
        components["news_filter"] = 0 if snapshot.news.blocked else 100
        components["smc"] = int(smc_s)

    if abort_reason:
        rejected_codes.append(str(abort_reason))
    if cycle_outcome in {"no_snapshot"} and "NO_SNAPSHOT" not in rejected_codes:
        rejected_codes.append("NO_SNAPSHOT")
    if "no_smc_zone" in rejected_codes:
        components["smc"] = min(int(components.get("smc") or 0), 20)

    # Soft parse known codes from free-text decision_reasons.
    for raw in decision_reasons:
        s = str(raw)
        low = s.lower()
        if (
            "min_lot_constraint" in low
            or "below_min_lot" in low
            or "below broker min" in low
            or "below broker volume_min" in low
        ):
            if "min_lot_constraint" in low or "volume_min" in low:
                rejected_codes.append("MIN_LOT_CONSTRAINT")
            else:
                rejected_codes.append("below_min_lot")
        for code in _REASON_LABELS:
            if code.replace("_", " ") in low or code in low:
                rejected_codes.append(code)

    ranked = _rank_rejection_codes(rejected_codes)
    action_u = str(decision_action or "").upper()
    take = action_u in {"BUY", "SELL"}
    executed = bool(forwarded_to_oms)
    rejected = (not take) and (
        action_u in {"NO_TRADE", "WATCH", "WAIT", ""}
        or cycle_outcome in {"no_trade", "no_snapshot", "aborted", "shadow", "wait"}
    )

    primary = ranked[0] if ranked else None
    secondary = ranked[1] if len(ranked) > 1 else None
    tertiary = ranked[2] if len(ranked) > 2 else None

    q_diff = (quality_total - required_quality) if quality_total is not None else None
    c_diff = (
        (confluence_total - required_confluence)
        if confluence_total is not None
        else None
    )

    return {
        "recorded_at": now.isoformat(),
        "trace_id": trace_id,
        "signal_id": signal_id,
        "market_session": session,
        "session_allowed": session_allowed,
        "cycle_outcome": cycle_outcome,
        "decision_action": decision_action,
        "forwarded_to_oms": bool(forwarded_to_oms),
        "take": take,
        "executed": executed,
        "rejected": rejected,
        "trend": trend,
        "quality": {
            "score": quality_total,
            "required": required_quality,
            "difference": q_diff,
            "passed": (
                quality_total >= required_quality if quality_total is not None else None
            ),
        },
        "confluence": {
            "total": confluence_total,
            "required": required_confluence,
            "difference": c_diff,
            "passed": (
                confluence_total >= required_confluence
                if confluence_total is not None
                else None
            ),
            "components": components,
            "engine_factors": dict(factors_raw),
        },
        "rejection": {
            "primary": primary,
            "secondary": secondary,
            "tertiary": tertiary,
            "primary_label": reason_label(primary) if primary else None,
            "secondary_label": reason_label(secondary) if secondary else None,
            "tertiary_label": reason_label(tertiary) if tertiary else None,
            "all_codes": ranked,
            "all_labels": [reason_label(c) for c in ranked],
            "decision_reasons": [str(r) for r in decision_reasons],
        },
        "volume_raw": str(volume_raw) if volume_raw is not None else None,
        "sizing": {
            "atr": diag.get("atr"),
            "stop_distance": diag.get("stop_distance"),
            "risk_budget": diag.get("risk_budget"),
            "risk_pct": diag.get("risk_pct"),
            "raw_lots": diag.get("raw_lots"),
            "calculated_lots": diag.get("calculated_lots"),
            "calculated_lot": diag.get("raw_lots") or diag.get("calculated_lots"),
            "broker_min_lot": diag.get("broker_min_lot"),
            "broker_minimum": diag.get("broker_min_lot"),
            "account_balance": diag.get("equity") or diag.get("balance"),
            "risk_percentage": diag.get("risk_pct"),
            "approved_lots": diag.get("approved_lots"),
            "sizing_status": diag.get("sizing_status"),
        },
        "atr": diag.get("atr"),
        "stop_distance": diag.get("stop_distance"),
        "risk_budget": diag.get("risk_budget"),
        "calculated_lots": diag.get("calculated_lots"),
        "opportunity_score": diag.get("opportunity_score"),
        "opportunity_threshold": diag.get("opportunity_threshold") or 70,
        "setup_state": diag.get("setup_state"),
        "sniper_state": diag.get("sniper_state") or diag.get("sniper"),
        "advisory_only": True,
    }


def hourly_scan_rates(
    cycles: list[dict[str, Any]],
    *,
    span_seconds: float = 3600.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Hourly discovery vs execution rates. Observation only — never forces trades."""
    moment = now or datetime.now(UTC)
    subset: list[dict[str, Any]] = []
    for row in cycles:
        raw = row.get("recorded_at")
        ts: datetime | None = None
        if isinstance(raw, datetime):
            ts = raw if raw.tzinfo else raw.replace(tzinfo=UTC)
        elif raw:
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                ts = None
        if ts is None or (moment - ts.astimezone(UTC)).total_seconds() <= span_seconds:
            subset.append(row)
    hours = span_seconds / 3600.0 if span_seconds else 1.0

    def _rate(n: int) -> float:
        return round(n / hours, 2) if hours else 0.0

    wait_reasons: Counter[str] = Counter()
    buy_n = sell_n = wait_n = take_n = exec_n = cand_n = ready_n = 0
    chase_n = conflict_n = spread_n = rr_n = min_lot_n = 0
    risk_n = safety_n = oms_n = 0
    for row in subset:
        action = str(row.get("decision_action") or row.get("action") or "").upper()
        if action == "BUY":
            buy_n += 1
        elif action == "SELL":
            sell_n += 1
        elif action in {"WAIT", "NO_TRADE", "WATCH", ""}:
            wait_n += 1
        if bool(row.get("take")) or action in {"BUY", "SELL"}:
            take_n += 1
        if bool(row.get("forwarded_to_oms")):
            exec_n += 1
        opp = row.get("opportunity_score")
        try:
            if opp is not None and int(opp) >= int(
                row.get("opportunity_threshold") or 70
            ):
                cand_n += 1
        except (TypeError, ValueError):
            pass
        setup = str(row.get("setup_state") or "").upper()
        if setup in {"SETUP_READY", "TAKE"}:
            ready_n += 1
        rej = row.get("rejection") if isinstance(row.get("rejection"), dict) else {}
        code = str(rej.get("primary") or row.get("abort_reason") or "").upper()
        if code:
            wait_reasons[code] += 1
            if "CHASE" in code:
                chase_n += 1
            if "CONFLICT" in code:
                conflict_n += 1
            if "SPREAD" in code:
                spread_n += 1
            if "RR" in code or "INSUFFICIENT_RR" in code:
                rr_n += 1
            if "MIN_LOT" in code:
                min_lot_n += 1
            if "DAILY_LOSS" in code or code.startswith("RISK"):
                risk_n += 1
            if "SAFETY" in code or "KILL" in code:
                safety_n += 1
            if "OMS" in code or "DUPLICATE" in code:
                oms_n += 1
    scans = len(subset)
    return {
        "window_seconds": span_seconds,
        "sample_limited": True,
        "scans": scans,
        "scans_per_hour": _rate(scans),
        "candidate_setups": cand_n,
        "candidate_setups_per_hour": _rate(cand_n),
        "setup_ready_count": ready_n,
        "take_count": take_n,
        "take_per_hour": _rate(take_n),
        "executed_count": exec_n,
        "executions_per_hour": _rate(exec_n),
        "BUY_count": buy_n,
        "SELL_count": sell_n,
        "WAIT_count": wait_n,
        "WAIT_CHASE_count": chase_n,
        "WAIT_CONFLICT_count": conflict_n,
        "WAIT_SPREAD_count": spread_n,
        "WAIT_RR_count": rr_n,
        "MIN_LOT_INFEASIBLE_count": min_lot_n,
        "risk_reject_count": risk_n,
        "safety_reject_count": safety_n,
        "oms_reject_count": oms_n,
        "wait_reasons": dict(wait_reasons.most_common(8)),
        "note": (
            "Rates are from the in-memory diagnostics ring. Empty buckets mean "
            "history is not in the ring — not zero opportunity. TAKE is not an "
            "MT5 fill; executed_count requires OMS forward."
        ),
    }


def compute_diagnostics_statistics(
    cycles: list[dict[str, Any]],
    *,
    window: int = 100,
) -> dict[str, Any]:
    """Aggregate last N diagnostic cycles (observation only)."""
    rows = list(cycles)[-window:]
    n = len(rows)
    generated = sum(1 for r in rows if r.get("signal_id") or r.get("decision_action"))
    rejected = sum(1 for r in rows if r.get("rejected"))
    executed = sum(1 for r in rows if r.get("executed"))
    # Prefer counting cycles that had a decision artefact as "signals generated".
    signals_generated = sum(
        1
        for r in rows
        if r.get("signal_id")
        or str(r.get("decision_action") or "").upper()
        in {"NO_TRADE", "WATCH", "BUY", "SELL"}
    )
    qualities = [
        int(r["quality"]["score"])
        for r in rows
        if isinstance(r.get("quality"), dict) and r["quality"].get("score") is not None
    ]
    confluences = [
        int(r["confluence"]["total"])
        for r in rows
        if isinstance(r.get("confluence"), dict)
        and r["confluence"].get("total") is not None
    ]
    counter: Counter[str] = Counter()
    for r in rows:
        rej = r.get("rejection") if isinstance(r.get("rejection"), dict) else {}
        code = rej.get("primary") if isinstance(rej, dict) else None
        if code:
            counter[str(code)] += 1
        elif r.get("rejected"):
            counter["unspecified"] += 1

    top = [
        {
            "code": code,
            "label": reason_label(code),
            "count": count,
            "share_pct": round(100.0 * count / rejected, 1) if rejected else 0.0,
        }
        for code, count in counter.most_common(8)
    ]
    execution_rate = round(100.0 * executed / n, 1) if n else 0.0
    return {
        "window": window,
        "cycles_in_window": n,
        "signals_generated": signals_generated or generated,
        "signals_rejected": rejected,
        "signals_executed": executed,
        "execution_rate_pct": execution_rate,
        "average_quality": (
            round(sum(qualities) / len(qualities), 1) if qualities else None
        ),
        "average_confluence": (
            round(sum(confluences) / len(confluences), 1) if confluences else None
        ),
        "top_rejection_reasons": top,
    }


def generate_smart_insights(
    stats: dict[str, Any],
    latest: dict[str, Any] | None,
) -> list[str]:
    """Advisory recommendations — never suggest lowering thresholds or forcing trades."""  # noqa: E501
    insights: list[str] = []
    top = list(stats.get("top_rejection_reasons") or [])
    if not stats.get("cycles_in_window"):
        insights.append(
            "No diagnostic cycles recorded yet. Wait for the ITE loop to produce "
            "snapshots — this desk only observes existing decisions."
        )
        return insights

    rejected = int(stats.get("signals_rejected") or 0)
    executed = int(stats.get("signals_executed") or 0)
    generated = int(stats.get("signals_generated") or 0)
    rate = stats.get("execution_rate_pct")

    if generated and rejected == generated and executed == 0:
        insights.append(
            "All observed signals in the window resolved to NO_TRADE / non-execution. "
            "Diagnosis only — thresholds and engines are unchanged."
        )

    if top:
        lead = top[0]
        insights.append(
            f"Most signals fail because: {lead.get('label')} "
            f"({lead.get('count')} of {rejected} rejects, {lead.get('share_pct')}%)."
        )
        if len(top) >= 2:
            insights.append(
                f"Secondary driver: {top[1].get('label')} "
                f"({top[1].get('count')} rejects)."
            )

    avg_q = stats.get("average_quality")
    avg_c = stats.get("average_confluence")
    req_q = (
        latest.get("quality", {}).get("required") if isinstance(latest, dict) else None
    ) or DEFAULT_ITE_CONFIG.min_trade_quality_score
    req_c = (
        latest.get("confluence", {}).get("required")
        if isinstance(latest, dict)
        else None
    ) or DEFAULT_ITE_CONFIG.min_confluence_score

    if avg_q is not None and avg_q < req_q:
        gap = round(float(req_q) - float(avg_q), 1)
        insights.append(
            f"Average quality ({avg_q}) sits {gap} below required ({req_q}). "
            "Improve structure/liquidity/OB/FVG inputs — do not lower the gate."
        )
    if avg_c is not None and avg_c < req_c:
        gap = round(float(req_c) - float(avg_c), 1)
        insights.append(
            f"Average confluence ({avg_c}) sits {gap} below required ({req_c}). "
            "Focus on MTF alignment and SMC zone presence."
        )

    if latest and isinstance(latest.get("rejection"), dict):
        labels = list(latest["rejection"].get("all_labels") or [])
        if labels:
            insights.append(
                "Latest cycle rejected because: "
                + " · ".join(f"❌ {x}" for x in labels[:3])
            )

    if rate is not None:
        insights.append(
            f"Execution rate over last {stats.get('cycles_in_window')} cycles: {rate}% "
            f"({executed} executed / {stats.get('cycles_in_window')} cycles)."
        )

    insights.append(
        "This desk diagnoses only. It never lowers thresholds, bypasses risk/safety, "
        "or opens trades."
    )
    return insights


@dataclass
class StrategyDiagnosticsStore:
    """In-memory ring buffer of the last 100 diagnostic cycles."""

    maxlen: int = 100
    _cycles: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)

    def __post_init__(self) -> None:
        self._cycles = deque(maxlen=self.maxlen)

    def record(self, cycle: dict[str, Any]) -> None:
        with self._lock:
            self._cycles.append(dict(cycle))
        # Durable per-cycle evidence (every scan — including NO_TRADE rejects)
        try:
            from app.application.services.cycle_evidence import record_cycle_evidence

            rejection = cycle.get("rejection") if isinstance(cycle, dict) else None
            reasons: list[str] = []
            if isinstance(rejection, dict):
                reasons.extend(str(r) for r in (rejection.get("all_codes") or []))
                reasons.extend(
                    str(r) for r in (rejection.get("decision_reasons") or [])
                )
            sizing = (
                cycle.get("sizing") if isinstance(cycle.get("sizing"), dict) else None
            )
            record_cycle_evidence(
                cycle_outcome=str(cycle.get("cycle_outcome") or ""),
                decision_action=(
                    str(cycle.get("decision_action"))
                    if cycle.get("decision_action") is not None
                    else None
                ),
                reasons=reasons,
                abort_reason=(
                    str(rejection.get("primary"))
                    if isinstance(rejection, dict) and rejection.get("primary")
                    else None
                ),
                session=(
                    str(cycle.get("market_session"))
                    if cycle.get("market_session") not in {None, "—"}
                    else None
                ),
                quality_score=(
                    (cycle.get("quality") or {}).get("score")
                    if isinstance(cycle.get("quality"), dict)
                    else None
                ),
                confluence_score=(
                    (cycle.get("confluence") or {}).get("total")
                    if isinstance(cycle.get("confluence"), dict)
                    else None
                ),
                forwarded_to_oms=bool(cycle.get("forwarded_to_oms")),
                trace_id=(
                    str(cycle.get("trace_id")) if cycle.get("trace_id") else None
                ),
                sizing=sizing,
            )
        except Exception:  # noqa: S110  # best-effort evidence path
            pass
        # AI Decision Engine v2 rejection telemetry (advisory; never mutates gates)
        try:
            if cycle.get("rejected"):
                from app.application.services.decision_v2_telemetry import (
                    record_rejection_telemetry,
                )
                from types import SimpleNamespace

                trend = (
                    cycle.get("trend") if isinstance(cycle.get("trend"), dict) else {}
                )
                conf = (
                    cycle.get("confluence")
                    if isinstance(cycle.get("confluence"), dict)
                    else {}
                )
                factors = (
                    conf.get("engine_factors")
                    if isinstance(conf.get("engine_factors"), dict)
                    else {}
                )
                rejection = (
                    cycle.get("rejection")
                    if isinstance(cycle.get("rejection"), dict)
                    else {}
                )
                trend_ns = SimpleNamespace(
                    macro_bias=trend.get("h4"),
                    primary=trend.get("h1"),
                    entry=trend.get("m15"),
                    execution=trend.get("m5"),
                    alignment_score=trend.get("score"),
                    aligned=trend.get("aligned"),
                    market_regime=trend.get("market_regime"),
                    mtf_contributions=trend.get("mtf_contributions") or {},
                    h4_is_context=trend.get("h4_is_context", False),
                )
                record_rejection_telemetry(
                    trend=trend_ns,
                    quality_score=(
                        (cycle.get("quality") or {}).get("score")
                        if isinstance(cycle.get("quality"), dict)
                        else None
                    ),
                    confidence_score=conf.get("total"),
                    liquidity_score=factors.get("liquidity"),
                    rejected_rules=list(rejection.get("all_codes") or []),
                    primary_reason=(
                        str(rejection.get("primary"))
                        if rejection.get("primary")
                        else None
                    ),
                    min_quality=int(self._config.min_trade_quality_score),
                    min_confidence=int(self._config.min_confluence_score),
                    scalping=self._config.is_scalping(),
                    trace_id=(
                        str(cycle.get("trace_id")) if cycle.get("trace_id") else None
                    ),
                )
        except Exception:  # noqa: S110  # best-effort telemetry path
            pass
        # M15 Trend Semantics v2 telemetry (advisory; never mutates gates)
        try:
            from app.application.services.m15_semantics_telemetry import (
                build_m15_semantics_telemetry,
                get_m15_semantics_telemetry_store,
            )
            import re

            trend = cycle.get("trend") if isinstance(cycle.get("trend"), dict) else {}
            conf = (
                cycle.get("confluence")
                if isinstance(cycle.get("confluence"), dict)
                else {}
            )
            factors = (
                conf.get("engine_factors")
                if isinstance(conf.get("engine_factors"), dict)
                else {}
            )
            rejection = (
                cycle.get("rejection")
                if isinstance(cycle.get("rejection"), dict)
                else {}
            )
            reasons = list(rejection.get("decision_reasons") or [])
            latest_bos = None
            for r in reasons:
                m = re.search(r"Latest BOS trend=(\w+)", str(r), re.I)
                if m:
                    latest_bos = m.group(1)
                    break
            has_ob = int(factors.get("order_block") or 0) >= 80 or any(
                "active order blocks=" in str(r).lower() for r in reasons
            )
            has_fvg = int(factors.get("fvg") or 0) >= 70 or any(
                "open fvgs=" in str(r).lower() for r in reasons
            )
            has_bos = any("structure events" in str(r).lower() for r in reasons) or (
                latest_bos is not None
            )
            event = build_m15_semantics_telemetry(
                h4=trend.get("h4"),
                h1=trend.get("h1"),
                m15=trend.get("m15"),
                m5=trend.get("m5"),
                latest_bos=latest_bos,
                has_ob=has_ob,
                has_fvg=has_fvg,
                has_bos=has_bos,
                quality_score=(
                    (cycle.get("quality") or {}).get("score")
                    if isinstance(cycle.get("quality"), dict)
                    else None
                ),
                confidence_score=conf.get("total"),
                min_quality=int(self._config.min_trade_quality_score),
                min_confidence=int(self._config.min_confluence_score),
                scalping=self._config.is_scalping(),
                trace_id=(
                    str(cycle.get("trace_id")) if cycle.get("trace_id") else None
                ),
                live_semantics=trend.get("m15_semantics") or None,
            )
            get_m15_semantics_telemetry_store().record(event)
        except Exception:  # noqa: S110  # best-effort telemetry path
            pass
        # Post-promotion monitor (warning only; never auto-rollback).
        try:
            from app.application.services.threshold_promotion import observe_cycle

            observe_cycle(cycle)
        except Exception:  # noqa: S110  # best-effort optional path
            pass
        # Experimental 75/75 monitor (100-eval report; never auto-promote).
        try:
            from app.application.services.experimental_threshold_profile import (
                observe_experimental_cycle,
            )

            observe_experimental_cycle(cycle)
        except Exception:  # noqa: S110  # best-effort optional path
            pass

    def record_from_artefacts(self, **kwargs: Any) -> dict[str, Any]:
        cycle = extract_cycle_diagnostics(config=self._config, **kwargs)
        self.record(cycle)
        return cycle

    def snapshot(self, *, limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            cycles = list(self._cycles)
        window = limit if limit is not None else self.maxlen
        window = max(1, min(int(window), self.maxlen))
        recent = cycles[-window:]
        latest = recent[-1] if recent else None
        stats = compute_diagnostics_statistics(recent, window=window)
        hourly = hourly_scan_rates(recent)
        insights = generate_smart_insights(stats, latest)
        from app.application.services.live_execution_explain import (
            enrich_cycles_with_explain,
        )

        cycles_newest_first = list(reversed(recent))
        explained = enrich_cycles_with_explain(cycles_newest_first)
        return {
            "advisory_only": True,
            "mutates_engines": False,
            "window": window,
            "latest": explained[0] if explained else None,
            "cycles": explained,
            "statistics": stats,
            "hourly": hourly,
            "smart_insights": insights,
            "thresholds": {
                "required_quality": int(self._config.min_trade_quality_score),
                "required_confluence": int(self._config.min_confluence_score),
            },
            "live_execution_explain": {
                "latest": (explained[0].get("explain") if explained else None),
                "count": len(explained),
            },
        }


_STORE: StrategyDiagnosticsStore | None = None
_STORE_LOCK = Lock()


def get_strategy_diagnostics_store() -> StrategyDiagnosticsStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = StrategyDiagnosticsStore()
        return _STORE


def reset_strategy_diagnostics_store() -> None:
    """Test helper — clears the singleton."""
    global _STORE
    with _STORE_LOCK:
        _STORE = StrategyDiagnosticsStore()
