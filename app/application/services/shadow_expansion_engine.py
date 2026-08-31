"""Shadow expansion engine — observation only.

Watches the same live market snapshot the production scanner already
computed. Records candidate setup-family presence. Never sends orders,
never alters live decisions, never touches Risk / Safety / Optimizer / OMS.

Promotion into production is impossible from this module: there is no
execution path, and every candidate still inherits Opportunity 70, edge 5,
Sniper, Risk, Safety, and OMS if a human later approves a separate change.
"""

from __future__ import annotations

from typing import Any

from app.application.services.strategy_loss_forensics import (
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
    _metrics,
    sample_status,
)

ADVISORY_ONLY = True
SHADOW_MAY_SUBMIT_ORDERS = False
SHADOW_MAY_ALTER_LIVE_DECISIONS = False
SHADOW_MAY_BYPASS_RISK = False
SHADOW_MAY_BYPASS_SAFETY = False
SHADOW_MAY_BYPASS_OMS = False
OPP_THRESHOLD = 70
EDGE_MARGIN = 5

# Presence detectors use already-computed families / scores. They do not
# re-run frozen direction, sniper, or OMS, and they never mark TAKE.
CANDIDATE_SPECS: tuple[dict[str, Any], ...] = (
    {"candidate_id": "A", "candidate_name": "continuation", "layer": "EXPANSION", "needs": ("structure",)},
    {"candidate_id": "B", "candidate_name": "pullback_continuation", "layer": "EXPANSION", "needs": ("structure",), "setup_any": ("RETEST", "INSIDE", "CONTROLLED", "PULLBACK")},
    {"candidate_id": "C", "candidate_name": "bos_continuation", "layer": "EXPANSION", "needs": ("structure",), "bos": True},
    {"candidate_id": "D", "candidate_name": "choch_reversal", "layer": "EXPANSION", "needs": ("structure",), "choch": True, "setup_any": ("CHOCH", "REVERSAL")},
    {"candidate_id": "E", "candidate_name": "sweep_bos", "layer": "EXPANSION", "needs": ("liquidity", "structure"), "bos": True},
    {"candidate_id": "F", "candidate_name": "liquidity_sweep_ob_retest", "layer": "EXPANSION", "needs": ("liquidity", "zone"), "ob": True, "setup_any": ("RETEST", "SWEEP", "CONTROLLED")},
    {"candidate_id": "G", "candidate_name": "fvg_retest", "layer": "EXPANSION", "needs": ("zone",), "fvg": True, "setup_any": ("RETEST", "INSIDE", "CONTROLLED")},
    {"candidate_id": "H", "candidate_name": "ob_retest", "layer": "EXPANSION", "needs": ("zone",), "ob": True, "setup_any": ("RETEST", "INSIDE", "CONTROLLED")},
    {"candidate_id": "I", "candidate_name": "displacement_continuation", "layer": "EXPANSION", "needs": ("structure",), "displacement": True},
    {"candidate_id": "J", "candidate_name": "session_continuation", "layer": "EXPANSION", "needs": ("structure",), "session_any": ("sydney", "tokyo", "london", "new_york", "ny", "overlap")},
    {"candidate_id": "K", "candidate_name": "london_setup", "layer": "EXPANSION", "session_any": ("london",)},
    {"candidate_id": "L", "candidate_name": "london_ny_overlap", "layer": "EXPANSION", "session_any": ("london_ny_overlap", "overlap")},
    {"candidate_id": "M", "candidate_name": "new_york_setup", "layer": "EXPANSION", "session_any": ("new_york", "ny")},
    {"candidate_id": "N", "candidate_name": "volatility_expansion", "layer": "EXPANSION", "regime_any": ("high_volatility", "expansion", "breakout", "news_volatility")},
    {"candidate_id": "O", "candidate_name": "compression_breakout", "layer": "EXPANSION", "setup_any": ("CONTROLLED", "BREAKOUT", "COMPRESSION"), "regime_any": ("breakout", "expansion", "low_volatility")},
    {"candidate_id": "P", "candidate_name": "trend_continuation", "layer": "EXPANSION", "needs": ("structure",), "regime_any": ("trend", "trending")},
    {"candidate_id": "Q", "candidate_name": "range_rejection", "layer": "EXPANSION", "regime_any": ("range", "mean_reversion", "low_volatility")},
    {"candidate_id": "R", "candidate_name": "structure_reclaim", "layer": "EXPANSION", "needs": ("structure",), "setup_any": ("RECLAIM", "RETEST")},
    {"candidate_id": "S", "candidate_name": "mtf_alignment", "layer": "EXPANSION", "mtf_pair": ("m1_bos", "m5_bos")},
    {"candidate_id": "T", "candidate_name": "momentum_confirmation", "layer": "EXPANSION", "momentum_min": 70},
    {"candidate_id": "U", "candidate_name": "confluence_expansion", "layer": "EXPANSION", "needs": ("structure", "zone")},
    {"candidate_id": "V", "candidate_name": "high_quality_pullback", "layer": "EXPANSION", "needs": ("structure", "zone"), "setup_any": ("RETEST", "PULLBACK", "CONTROLLED")},
    {"candidate_id": "W", "candidate_name": "reversal_confirmation", "layer": "EXPANSION", "needs": ("structure",), "setup_any": ("CHOCH", "REVERSAL", "CONTROLLED")},
    {"candidate_id": "X", "candidate_name": "continuation_after_liquidity", "layer": "EXPANSION", "needs": ("structure", "liquidity")},
)

PROMOTION_STATES = (
    "NOT_READY",
    "INSUFFICIENT_SAMPLE",
    "RESEARCH",
    "VALIDATION",
    "OOS_PASS",
    "PROMOTION_CANDIDATE",
    "REQUIRES_REVIEW",
    "APPROVED",
    "LIVE",
)
ALLOW_LIVE_PROMOTION = False
FUTURE_FIELD_MARKERS = (
    "future_",
    "next_candle",
    "next_bar",
    "lookahead",
    "future_bos",
    "future_choch",
    "future_fvg",
    "future_pnl",
    "future_spread",
)


class ShadowExpansionBlocked(RuntimeError):
    """Raised if any caller tries to use shadow as an execution path."""


def submit_order(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_EXPANSION_CANNOT_SEND_ORDERS")


def alter_live_decision(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_EXPANSION_CANNOT_ALTER_LIVE_DECISIONS")


def bypass_risk(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_EXPANSION_CANNOT_BYPASS_RISK")


def bypass_safety(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_EXPANSION_CANNOT_BYPASS_SAFETY")


def bypass_oms(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_EXPANSION_CANNOT_BYPASS_OMS")


def _families(cycle: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in ("buy_families", "sell_families"):
        raw = cycle.get(key) or []
        if isinstance(raw, (list, tuple)):
            out.update(str(x).strip().lower() for x in raw if x)
    return out


def _has_token(cycle: dict[str, Any], *needles: str) -> bool:
    blob = " ".join(
        str(cycle.get(k) or "")
        for k in (
            "setup_state",
            "sniper_state",
            "bos_state",
            "choch_state",
            "ob_state",
            "fvg_state",
            "first_authoritative_blocker",
        )
    ).upper()
    return any(n.upper() in blob for n in needles)


def candidate_present(spec: dict[str, Any], cycle: dict[str, Any]) -> bool:
    fam = _families(cycle)
    needs = tuple(spec.get("needs") or ())
    if needs and not all(n in fam for n in needs):
        return False
    setup_any = spec.get("setup_any")
    if setup_any and not _has_token(cycle, *setup_any):
        state = str(cycle.get("setup_state") or "").upper()
        if state not in {str(s).upper() for s in setup_any}:
            return False
    session_any = spec.get("session_any")
    if session_any:
        session = str(cycle.get("market_session") or "").lower()
        if not any(s in session for s in session_any):
            return False
    regime_any = spec.get("regime_any")
    if regime_any:
        regime = str(cycle.get("market_regime") or "").lower()
        if not any(r.lower() in regime for r in regime_any):
            return False
    if spec.get("ob") and not (
        _has_token(cycle, "OB", "ORDER_BLOCK") or "zone" in fam
    ):
        return False
    if spec.get("fvg") and not _has_token(cycle, "FVG"):
        # Zone family without FVG token is not enough to claim FVG reaction.
        if "fvg" not in fam and not str(cycle.get("fvg_state") or ""):
            return False
    if spec.get("choch") and not _has_token(cycle, "CHOCH"):
        return False
    if spec.get("bos") and not _has_token(cycle, "BOS", "BREAK_OF_STRUCTURE"):
        return False
    if spec.get("displacement") and not _has_token(
        cycle, "DISPLACEMENT", "IMPULSE"
    ):
        audit = cycle.get("opportunity_audit") if isinstance(cycle.get("opportunity_audit"), dict) else {}
        disp = audit.get("displacement") if isinstance(audit.get("displacement"), dict) else {}
        try:
            if int(disp.get("score") or cycle.get("displacement_score") or 0) < 70:
                return False
        except (TypeError, ValueError):
            return False
    mtf_pair = spec.get("mtf_pair")
    if mtf_pair:
        breakdown = cycle.get("score_breakdown") if isinstance(cycle.get("score_breakdown"), dict) else {}
        factors = cycle.get("factors") if isinstance(cycle.get("factors"), dict) else {}
        left, right = mtf_pair
        left_v = breakdown.get(left) or factors.get(left) or cycle.get(left)
        right_v = breakdown.get(right) or factors.get(right) or cycle.get(right)
        try:
            if int(left_v or 0) < 70 or int(right_v or 0) < 70:
                return False
        except (TypeError, ValueError):
            return False
    momentum_min = spec.get("momentum_min")
    if momentum_min is not None:
        mom = cycle.get("momentum_score")
        try:
            if mom is None or int(mom) < int(momentum_min):
                return False
        except (TypeError, ValueError):
            return False
    return True


def detect_lookahead_fields(row: dict[str, Any] | None) -> list[str]:
    """Return keys that would leak future information into a research feature."""
    leaked: list[str] = []
    for key in dict(row or {}):
        low = str(key).lower()
        if any(marker in low for marker in FUTURE_FIELD_MARKERS):
            leaked.append(str(key))
    return leaked


def features_as_of(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """Drop future-leaking keys. Shadow may only see T-or-before fields."""
    row = dict(cycle or {})
    for key in detect_lookahead_fields(row):
        row.pop(key, None)
    return row


def promotion_status(
    *,
    sample_size: int,
    oos_positive: bool,
    lookahead: bool,
    human_approved: bool = False,
    promote_live: bool = False,
) -> str:
    """Research promotion labels. LIVE is unreachable without a separate task."""
    if lookahead:
        return "NOT_READY"
    if sample_size < 20:
        return "INSUFFICIENT_SAMPLE"
    if not oos_positive:
        return "RESEARCH" if sample_size < 50 else "VALIDATION"
    if promote_live or ALLOW_LIVE_PROMOTION:
        raise ShadowExpansionBlocked("SHADOW_CANNOT_GO_LIVE_FROM_THIS_MODULE")
    if sample_size >= 50:
        return "PROMOTION_CANDIDATE"
    return "OOS_PASS"


def apply_human_promotion(to_state: str, *, approved_by: str | None) -> str:
    target = str(to_state or "").upper()
    if target == "LIVE" or not approved_by:
        raise ShadowExpansionBlocked("SHADOW_CANNOT_GO_LIVE_FROM_THIS_MODULE")
    if target not in PROMOTION_STATES or target in {"LIVE"}:
        raise ShadowExpansionBlocked("INVALID_PROMOTION_STATE")
    if target == "APPROVED":
        return "PROMOTION_CANDIDATE"
    return target


def observe_shadow_cycle(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """Label which expansion families are present. Never a fill."""
    row = features_as_of(cycle)
    edge = None
    opp = None
    try:
        edge = int(row.get("directional_edge")) if row.get("directional_edge") is not None else None
    except (TypeError, ValueError):
        edge = None
    try:
        opp = int(row.get("opportunity_score")) if row.get("opportunity_score") is not None else None
    except (TypeError, ValueError):
        opp = None
    would_pass_core = bool(
        edge is not None and opp is not None and edge >= EDGE_MARGIN and opp >= OPP_THRESHOLD
    )
    setup = str(row.get("setup_state") or "").upper()
    first_live_blocker = str(row.get("first_authoritative_blocker") or "") or None
    would_live_take = bool(would_pass_core and setup == "TAKE")
    why_rejected = None if would_live_take else (first_live_blocker or "LIVE_GATES_NOT_CLEARED")
    present_rows: list[dict[str, Any]] = []
    present_names: list[str] = []
    for spec in CANDIDATE_SPECS:
        present = candidate_present(spec, row)
        if present:
            present_names.append(str(spec["candidate_name"]))
        present_rows.append(
            {
                "candidate_id": spec["candidate_id"],
                "candidate_name": spec["candidate_name"],
                "candidate_family": spec["candidate_name"],
                "layer": spec.get("layer") or "EXPANSION",
                "CORE": False,
                "EXPANSION": True,
                "SHADOW_ONLY": True,
                "SHADOW": True,
                "COUNTERFACTUAL": True,
                "NOT_EXECUTED": True,
                "timestamp": row.get("recorded_at"),
                "symbol": row.get("symbol") or "XAUUSD_i",
                "direction": row.get("candidate") or row.get("decision_action"),
                "entry_reason": spec["candidate_name"],
                "hypothetical_entry": row.get("entry") or row.get("bid"),
                "hypothetical_SL": row.get("stop") or row.get("sl") or row.get("stop_loss"),
                "hypothetical_TP": row.get("target") or row.get("tp") or row.get("take_profit"),
                "hypothetical_outcome": UNKNOWN,
                "hypothetical_R": row.get("rr") or row.get("expected_rr") or UNKNOWN,
                "MAE": UNKNOWN,
                "MFE": UNKNOWN,
                "opportunity": opp,
                "edge": edge,
                "counterfactual_edge": edge,
                "counterfactual_opportunity": opp,
                "setup_families": list(row.get("buy_families") or [])
                + list(row.get("sell_families") or []),
                "session": row.get("market_session"),
                "regime": row.get("market_regime"),
                "candidate_reason": spec["candidate_name"],
                "would_current_live_strategy_take": would_live_take,
                "why_live_strategy_rejected": why_rejected,
                "first_live_blocker": first_live_blocker,
                "would_pass_core": would_pass_core,
                "would_pass_expansion": present,
                "would_submit_order": False,
                "shadow_result": "PRESENT" if present else "ABSENT",
                "lookahead_fields": detect_lookahead_fields(cycle),
            }
        )
    return {
        "advisory_only": True,
        "SHADOW_ONLY": True,
        "SHADOW": True,
        "COUNTERFACTUAL": True,
        "NOT_EXECUTED": True,
        "shadow": True,
        "would_submit_order": False,
        "would_current_live_strategy_take": would_live_take,
        "why_live_strategy_rejected": why_rejected,
        "first_live_blocker": first_live_blocker,
        "counterfactual_edge": edge,
        "counterfactual_opportunity": opp,
        "alters_live_decision": False,
        "bypasses_risk": False,
        "bypasses_safety": False,
        "bypasses_oms": False,
        "inherits_opportunity_70": True,
        "inherits_edge_5": True,
        "production_gates_still_required": True,
        "directional_edge": edge,
        "opportunity_score": opp,
        "production_both_qualify": would_pass_core,
        "present_families": present_names,
        "candidates": present_rows,
        "not_a_fill": True,
        "not_a_ticket": True,
        "hypothetical_outcome": UNKNOWN,
    }


def classify_candidate_vs_production(
    *,
    sample_size: int,
    expectancy_r: Any,
    profit_factor: Any,
    oos_expectancy: Any,
) -> str:
    if sample_size < 20:
        return INSUFFICIENT_SAMPLE
    if sample_size < 50:
        return "OBSERVATIONAL"
    pos = False
    try:
        pos = float(expectancy_r) > 0 and (
            profit_factor == UNKNOWN or float(profit_factor) > 1.0
        )
    except (TypeError, ValueError):
        pos = False
    oos_ok = False
    try:
        oos_ok = oos_expectancy not in {None, UNKNOWN} and float(oos_expectancy) > 0
    except (TypeError, ValueError):
        oos_ok = False
    if sample_size >= 100 and pos and oos_ok:
        return "PRODUCTION_CANDIDATE"
    if pos and oos_ok:
        return "PROMISING"
    if not pos:
        return "REJECT"
    return "OBSERVATIONAL"


def walk_forward_split(
    trades: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Time-ordered 60/20/20. Refuses to reuse the selection sample as OOS."""
    ordered = sorted(
        trades,
        key=lambda t: str(t.get("exit_time") or t.get("timestamp_utc") or ""),
    )
    n = len(ordered)
    if n < 20:
        return {
            "train": [],
            "validation": [],
            "out_of_sample": [],
            "status": INSUFFICIENT_SAMPLE,
            "lookahead": False,
            "hold_overlap": False,
        }
    i_train = int(n * 0.60)
    i_val = int(n * 0.80)
    train = ordered[:i_train]
    validation = ordered[i_train:i_val]
    oos = ordered[i_val:]
    # Guard: OOS exits must not precede the last train exit (split corruption).
    # Holding across the cut is overlap, not feature lookahead.
    lookahead = False
    hold_overlap = False
    if train and oos:
        last_train = str(train[-1].get("exit_time") or "")
        first_oos_exit = str(oos[0].get("exit_time") or "")
        first_oos_entry = str(oos[0].get("entry_time") or "")
        if first_oos_exit and last_train and first_oos_exit < last_train:
            lookahead = True
        if first_oos_entry and last_train and first_oos_entry < last_train:
            hold_overlap = True
    return {
        "train": train,
        "validation": validation,
        "out_of_sample": oos,
        "status": sample_status(n),
        "lookahead": lookahead,
        "hold_overlap": hold_overlap,
        "rejected_if_lookahead": lookahead,
    }


def _family_trades(matched: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in matched:
        fams = [str(x).lower() for x in (t.get("buy_families") or [])] + [
            str(x).lower() for x in (t.get("sell_families") or [])
        ]
        setups = str(t.get("setup_state") or "").lower()
        if name.replace("_", " ") in setups or name in fams or name in str(t.get("shadow_families") or []):
            out.append(t)
            continue
        shadow = t.get("shadow_families")
        if isinstance(shadow, (list, tuple)) and name in shadow:
            out.append(t)
    return out


def expansion_report(
    *,
    matched_trades: list[dict[str, Any]] | None = None,
    current_cycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matched = list(matched_trades or [])
    production = _metrics(matched)
    live = observe_shadow_cycle(current_cycle)
    candidates: list[dict[str, Any]] = []
    for spec in CANDIDATE_SPECS:
        name = spec["candidate_name"]
        rows = _family_trades(matched, name)
        split = walk_forward_split(rows)
        train_m = _metrics(split["train"])
        val_m = _metrics(split["validation"])
        oos_m = _metrics(split["out_of_sample"])
        overall = _metrics(rows)
        if split.get("lookahead"):
            klass = "REJECT"
            oos_result = "LOOKAHEAD_REJECTED"
        else:
            klass = classify_candidate_vs_production(
                sample_size=len(rows),
                expectancy_r=overall.get("AVERAGE_R")
                if overall.get("AVERAGE_R") != UNKNOWN
                else overall.get("EXPECTANCY"),
                profit_factor=overall.get("PROFIT_FACTOR"),
                oos_expectancy=oos_m.get("EXPECTANCY"),
            )
            oos_result = (
                oos_m.get("EXPECTANCY")
                if len(split["out_of_sample"])
                else INSUFFICIENT_SAMPLE
            )
        oos_ok = False
        try:
            oos_ok = (
                not split.get("lookahead")
                and oos_result not in {None, INSUFFICIENT_SAMPLE, UNKNOWN, "LOOKAHEAD_REJECTED"}
                and float(oos_m.get("EXPECTANCY") or 0) > 0
                and len(split["out_of_sample"]) >= 1
                and len(rows) >= 20
            )
        except (TypeError, ValueError):
            oos_ok = False
        promo = promotion_status(
            sample_size=len(rows),
            oos_positive=oos_ok,
            lookahead=bool(split.get("lookahead")),
        )
        buy = [t for t in rows if str(t.get("direction") or "").upper() in {"BUY", "LONG"}]
        sell = [t for t in rows if str(t.get("direction") or "").upper() in {"SELL", "SHORT"}]
        candidates.append(
            {
                "candidate_id": spec.get("candidate_id"),
                "candidate_name": name,
                "layer": spec.get("layer") or "EXPANSION",
                "CORE": False,
                "EXPANSION": True,
                "SHADOW_ONLY": True,
                "sample_size": len(rows),
                "win_rate": overall.get("WIN_RATE"),
                "win_rate_display": overall.get("WIN_RATE_DISPLAY"),
                "expectancy_R": overall.get("AVERAGE_R"),
                "profit_factor": overall.get("PROFIT_FACTOR"),
                "average_R": overall.get("AVERAGE_R"),
                "max_drawdown_R": overall.get("MAX_DRAWDOWN"),
                "average_MAE": overall.get("MAE"),
                "average_MFE": overall.get("MFE"),
                "average_hold_time": overall.get("AVERAGE_HOLD_TIME"),
                "BUY_performance": _metrics(buy),
                "SELL_performance": _metrics(sell),
                "session_performance": {
                    s: _metrics([t for t in rows if str(t.get("session") or "").lower() == s])
                    for s in ("sydney", "tokyo", "london", "london_ny_overlap", "new_york")
                },
                "classification": klass,
                "promotion_status": promo,
                "train": train_m,
                "validation": val_m,
                "out_of_sample": oos_m,
                "out_of_sample_result": oos_result,
                "present_on_current_scan": name in live["present_families"],
                "auto_promote": False,
                "can_send_orders": False,
            }
        )
    ranked = [
        c
        for c in candidates
        if c["classification"] in {"PROMISING", "PRODUCTION_CANDIDATE"}
    ]
    best = ranked[0]["candidate_name"] if ranked else INSUFFICIENT_SAMPLE
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "never_sends_orders": True,
        "never_bypasses_opportunity_70": True,
        "never_bypasses_edge_5": True,
        "never_bypasses_sniper_risk_safety_oms": True,
        "current_production": production,
        "current_scan": live,
        "candidates": candidates,
        "best_expansion_candidate": best,
        "rejects_high_win_rate_negative_expectancy": True,
        "rejects_martingale": True,
        "rejects_lookahead": True,
        "human_review_required_before_production": True,
        "SHADOW_ONLY": True,
        "allow_live_promotion": False,
        "ALLOW_LIVE_PROMOTION": False,
        "would_submit_order": False,
        "never_merges_core_and_expansion": True,
        "disclaimer": "Historical data does not guarantee future profitability.",
    }
