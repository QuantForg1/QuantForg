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
    "session_blocked": "Session blocked",
    "news_blackout": "News blackout",
    "spread_too_wide": "Spread too wide",
    "atr_elevated": "ATR elevated",
    "atr_too_low": "ATR too low",
    "drawdown_elevated": "Drawdown elevated",
    "NO_SNAPSHOT": "No market snapshot",
    "NO_MARKET_CONTEXT": "No market context",
}

_REASON_PRIORITY: tuple[str, ...] = (
    "session_blocked",
    "news_blackout",
    "spread_too_wide",
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
    trend = {"h4": "—", "h1": "—", "m15": "—", "m5": "—", "aligned": None, "score": None}
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
                (
                    100
                    if snapshot is not None and not snapshot.news.blocked
                    else 0
                ),
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
        components["smc"] = min(int(components["smc"]), 20)

    # Soft parse known codes from free-text decision_reasons.
    for raw in decision_reasons:
        s = str(raw)
        low = s.lower()
        for code in _REASON_LABELS:
            if code.replace("_", " ") in low or code in low:
                rejected_codes.append(code)

    ranked = _rank_rejection_codes(rejected_codes)
    executed = bool(forwarded_to_oms) or str(decision_action or "").upper() in {
        "BUY",
        "SELL",
    }
    rejected = (not executed) and (
        str(decision_action or "").upper() in {"NO_TRADE", "WATCH", ""}
        or cycle_outcome in {"no_trade", "no_snapshot", "aborted", "shadow"}
    )

    primary = ranked[0] if ranked else None
    secondary = ranked[1] if len(ranked) > 1 else None
    tertiary = ranked[2] if len(ranked) > 2 else None

    q_diff = (
        (quality_total - required_quality) if quality_total is not None else None
    )
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
        "executed": executed,
        "rejected": rejected,
        "trend": trend,
        "quality": {
            "score": quality_total,
            "required": required_quality,
            "difference": q_diff,
            "passed": (
                quality_total >= required_quality
                if quality_total is not None
                else None
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
            "approved_lots": diag.get("approved_lots"),
        },
        "atr": diag.get("atr"),
        "stop_distance": diag.get("stop_distance"),
        "risk_budget": diag.get("risk_budget"),
        "calculated_lots": diag.get("calculated_lots"),
        "advisory_only": True,
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
    """Advisory recommendations — never suggest lowering thresholds or forcing trades."""
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
        latest.get("quality", {}).get("required")
        if isinstance(latest, dict)
        else None
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
                "Latest cycle rejected because: " + " · ".join(f"❌ {x}" for x in labels[:3])
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
        # Post-promotion monitor (warning only; never auto-rollback).
        try:
            from app.application.services.threshold_promotion import observe_cycle

            observe_cycle(cycle)
        except Exception:
            pass
        # Experimental 75/75 monitor (100-eval report; never auto-promote).
        try:
            from app.application.services.experimental_threshold_profile import (
                observe_experimental_cycle,
            )

            observe_experimental_cycle(cycle)
        except Exception:
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
        insights = generate_smart_insights(stats, latest)
        return {
            "advisory_only": True,
            "mutates_engines": False,
            "window": window,
            "latest": latest,
            "cycles": list(reversed(recent)),  # newest first for Ops desk
            "statistics": stats,
            "smart_insights": insights,
            "thresholds": {
                "required_quality": int(self._config.min_trade_quality_score),
                "required_confluence": int(self._config.min_confluence_score),
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
