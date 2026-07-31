"""Read-only AI Decision Engine rejection analysis (evidence only).

Never mutates thresholds, risk, OMS, or MT5. Aggregates durable cycle
evidence JSONL + in-memory Strategy Diagnostics + AI Scalping diagnostics.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

FILTER_FAMILIES: tuple[str, ...] = (
    "mtf_alignment",
    "ai_quality",
    "confidence",
    "confluence",
    "liquidity",
    "spread",
    "atr_volatility",
    "session",
    "news",
    "risk_sizing",
    "structure_pa",
    "momentum",
    "other",
)

_CODE_TO_FAMILY: dict[str, str] = {
    "mtf_not_aligned": "mtf_alignment",
    "m15_not_confirming": "mtf_alignment",
    "entry_tf_not_confirming": "mtf_alignment",
    "quality_below_threshold": "ai_quality",
    "ai_quality_reject": "ai_quality",
    "confidence_below_threshold": "confidence",
    "no_liquidity_context": "liquidity",
    "spread_too_wide": "spread",
    "spread_reject": "spread",
    "atr_elevated": "atr_volatility",
    "atr_too_low": "atr_volatility",
    "session_blocked": "session",
    "session_gate": "session",
    "market_window_closed": "session",
    "news_blackout": "news",
    "below_min_lot": "risk_sizing",
    "SAFETY_BLOCKED": "risk_sizing",
    "safety_blocked": "risk_sizing",
    "NO_SNAPSHOT": "other",
    "NO_MARKET_CONTEXT": "other",
    "no_structure_event": "structure_pa",
    "no_active_order_block": "structure_pa",
    "no_open_fvg": "structure_pa",
    "no_smc_zone": "structure_pa",
    "ai_check_fail:strong_structure": "structure_pa",
    "ai_check_fail:high_liquidity": "liquidity",
    "ai_check_fail:momentum_confirmation": "momentum",
    "ai_check_fail:tight_spread": "spread",
    "ai_check_fail:valid_volatility": "atr_volatility",
    "ai_check_fail:session_quality": "session",
    "ai_check_fail:adaptive_confidence": "confidence",
    "ai_check_fail:adaptive_quality": "ai_quality",
    "ai_check_fail:pa_confluence": "confluence",
    "ai_check_fail:min_rr": "risk_sizing",
    "ai_check_fail:clear_direction": "other",
}

_AI_CHECK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"weak structure|structure score", "ai_check_fail:strong_structure"),
    (r"insufficient liquidity|liquidity score", "ai_check_fail:high_liquidity"),
    (r"momentum .*no confirmation|momentum \d+", "ai_check_fail:momentum_confirmation"),
    (r"spread reject|spread too wide", "ai_check_fail:tight_spread"),
    (r"volatility too compressed|invalid volatility|atr%", "ai_check_fail:valid_volatility"),
    (r"session quality .*★", "ai_check_fail:session_quality"),
    (r"confidence \d+ < adaptive", "ai_check_fail:adaptive_confidence"),
    (r"trade quality \d+ < adaptive", "ai_check_fail:adaptive_quality"),
    (r"pa confluence \d+", "ai_check_fail:pa_confluence"),
    (r"expected rr .*below minimum", "ai_check_fail:min_rr"),
    (r"no clear buy/sell", "ai_check_fail:clear_direction"),
)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _is_soft_observation(text: str) -> bool:
    """Soft score / weighting lines are observational — not hard NO_TRADE causes."""
    low = text.lower()
    if "reject only above" in low or "soft score" in low or "soft-ok" in low:
        return True
    if "soft-weighted" in low or "riskx=" in low:
        return True
    if "atr" in low and ("acceptable" in low or "of price acceptable" in low):
        return True
    if "news protection disabled" in low or "fail-open" in low or "no reliable calendar" in low:
        return True
    if "m15 structure events" in low or "latest bos" in low:
        return True
    if "active order blocks=" in low or "open fvgs=" in low:
        return True
    return False


def _family_from_text(text: str) -> str | None:
    low = text.lower()
    if "ignored_action" in low or _is_soft_observation(text):
        return None
    if "mtf" in low or "not aligned" in low:
        return "mtf_alignment"
    if "confidence" in low and ("<" in low or "below" in low or "adaptive" in low):
        return "confidence"
    if "confluence" in low and ("below" in low or "failed" in low or "<" in low):
        return "confluence"
    if "trade quality" in low or ("quality" in low and ("below" in low or "gate" in low)):
        return "ai_quality"
    if "liquidity" in low and ("insufficient" in low or "no_liquidity" in low or "score" in low):
        return "liquidity"
    if "spread" in low and ("reject" in low or "too wide" in low) and "reject only above" not in low:
        return "spread"
    if ("atr" in low or "volatil" in low or "compression" in low) and (
        "too" in low or "invalid" in low or "elevated" in low or "compress" in low or "reject" in low
    ):
        return "atr_volatility"
    if "session" in low and (
        "closed" in low or "weekend" in low or "off_hours" in low or "blocked" in low
    ):
        return "session"
    if "news" in low and ("blackout" in low or "blocked" in low):
        return "news"
    if "below_min_lot" in low or "broker min" in low or "margin" in low:
        return "risk_sizing"
    if "momentum" in low and ("<" in low or "no confirmation" in low):
        return "momentum"
    if "weak structure" in low or "structure score" in low or "pa confluence" in low:
        return "structure_pa"
    if "ai quality gates rejected" in low:
        return "ai_quality"
    if "eligibility failed" in low:
        return "other"
    return None


def _soft_family_from_text(text: str) -> str | None:
    """Classify soft/observational filter mentions (not hard rejects)."""
    if not _is_soft_observation(text):
        return None
    low = text.lower()
    if "spread" in low:
        return "spread"
    if "atr" in low or "volatil" in low:
        return "atr_volatility"
    if "session" in low:
        return "session"
    if "news" in low:
        return "news"
    return None


def _parse_metrics_from_reasons(reasons: list[str]) -> dict[str, float | None]:
    spread_abs: float | None = None
    atr_pct: float | None = None
    for raw in reasons:
        m = re.search(r"spread\s+([\d.]+)\s+elevated", raw, re.I)
        if m and spread_abs is None:
            spread_abs = _safe_float(m.group(1))
        m = re.search(r"atr\s+([\d.]+)\s*%", raw, re.I)
        if m and atr_pct is None:
            atr_pct = _safe_float(m.group(1))
    return {"spread": spread_abs, "atr_pct": atr_pct}


def _infer_ai_check_codes(reasons: list[str]) -> list[str]:
    codes: list[str] = []
    for raw in reasons:
        low = raw.lower()
        for pattern, code in _AI_CHECK_PATTERNS:
            if re.search(pattern, low):
                if code not in codes:
                    codes.append(code)
    return codes


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or limit <= 0:
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        logger.warning("decision_analysis_jsonl_read_failed", path=str(path), error=str(exc))
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _normalize_from_diagnostics_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    trend = cycle.get("trend") or {}
    quality = cycle.get("quality") or {}
    conf = cycle.get("confluence") or {}
    factors = conf.get("engine_factors") or {}
    components = conf.get("components") or {}
    rejection = cycle.get("rejection") or {}
    sizing = cycle.get("sizing") or {}
    reasons = [str(r) for r in (rejection.get("decision_reasons") or [])]
    codes = [str(c) for c in (rejection.get("all_codes") or []) if str(c).strip()]
    if rejection.get("primary") and str(rejection["primary"]) not in codes:
        codes.insert(0, str(rejection["primary"]))
    for code in _infer_ai_check_codes(reasons):
        if code not in codes:
            codes.append(code)
    parsed = _parse_metrics_from_reasons(reasons)
    stage_fails = [
        s.get("key")
        for s in ((cycle.get("explain") or {}).get("stages") or [])
        if isinstance(s, dict) and str(s.get("status")).upper() == "FAIL"
    ]
    # Risk stage often fails with approved_lots=0 as a cascade of NO_TRADE —
    # only treat as risk_sizing when an explicit risk/sizing code exists.
    hard_risk = any(
        c in {"below_min_lot", "SAFETY_BLOCKED", "safety_blocked", "drawdown_elevated"}
        for c in codes
    )
    if "risk" in stage_fails and not hard_risk:
        stage_fails = [s for s in stage_fails if s != "risk"]

    return {
        "source": "strategy_diagnostics",
        "recorded_at": cycle.get("recorded_at"),
        "trace_id": cycle.get("trace_id") or cycle.get("signal_id"),
        "decision_action": cycle.get("decision_action"),
        "rejected": bool(cycle.get("rejected", True)),
        "session": cycle.get("market_session"),
        "quality_score": _safe_int(quality.get("score")),
        "confluence_score": _safe_int(conf.get("total")),
        "mtf_score": _safe_int(trend.get("score") if trend.get("score") is not None else factors.get("mtf")),
        "mtf_aligned": bool(trend.get("aligned")) if trend.get("aligned") is not None else None,
        "ai_confidence": None,
        "liquidity_score": _safe_int(factors.get("liquidity") or components.get("liquidity_sweep")),
        "spread_score": _safe_int(factors.get("spread")),
        "spread": parsed.get("spread"),
        "atr": _safe_float(cycle.get("atr") or sizing.get("atr")),
        "atr_pct": parsed.get("atr_pct"),
        "session_score": _safe_int(factors.get("session")),
        "news_score": _safe_int(factors.get("news") or components.get("news_filter")),
        "risk_pct": _safe_float(sizing.get("risk_pct")),
        "approved_lots": _safe_float(sizing.get("approved_lots")),
        "primary_code": rejection.get("primary"),
        "codes": codes,
        "reasons": reasons,
        "stage_fails": stage_fails,
        "engine_factors": dict(factors) if isinstance(factors, dict) else {},
    }


def _normalize_from_jsonl(row: dict[str, Any]) -> dict[str, Any]:
    mctx = row.get("market_context") or {}
    reasons = [str(r) for r in (row.get("reasons") or [])]
    primary = row.get("primary_reason")
    codes: list[str] = []
    if primary:
        codes.append(str(primary))
    for r in reasons:
        if re.fullmatch(r"[A-Za-z0-9_]{3,64}", r.strip()) and r not in codes:
            codes.append(r)
    for code in _infer_ai_check_codes(reasons):
        if code not in codes:
            codes.append(code)
    parsed = _parse_metrics_from_reasons(reasons)
    return {
        "source": "cycle_evidence_jsonl",
        "recorded_at": row.get("recorded_at"),
        "trace_id": row.get("trace_id"),
        "decision_action": row.get("decision_action"),
        "rejected": bool(row.get("rejected", True)),
        "session": row.get("session") or mctx.get("trading_session"),
        "quality_score": _safe_int(row.get("quality_score")),
        "confluence_score": _safe_int(row.get("confluence_score")),
        "mtf_score": _safe_int(mctx.get("mtf_score")),
        "mtf_aligned": (
            bool(mctx.get("mtf_aligned")) if mctx.get("mtf_aligned") is not None else None
        ),
        "ai_confidence": _safe_int(mctx.get("ai_confidence")),
        "liquidity_score": _safe_int(mctx.get("liquidity_score")),
        "spread_score": _safe_int(mctx.get("spread_score")),
        "spread": _safe_float(mctx.get("spread") if mctx.get("spread") is not None else parsed.get("spread")),
        "atr": _safe_float(mctx.get("atr")),
        "atr_pct": _safe_float(mctx.get("atr_pct") if mctx.get("atr_pct") is not None else parsed.get("atr_pct")),
        "session_score": _safe_int(mctx.get("session_score")),
        "news_score": _safe_int(mctx.get("news_score")),
        "risk_pct": _safe_float(mctx.get("risk_pct") or (row.get("sizing") or {}).get("risk_pct")),
        "approved_lots": _safe_float((row.get("sizing") or {}).get("approved_lots")),
        "primary_code": str(primary) if primary else None,
        "codes": codes,
        "reasons": reasons,
        "stage_fails": [],
        "engine_factors": {},
    }


def _normalize_from_ai_diag(event: dict[str, Any]) -> dict[str, Any]:
    details = event.get("details") or {}
    reason = str(event.get("reason") or "")
    reasons = [reason] if reason else []
    reasons.extend(str(r) for r in (details.get("reasons") or []) if str(r).strip())
    checks = details.get("quality_checks") or details.get("checks") or {}
    codes: list[str] = []
    for key, ok in checks.items() if isinstance(checks, dict) else []:
        if ok is False:
            codes.append(f"ai_check_fail:{key}")
    if event.get("outcome") == "rejected":
        if "ai_quality_reject" not in codes:
            codes.insert(0, "ai_quality_reject")
    for code in _infer_ai_check_codes(reasons):
        if code not in codes:
            codes.append(code)
    factors = details.get("factors") or {}
    return {
        "source": "ai_scalping_diagnostics",
        "recorded_at": event.get("at") or event.get("recorded_at"),
        "trace_id": event.get("id"),
        "decision_action": "NO_TRADE" if event.get("outcome") == "rejected" else "TAKEN",
        "rejected": event.get("outcome") == "rejected",
        "session": details.get("session"),
        "quality_score": _safe_int(details.get("trade_quality") or details.get("quality")),
        "confluence_score": _safe_int(details.get("confluence") or details.get("pa_confluence")),
        "mtf_score": _safe_int(factors.get("mtf") if isinstance(factors, dict) else None),
        "mtf_aligned": None,
        "ai_confidence": _safe_int(details.get("ai_confidence") or event.get("confidence")),
        "liquidity_score": _safe_int(details.get("liquidity")),
        "spread_score": _safe_int(details.get("spread_score")),
        "spread": _safe_float(details.get("spread")),
        "atr": None,
        "atr_pct": _safe_float(details.get("atr_pct")),
        "session_score": _safe_int(factors.get("session") if isinstance(factors, dict) else None),
        "news_score": None,
        "risk_pct": None,
        "approved_lots": None,
        "primary_code": codes[0] if codes else None,
        "codes": codes,
        "reasons": reasons,
        "stage_fails": [],
        "quality_checks": checks if isinstance(checks, dict) else {},
        "engine_factors": dict(factors) if isinstance(factors, dict) else {},
    }


def _dedupe_events(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Prefer richest record per trace/time; keep newest first up to limit."""
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def richness(ev: dict[str, Any]) -> int:
        score = 0
        for k in (
            "quality_score",
            "confluence_score",
            "mtf_score",
            "ai_confidence",
            "liquidity_score",
            "spread_score",
            "atr",
            "atr_pct",
            "spread",
        ):
            if ev.get(k) is not None:
                score += 2
        score += min(len(ev.get("codes") or []), 6)
        score += min(len(ev.get("reasons") or []), 6)
        src = str(ev.get("source") or "")
        if "strategy_diagnostics" in src:
            score += 3
        if "ai_scalping_diagnostics" in src:
            score += 2
        return score

    for ev in events:
        key = str(ev.get("trace_id") or "")
        if not key:
            key = f"{ev.get('recorded_at')}|{ev.get('source')}|{ev.get('quality_score')}"
        if key not in by_key:
            by_key[key] = ev
            order.append(key)
            continue
        if richness(ev) < richness(by_key[key]):
            # Still merge missing scalar fields from poorer record
            merged = dict(by_key[key])
            for k, v in ev.items():
                if merged.get(k) in (None, [], {}) and v not in (None, [], {}):
                    merged[k] = v
            by_key[key] = merged
            continue
        merged = dict(by_key[key])
        for k, v in ev.items():
            if v is None:
                continue
            if merged.get(k) in (None, [], {}):
                merged[k] = v
            elif k in {"codes", "reasons", "stage_fails"} and isinstance(v, list):
                seen = set(merged.get(k) or [])
                for item in v:
                    if item not in seen:
                        merged.setdefault(k, []).append(item)
                        seen.add(item)
        if ev.get("ai_confidence") is not None:
            merged["ai_confidence"] = ev["ai_confidence"]
        if ev.get("atr_pct") is not None:
            merged["atr_pct"] = ev["atr_pct"]
        if ev.get("quality_checks"):
            merged["quality_checks"] = ev["quality_checks"]
        merged["source"] = f"{by_key[key].get('source')}+{ev.get('source')}"
        by_key[key] = merged

    ordered = sorted(order, key=lambda k: str(by_key[k].get("recorded_at") or ""), reverse=True)
    return [by_key[k] for k in ordered[:limit]]


def analyze_decision_rejections(*, limit: int = 1000) -> dict[str, Any]:
    """Aggregate last N evaluation cycles into rejection statistics + Pareto."""
    limit = max(1, min(int(limit), 5000))
    raw_events: list[dict[str, Any]] = []

    jsonl_path: str | None = None
    jsonl_exists = False
    jsonl_bytes = 0
    try:
        from app.application.services.cycle_evidence import _evidence_path

        path = _evidence_path()
        jsonl_path = str(path)
        jsonl_exists = path.exists()
        jsonl_bytes = path.stat().st_size if path.exists() else 0
        for row in _read_jsonl_tail(path, limit):
            if row.get("event") == "trade_rejected":
                raw_events.append(
                    {
                        "source": "rejection_log",
                        "recorded_at": row.get("recorded_at"),
                        "trace_id": row.get("trace_id"),
                        "decision_action": "NO_TRADE",
                        "rejected": True,
                        "session": row.get("session"),
                        "quality_score": None,
                        "confluence_score": None,
                        "mtf_score": None,
                        "primary_code": row.get("code"),
                        "codes": [row.get("code")] if row.get("code") else [],
                        "reasons": list(row.get("reasons") or []),
                        "stage_fails": [],
                        "risk_pct": _safe_float((row.get("sizing") or {}).get("risk_pct")),
                        "spread": None,
                        "atr": _safe_float((row.get("sizing") or {}).get("atr")),
                        "ai_confidence": None,
                        "liquidity_score": None,
                        "spread_score": None,
                        "atr_pct": None,
                        "session_score": None,
                        "news_score": None,
                        "approved_lots": None,
                        "mtf_aligned": None,
                        "engine_factors": {},
                    }
                )
            else:
                raw_events.append(_normalize_from_jsonl(row))
    except Exception as exc:
        logger.warning("decision_analysis_jsonl_failed", error=str(exc))

    diag_stats: dict[str, Any] = {}
    try:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        snap = get_strategy_diagnostics_store().snapshot(limit=min(limit, 2000))
        for cycle in snap.get("cycles") or []:
            if isinstance(cycle, dict):
                raw_events.append(_normalize_from_diagnostics_cycle(cycle))
        diag_stats = snap.get("statistics") or {}
    except Exception as exc:
        logger.warning("decision_analysis_diagnostics_failed", error=str(exc))

    ai_jsonl_exists = False
    ai_jsonl_bytes = 0
    try:
        from app.domain.institutional_trading.ai_scalping.diagnostics import (
            get_scalping_diagnostics_store,
        )

        store = get_scalping_diagnostics_store()
        recent: list[dict[str, Any]] = []
        if hasattr(store, "recent"):
            recent = store.recent(limit=min(limit, 2000))
        for event in recent:
            if isinstance(event, dict):
                raw_events.append(_normalize_from_ai_diag(event))
        ai_path = getattr(store, "_path", None)
        if isinstance(ai_path, Path):
            ai_jsonl_exists = ai_path.exists()
            ai_jsonl_bytes = ai_path.stat().st_size if ai_path.exists() else 0
            # Also mine durable AI diagnostics journal (survives restarts).
            for event in _read_jsonl_tail(ai_path, min(limit, 2000)):
                raw_events.append(_normalize_from_ai_diag(event))
    except Exception as exc:
        logger.warning("decision_analysis_ai_diag_failed", error=str(exc))

    events = _dedupe_events(raw_events, limit)

    primary_counter: Counter[str] = Counter()
    code_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    soft_family_counter: Counter[str] = Counter()
    combo_counter: Counter[str] = Counter()
    stage_counter: Counter[str] = Counter()
    ai_check_counter: Counter[str] = Counter()

    quality_vals: list[float] = []
    confluence_vals: list[float] = []
    mtf_vals: list[float] = []
    confidence_vals: list[float] = []
    liquidity_vals: list[float] = []
    spread_score_vals: list[float] = []
    spread_vals: list[float] = []
    atr_vals: list[float] = []
    atr_pct_vals: list[float] = []
    session_vals: list[float] = []
    news_vals: list[float] = []
    risk_vals: list[float] = []
    factor_avgs: dict[str, list[float]] = {
        "mtf": [],
        "liquidity": [],
        "spread": [],
        "session": [],
        "news": [],
        "volatility": [],
        "structure": [],
        "quality": [],
    }

    rejected_n = 0
    executed_n = 0
    no_trade_n = 0

    for ev in events:
        action = str(ev.get("decision_action") or "").upper()
        rejected = bool(ev.get("rejected"))
        if rejected or action in {"NO_TRADE", "WATCH"}:
            rejected_n += 1
            no_trade_n += 1
        if action in {"BUY", "SELL"} and not rejected:
            executed_n += 1

        primary = str(ev.get("primary_code") or "unknown")
        plow = primary.lower()
        if primary.startswith("MTF") or "not aligned" in plow:
            primary = "mtf_not_aligned"
        elif "trade quality" in plow and "below" in plow:
            primary = "quality_below_threshold"
        primary_counter[primary] += 1

        codes = [str(c) for c in (ev.get("codes") or []) if str(c).strip()]
        families_hit: set[str] = set()
        soft_hit: set[str] = set()
        for code in codes:
            if code in {"ignored_action", "Eligibility failed — NO_TRADE"}:
                continue
            if "AI quality gates rejected" in code:
                code_counter["ai_quality_gates_rejected"] += 1
                families_hit.add("ai_quality")
                continue
            code_counter[code] += 1
            fam = _CODE_TO_FAMILY.get(code) or _family_from_text(code)
            if fam:
                families_hit.add(fam)
            if code.startswith("ai_check_fail:"):
                ai_check_counter[code.removeprefix("ai_check_fail:")] += 1
        for reason in ev.get("reasons") or []:
            text = str(reason)
            soft = _soft_family_from_text(text)
            if soft:
                soft_hit.add(soft)
                continue
            fam = _family_from_text(text)
            if fam:
                families_hit.add(fam)
        if not families_hit and primary and primary != "unknown":
            fam = _CODE_TO_FAMILY.get(primary) or _family_from_text(primary)
            if fam:
                families_hit.add(fam)
        if not families_hit and (rejected or action in {"NO_TRADE", "WATCH"}):
            families_hit.add("other")
        for fam in families_hit:
            family_counter[fam] += 1
        for fam in soft_hit:
            soft_family_counter[fam] += 1
        combo_counter["+".join(sorted(families_hit)) if families_hit else "NONE"] += 1

        for stage in ev.get("stage_fails") or []:
            stage_counter[str(stage)] += 1

        checks = ev.get("quality_checks") or {}
        if isinstance(checks, dict):
            for k, ok in checks.items():
                if ok is False:
                    ai_check_counter[str(k)] += 1

        # Prefer explicit AI confidence; else confluence total is decision.confidence
        conf_val = ev.get("ai_confidence")
        if conf_val is None:
            conf_val = ev.get("confluence_score")
        for bucket, key, value in (
            (quality_vals, "quality_score", ev.get("quality_score")),
            (confluence_vals, "confluence_score", ev.get("confluence_score")),
            (mtf_vals, "mtf_score", ev.get("mtf_score")),
            (confidence_vals, "confidence", conf_val),
            (liquidity_vals, "liquidity_score", ev.get("liquidity_score")),
            (spread_score_vals, "spread_score", ev.get("spread_score")),
            (spread_vals, "spread", ev.get("spread")),
            (atr_vals, "atr", ev.get("atr")),
            (atr_pct_vals, "atr_pct", ev.get("atr_pct")),
            (session_vals, "session_score", ev.get("session_score")),
            (news_vals, "news_score", ev.get("news_score")),
            (risk_vals, "risk_pct", ev.get("risk_pct")),
        ):
            if value is None:
                continue
            try:
                bucket.append(float(value))
            except (TypeError, ValueError):
                pass

        factors = ev.get("engine_factors") or {}
        if isinstance(factors, dict):
            for fk in factor_avgs:
                if factors.get(fk) is not None:
                    try:
                        factor_avgs[fk].append(float(factors[fk]))
                    except (TypeError, ValueError):
                        pass

    total = len(events)
    pareto_primary = []
    running = 0
    for code, count in primary_counter.most_common():
        running += count
        pareto_primary.append(
            {
                "code": code,
                "label": code.replace("_", " "),
                "count": count,
                "share_pct": round(100.0 * count / total, 2) if total else 0.0,
                "cumulative_share_pct": round(100.0 * running / total, 2) if total else 0.0,
            }
        )

    family_hit_total = max(sum(family_counter.values()), 1)
    pareto_family = [
        {
            "family": fam,
            "count": count,
            "share_of_family_hits_pct": round(100.0 * count / family_hit_total, 2),
            "share_of_cycles_pct": round(100.0 * count / total, 2) if total else 0.0,
        }
        for fam, count in family_counter.most_common()
    ]

    # Ensure all requested families appear (zero-fill)
    seen_fams = {row["family"] for row in pareto_family}
    for fam in FILTER_FAMILIES:
        if fam not in seen_fams:
            pareto_family.append(
                {
                    "family": fam,
                    "count": 0,
                    "share_of_family_hits_pct": 0.0,
                    "share_of_cycles_pct": 0.0,
                }
            )

    top_combos = [
        {
            "combination": combo,
            "count": count,
            "share_pct": round(100.0 * count / total, 2) if total else 0.0,
        }
        for combo, count in combo_counter.most_common(25)
    ]

    return {
        "advisory_only": True,
        "mutates_engines": False,
        "thresholds_changed": False,
        "as_of": datetime.now(UTC).isoformat(),
        "requested_limit": limit,
        "cycles_analyzed": total,
        "sample_complete": total >= limit,
        "sample_note": (
            "Merged durable ite_cycle_evidence.jsonl + in-memory Strategy Diagnostics "
            "+ AI Scalping diagnostics (memory + JSONL); deduped by trace_id. "
            f"Requested {limit}; available after merge: {total}."
        ),
        "sources": {
            "jsonl_path": jsonl_path,
            "jsonl_exists": jsonl_exists,
            "jsonl_bytes": jsonl_bytes,
            "ai_scalping_jsonl_exists": ai_jsonl_exists,
            "ai_scalping_jsonl_bytes": ai_jsonl_bytes,
            "strategy_diagnostics_stats": diag_stats,
        },
        "outcomes": {
            "total": total,
            "rejected_or_no_trade": rejected_n,
            "no_trade": no_trade_n,
            "executed_like": executed_n,
            "execution_rate_pct": round(100.0 * executed_n / total, 2) if total else 0.0,
            "rejection_rate_pct": round(100.0 * rejected_n / total, 2) if total else 0.0,
        },
        "averages": {
            "quality_score": _avg(quality_vals),
            "confluence_score": _avg(confluence_vals),
            "mtf_score": _avg(mtf_vals),
            "confidence": _avg(confidence_vals),
            "ai_confidence": _avg(
                [float(ev["ai_confidence"]) for ev in events if ev.get("ai_confidence") is not None]
            ),
            "liquidity_score": _avg(liquidity_vals),
            "spread_score": _avg(spread_score_vals),
            "spread": _avg(spread_vals),
            "atr": _avg(atr_vals),
            "atr_pct": _avg(atr_pct_vals),
            "session_score": _avg(session_vals),
            "news_score": _avg(news_vals),
            "risk_pct": _avg(risk_vals),
            "engine_factor_averages": {k: _avg(v) for k, v in factor_avgs.items()},
            "n_quality": len(quality_vals),
            "n_mtf": len(mtf_vals),
            "n_confidence": len(confidence_vals),
            "n_spread": len(spread_vals),
            "n_atr": len(atr_vals),
            "n_atr_pct": len(atr_pct_vals),
        },
        "rejection_frequency_by_primary_code": pareto_primary,
        "rejection_frequency_by_filter_family": pareto_family,
        "soft_observation_frequency_by_filter_family": [
            {
                "family": fam,
                "count": count,
                "share_of_cycles_pct": round(100.0 * count / total, 2) if total else 0.0,
                "note": "Soft score/weight only — not a hard NO_TRADE cause",
            }
            for fam, count in soft_family_counter.most_common()
        ],
        "rejection_combinations": top_combos,
        "stage_fail_frequency": [
            {
                "stage": k,
                "count": v,
                "share_pct": round(100.0 * v / total, 2) if total else 0.0,
            }
            for k, v in stage_counter.most_common()
        ],
        "ai_quality_check_fail_frequency": [
            {
                "check": k,
                "count": v,
                "share_of_cycles_pct": round(100.0 * v / total, 2) if total else 0.0,
            }
            for k, v in ai_check_counter.most_common()
        ],
        "code_frequency_all_codes": [
            {
                "code": k,
                "count": v,
                "share_pct": round(100.0 * v / total, 2) if total else 0.0,
            }
            for k, v in code_counter.most_common(40)
        ],
    }
