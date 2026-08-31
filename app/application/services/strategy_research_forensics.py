"""Read-only Strategy Research forensics facade.

Combines forensic ledger, matched-only stats, shadow expansion, funnel
histograms, and VPS classification. Never sends orders or changes gates.
"""

from __future__ import annotations

from typing import Any

from app.application.services.opportunity_funnel_telemetry import funnel_snapshot
from app.application.services.shadow_expansion_engine import (
    expansion_report,
    observe_shadow_cycle,
)
from app.application.services.shadow_observation_pipeline import shadow_dataset_snapshot
from app.application.services.strategy_forensic_ledger import (
    STRATEGY_MATCHED,
    UNMATCHED,
    list_signals,
    list_submissions,
)
from app.application.services.strategy_intelligence_center import (
    pair_deals_into_closed_trades,
)
from app.application.services.strategy_loss_forensics import (
    DISCLAIMER,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
    build_loss_forensics,
    sample_status,
)
from app.application.services.strategy_settings_audit import (
    audit_news_protection,
    build_strategy_settings_audit,
)
from app.application.services.vps_continuity_classifier import classify_vps_continuity

PRODUCTION_SHA = "2ca77933316c1bc798e84d884f353e30eac385d3"
RESEARCH_STAGES = (
    "COLLECT",
    "MATCH",
    "CLASSIFY",
    "MEASURE",
    "BACKTEST",
    "WALK-FORWARD",
    "COMPARE",
    "CONFIDENCE",
    "SHADOW",
    "PROMOTION_CANDIDATE",
)


def research_workflow(*, matched_n: int) -> dict[str, Any]:
    """Evidence pipeline. Never COLLECT → GUESS → DEPLOY."""
    n = int(matched_n or 0)
    current = "COLLECT"
    if n > 0:
        current = "MATCH"
    if n >= 5:
        current = "CLASSIFY"
    if n >= 10:
        current = "MEASURE"
    if n >= 20:
        current = "WALK-FORWARD"
    return {
        "stages": list(RESEARCH_STAGES),
        "current": current,
        "never_guess_then_deploy": True,
        "max_automated_state": "PROMOTION_CANDIDATE",
        "live_requires_explicit_human_authorization": True,
        "matched_n": n,
    }


def _latest_cycle(diagnostics: dict[str, Any] | None) -> dict[str, Any]:
    if not diagnostics:
        return {}
    latest = diagnostics.get("latest")
    if isinstance(latest, dict):
        return latest
    cycles = diagnostics.get("cycles")
    if isinstance(cycles, list) and cycles and isinstance(cycles[0], dict):
        return cycles[0]
    return {}


def _nested_score(container: Any, key: str) -> Any:
    if not isinstance(container, dict):
        return None
    nested = container.get(key)
    if isinstance(nested, dict):
        return nested.get("score")
    return nested


def classify_conflict_paint(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """CONFLICT→displacement/timing=20 is paint after Sniper WAIT, not a TAKE killer.

    scoring.py paints only when setup_state is CHASING/STALE/CONFLICT. TAKE is
    never in that set. On the live tape the authoritative blocker is already
    WAIT_NO_DIRECTIONAL_EDGE (edge 4 < 5). Leave scoring.py unchanged.
    """
    row = dict(cycle or {})
    setup = str(row.get("setup_state") or "").upper()
    blocker = str(row.get("first_authoritative_blocker") or "").upper()
    painted = setup in {"CHASING", "STALE", "CONFLICT"}
    take = setup == "TAKE"
    direction_already_failed = "NO_DIRECTIONAL_EDGE" in blocker or blocker == "DIRECTION_NONE"
    sniper = row.get("sniper_entry") if isinstance(row.get("sniper_entry"), dict) else {}
    pillars = sniper.get("pillars") if isinstance(sniper.get("pillars"), dict) else {}
    diagnostics = (
        sniper.get("diagnostics") if isinstance(sniper.get("diagnostics"), dict) else {}
    )
    entry_state = str(
        sniper.get("entry_state") or diagnostics.get("entry_state") or ""
    ).upper()
    has_sniper = bool(sniper)
    raw_displacement: Any = UNKNOWN
    raw_timing: Any = UNKNOWN
    if has_sniper:
        raw_displacement = 78 if pillars.get("displacement_or_momentum") else 20
        raw_timing = 80 if entry_state in {"RETEST", "INSIDE", "CONTROLLED"} else 20
    audit = row.get("opportunity_audit") if isinstance(row.get("opportunity_audit"), dict) else {}
    breakdown = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
    effective_displacement = _nested_score(audit, "displacement")
    if effective_displacement is None:
        effective_displacement = breakdown.get("displacement")
    effective_timing = _nested_score(audit, "timing")
    if effective_timing is None:
        effective_timing = breakdown.get("timing") or breakdown.get("timing_retest")
    paint_reason = f"STALE_OR_CHASE_PAINT:{setup}" if painted and not take else "NONE"
    return {
        "classification": "SECONDARY_OBSERVABILITY_SCORING_PAINT",
        "changes_qualifying_take_into_wait": False,
        "applies_on_this_scan": painted and not take,
        "setup_state": setup or None,
        "first_authoritative_blocker": blocker or None,
        "direction_gate_already_failed": direction_already_failed,
        "leave_scoring_unchanged": True,
        "paint_timing": "AFTER_SNIPER_BEFORE_OPPORTUNITY_VERDICT",
        "paint_is_first_blocker": False,
        "paint_reason": paint_reason,
        "raw_displacement": raw_displacement,
        "effective_displacement": effective_displacement if effective_displacement is not None else UNKNOWN,
        "raw_timing": raw_timing,
        "effective_timing": effective_timing if effective_timing is not None else UNKNOWN,
        "evidence": (
            "Paint runs after evaluate_sniper_entry. TAKE setup_state is not painted. "
            "Sentinel 20 is treated as absent by _smc_presence_score, so it withholds "
            "a boost rather than creating a new WAIT on a passed Sniper TAKE."
        ),
    }


def current_market_panel(cycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": cycle.get("symbol") or "XAUUSD_i",
        "buy_score": cycle.get("buy_score"),
        "sell_score": cycle.get("sell_score"),
        "ltf_buy": cycle.get("ltf_buy_score") or cycle.get("ltf_buy"),
        "ltf_sell": cycle.get("ltf_sell_score") or cycle.get("ltf_sell"),
        "directional_edge": cycle.get("directional_edge"),
        "required_edge": 5,
        "opportunity_score": cycle.get("opportunity_score"),
        "required_opportunity": 70,
        "setup_state": cycle.get("setup_state"),
        "sniper_state": cycle.get("sniper_state") or cycle.get("sniper"),
        "first_authoritative_blocker": cycle.get("first_authoritative_blocker"),
        "blocker_source": cycle.get("blocker_source"),
        "market_session": cycle.get("market_session"),
        "scan_as_of": cycle.get("scan_as_of") or cycle.get("recorded_at"),
        "data": cycle.get("data"),
        "scanner_status": cycle.get("scanner_status")
        or cycle.get("scanner")
        or cycle.get("data")
        or "UNKNOWN",
        "execution_status": (
            "EXECUTED"
            if cycle.get("mt5_ticket") or cycle.get("ticket")
            else (
                "FORWARDED_NO_TICKET"
                if cycle.get("forwarded_to_oms")
                else "NOT_REACHED"
            )
        ),
        "risk": cycle.get("risk") or "NOT_REACHED",
        "safety": cycle.get("safety") or "NOT_REACHED",
        "oms": cycle.get("oms") or cycle.get("oms_status") or "NOT_REACHED",
        "forwarded_to_oms": bool(cycle.get("forwarded_to_oms")),
        "mt5_ticket": cycle.get("mt5_ticket") or cycle.get("ticket"),
        "conflict_paint": classify_conflict_paint(cycle),
        "data_age_seconds": cycle.get("data_age_seconds"),
        "market_data_valid": cycle.get("market_data_valid"),
        "as_of": cycle.get("as_of") or cycle.get("scan_as_of") or cycle.get("recorded_at"),
        "stable_scores_are_not_frozen_scanner": True,
    }


def frequency_bottleneck(cycle: dict[str, Any], histograms: dict[str, Any]) -> str:
    edge = cycle.get("directional_edge")
    opp = cycle.get("opportunity_score")
    try:
        if edge is not None and int(edge) < 5:
            return "DIRECTION"
    except (TypeError, ValueError):
        pass
    try:
        if opp is not None and int(opp) < 70:
            return "OPPORTUNITY"
    except (TypeError, ValueError):
        pass
    rates = (histograms.get("rates_pct") or {}) if isinstance(histograms, dict) else {}
    if float(rates.get("both_qualify") or 0) == 0:
        return "DIRECTION_THEN_OPPORTUNITY"
    if float(rates.get("sniper_take") or 0) == 0:
        return "SNIPER"
    if float(rates.get("oms_forward") or 0) == 0:
        return "PRE_OMS"
    return "NONE_OBSERVED"


def build_strategy_research_forensics(
    *,
    days: int = 90,
    diagnostics: dict[str, Any] | None = None,
    deals: list[dict[str, Any]] | None = None,
    vps_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if diagnostics is None:
        try:
            from app.application.services.strategy_diagnostics import (
                get_strategy_diagnostics_store,
            )

            diagnostics = get_strategy_diagnostics_store().snapshot(limit=100)
        except Exception:
            diagnostics = {}
    cycle = _latest_cycle(diagnostics)
    closed: list[dict[str, Any]] = []
    deal_meta: dict[str, Any] = {"attempted": False}
    if deals is not None:
        closed = pair_deals_into_closed_trades(deals)
        deal_meta = {"attempted": True, "ok": True, "via": "injected", "raw_count": len(deals)}
    else:
        try:
            from app.application.services.strategy_intelligence_center import (
                _load_history_deals,
            )

            raw, deal_meta = _load_history_deals(days=days)
            closed = pair_deals_into_closed_trades(raw)
        except Exception as exc:
            deal_meta = {"attempted": True, "ok": False, "error": str(exc)[:200]}

    forensics = build_loss_forensics(closed_trades=closed)
    try:
        histograms = funnel_snapshot()
    except Exception:
        histograms = {"advisory_only": True, "failed": True, "windows": {}}
    try:
        shadow = expansion_report(
            matched_trades=list(forensics.get("matched_preview") or []),
            current_cycle=cycle,
        )
    except Exception as exc:
        shadow = {
            "SHADOW_ONLY": True,
            "would_submit_order": False,
            "failed": True,
            "error": str(exc)[:200],
            "candidates": [],
            "best_expansion_candidate": INSUFFICIENT_SAMPLE,
        }
    try:
        current_shadow = observe_shadow_cycle(cycle)
    except Exception:
        current_shadow = {
            "SHADOW_ONLY": True,
            "NOT_EXECUTED": True,
            "would_submit_order": False,
            "failed": True,
            "candidates": [],
        }
    try:
        shadow_dataset = shadow_dataset_snapshot()
    except Exception as exc:
        shadow_dataset = {
            "advisory_only": True,
            "dataset": "SHADOW",
            "would_submit_order": False,
            "ALLOW_LIVE_PROMOTION": False,
            "failed": True,
            "error": str(exc)[:200],
            "observations": 0,
            "virtual_completed": 0,
            "candidates": [],
            "verdict": {
                "code": "NO_SAFE_EXPANSION_PROVEN",
                "text": "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA",
                "n": 0,
            },
        }
    vps = classify_vps_continuity(vps_facts)
    overall = forensics.get("overall") or {}
    settings = build_strategy_settings_audit()
    news = audit_news_protection()
    n = int(forensics.get("matched_count") or 0)
    paint = classify_conflict_paint(cycle)
    bottleneck = frequency_bottleneck(cycle, histograms)
    blocker = str(cycle.get("first_authoritative_blocker") or "").upper()
    decision_class = "B" if "NO_DIRECTIONAL_EDGE" in blocker else "A"
    return {
        "schema_version": "1.0.0",
        "advisory_only": True,
        "mutates_engines": False,
        "never_sends_orders": True,
        "never_lowers_opportunity_70": True,
        "never_lowers_edge_5": True,
        "live_order_sent": False,
        "mt5_ticket": None,
        "disclaimer": DISCLAIMER,
        "production_sha": PRODUCTION_SHA,
        "research_workflow": research_workflow(matched_n=n),
        "current_market": current_market_panel(cycle),
        "current_shadow": current_shadow,
        "shadow_dataset": shadow_dataset,
        "core_vs_expansion": shadow_dataset.get("core_vs_expansion")
        if isinstance(shadow_dataset, dict)
        else {},
        "funnel_histograms": histograms,
        "trade_frequency_bottleneck": bottleneck,
        "forensics": forensics,
        "shadow_expansion": shadow,
        "vps": vps,
        "settings_audit": settings,
        "news_protection": news,
        "sample_status": sample_status(n),
        "conflict_paint": paint,
        "decision_matrix": {
            "code": decision_class,
            "A": "legitimate market condition",
            "B": "legitimate strategy hold",
            "C": "proven over-selectivity",
            "D": "proven evidence-loss defect",
            "E": "observability defect",
            "F": "infrastructure/data defect",
            "G": "asymmetry defect",
            "H": "execution bottleneck",
            "I": "loss-producing strategy defect",
            "selected": decision_class,
            "C_proven": False,
            "I_proven": False,
            "sample_size": n,
            "confidence": sample_status(n),
        },
        "expansion_verdict": {
            "SAFE_EXPANSION_PROVEN": False,
            "verdict": ((shadow_dataset or {}).get("verdict") or {}).get(
                "text",
                "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA",
            ),
            "reason": "STRATEGY_MATCHED n=0; shadow virtual outcomes remain INSUFFICIENT_SAMPLE until future prints close research entries",
            "win_rate_80_90_supported": False,
            "shadow_observations": (shadow_dataset or {}).get("observations"),
            "shadow_virtual_completed": (shadow_dataset or {}).get("virtual_completed"),
        },
        "signals_persisted": len(list_signals()),
        "submissions_persisted": len(list_submissions()),
        "deal_source": deal_meta,
        "classification_contract": {
            "STRATEGY_MATCHED": STRATEGY_MATCHED,
            "UNMATCHED_BROKER_ACTIVITY": UNMATCHED,
            "time_window_join_forbidden": True,
        },
        "report": {
            "FIRST_PROVEN_LOSS_CAUSE": forensics.get("first_proven_loss_cause"),
            "LAST_PROFITABLE_TRADE": overall.get("last_profitable_trade"),
            "LAST_PROFITABLE_PERIOD": overall.get("last_profitable_day"),
            "BEST_WINNING_SETUP": overall.get("best_winning_setup"),
            "WORST_LOSING_SETUP": overall.get("worst_losing_setup"),
            "BUY_EXPECTANCY": forensics.get("BUY_EXPECTANCY"),
            "SELL_EXPECTANCY": forensics.get("SELL_EXPECTANCY"),
            "SESSION_EXPECTANCY": forensics.get("SESSION_EXPECTANCY"),
            "REGIME_EXPECTANCY": forensics.get("REGIME_EXPECTANCY"),
            "CURRENT_BOTTLENECK": bottleneck,
            "CURRENT_TRADE_FREQUENCY_BOTTLENECK": bottleneck,
            "WALK_FORWARD": INSUFFICIENT_SAMPLE if n < 20 else UNKNOWN,
            "SHADOW_CANDIDATES": [
                {
                    "candidate_name": c.get("candidate_name"),
                    "classification": c.get("classification"),
                    "sample_size": c.get("sample_size"),
                    "promotion_status": c.get("promotion_status"),
                }
                for c in (shadow.get("candidates") or [])
            ],
            "SHADOW_EXPANSION_CANDIDATES": [
                {
                    "candidate_name": c.get("candidate_name"),
                    "classification": c.get("classification"),
                    "sample_size": c.get("sample_size"),
                }
                for c in (shadow.get("candidates") or [])
            ],
            "BEST_SHADOW_CANDIDATE": shadow.get("best_expansion_candidate"),
            "BEST_EXPANSION_CANDIDATE": shadow.get("best_expansion_candidate"),
            "SHADOW_DATASET_N": (shadow_dataset or {}).get("observations"),
            "SHADOW_VIRTUAL_COMPLETED": (shadow_dataset or {}).get("virtual_completed"),
            "SHADOW_VERDICT": ((shadow_dataset or {}).get("verdict") or {}).get("text"),
            "CORE_VS_EXPANSION": (shadow_dataset or {}).get("core_vs_expansion"),
            "SAMPLE_SIZE": n,
            "OUT_OF_SAMPLE_RESULT": INSUFFICIENT_SAMPLE if n < 20 else UNKNOWN,
            "MAX_DRAWDOWN": overall.get("MAX_DRAWDOWN"),
            "PROFIT_FACTOR": overall.get("PROFIT_FACTOR"),
            "WIN_RATE": overall.get("WIN_RATE_DISPLAY") or overall.get("WIN_RATE"),
            "WIN_RATE_N": overall.get("sample_size"),
            "PROVEN_CODE_DEFECTS": False,
            "CODE_DEFECT_PROVEN": False,
            "LIVE_CHANGE_JUSTIFICATION": False,
            "TRADING_CHANGE_JUSTIFIED": False,
            "VPS_AUTONOMY": vps.get("vps_autonomy_status"),
            "VPS_AUTONOMY_STATUS": vps.get("vps_autonomy_status"),
            "MT5_REBOOT_RECOVERY": vps.get("mt5_reboot_recovery"),
            "MT5_REBOOT_RECOVERY_STATUS": vps.get("mt5_reboot_recovery"),
            "FILES_CHANGED": UNKNOWN,
            "TESTS": UNKNOWN,
            "COMMIT": "NO",
            "DEPLOYMENT": "NO",
            "ROLLBACK": "revert research observability files; production SHA unchanged",
            "LIVE_ORDER_SENT": "NO",
            "MT5_TICKET": "NONE",
            "NEWS_PROTECTION_STATUS": news.get("STATUS"),
            "SAFE_EXPANSION_PROVEN": False,
            "WIN_RATE_80_90_SUPPORTED": False,
        },
        "observed_at": cycle.get("recorded_at"),
    }
