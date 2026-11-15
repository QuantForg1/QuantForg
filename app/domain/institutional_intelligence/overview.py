"""Read-only overview builders for Phase 6 Institutional Intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_intelligence import (
    MODULE_ROUTES,
    RECOMMENDATION_STATUSES,
    data_quality,
    isolation_payload,
)
from app.domain.institutional_intelligence.recommendations import (
    get_recommendation_store,
)


def _safe_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return {"error": type(exc).__name__, "detail": str(exc)[:240]}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_hub_summary() -> dict[str, Any]:
    store = get_recommendation_store()
    recs = store.list_all(limit=20)
    return {
        "ok": True,
        "modules": list(MODULE_ROUTES),
        "recommendation_statuses": list(RECOMMENDATION_STATUSES),
        "pending_recommendations": sum(
            1 for r in recs if r.get("status") in {"Proposed", "Under Review"}
        ),
        "links": {
            "phase4_ati": "/ai-trading-intelligence",
            "phase5_operations": "/operations",
        },
        "data_quality": data_quality(
            source="institutional_intelligence.hub",
            as_of=_now(),
        ),
        **isolation_payload(),
    }


def build_market_overview(
    *,
    symbol: str = "XAUUSD",
    regime_label: str | None = None,
    regime_confidence: float | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    assessment: dict[str, Any] | None = None
    market: dict[str, Any] | None = None

    try:
        from app.domain.ai_trading_intelligence.regime import map_canonical_regime

        assessment_obj = map_canonical_regime(
            regime_label,
            confidence=regime_confidence,
        )
        conf = assessment_obj.confidence
        assessment = {
            "regime": getattr(
                assessment_obj.regime, "value", str(assessment_obj.regime)
            ),
            "confidence": float(conf) if conf is not None else None,
            "methodology": assessment_obj.methodology,
            "rationale": assessment_obj.rationale,
        }
    except Exception as exc:
        missing.append("regime")
        assessment = {"error": type(exc).__name__}

    try:
        from app.domain.ai_trading_intelligence.market_intelligence import (
            assemble_market_intelligence,
        )

        facts: dict[str, Any] = {
            "regime_label": regime_label or "unknown",
            "regime_confidence": regime_confidence
            if regime_confidence is not None
            else 40,
            "data_sources": ["caller_facts"],
            "confidence": regime_confidence if regime_confidence is not None else 40,
        }
        bundle = assemble_market_intelligence(symbol=symbol, facts=facts)
        reg = bundle.regime
        market = {
            "symbol": bundle.symbol,
            "regime": getattr(reg.regime, "value", str(reg.regime)) if reg else None,
            "notes": list(bundle.notes or []),
            "liquidity": bundle.liquidity,
            "trend": bundle.trend,
            "momentum": bundle.momentum,
            "volatility": bundle.volatility,
            "methodology": bundle.methodology,
        }
        if market.get("liquidity") is None:
            missing.append("liquidity")
    except Exception as exc:
        missing.append("market_intelligence")
        market = {"error": type(exc).__name__}

    # Forecast only when we have a regime assessment with confidence —
    # never invent prices or guarantee outcomes.
    forecast: dict[str, Any] | None = None
    if assessment and "error" not in assessment and assessment.get("regime"):
        forecast_conf = assessment.get("confidence")
        forecast = {
            "horizon": "intraday_session",
            "direction_bias": assessment.get("regime"),
            "confidence": forecast_conf,
            "model_version": isolation_payload()["model_version"],
            "data_timestamp": _now(),
            "supporting_evidence": [
                f"canonical_regime={assessment.get('regime')}",
                f"confidence={forecast_conf}",
            ],
            "limitations": [
                "Not a guaranteed future outcome",
                "Derived from supplied regime facts only",
                "Does not invent OHLC or liquidity",
            ],
            "guarantees_outcome": False,
        }
    else:
        missing.append("forecast_evidence")

    return {
        "ok": True,
        "module": "predictive_market_intelligence",
        "symbol": symbol,
        "regime": assessment,
        "market": market,
        "forecast": forecast,
        "historical_transitions": [],
        "historical_transitions_note": "unavailable_without_persisted_regime_timeline",
        "data_quality": data_quality(
            source="ati.regime+market_intelligence",
            as_of=_now(),
            stale=False,
            missing_fields=missing,
        ),
        **isolation_payload(),
    }


def build_strategy_overview(
    *,
    strategies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [r for r in (strategies or []) if isinstance(r, dict)]
    labeled: list[dict[str, Any]] = []
    for row in rows:
        result_class = str(
            row.get("result_class")
            or row.get("data_class")
            or row.get("source_class")
            or "unavailable"
        ).lower()
        if result_class not in {
            "backtest",
            "paper",
            "live",
            "simulated",
            "unavailable",
        }:
            result_class = "unavailable"
        raw_metrics = row.get("metrics")
        metrics: dict[str, Any] = (
            raw_metrics if isinstance(raw_metrics, dict) else {}
        )
        # Only pass through numeric metrics that are present — never invent.
        clean_metrics = {
            k: metrics[k]
            for k in (
                "net_profit",
                "gross_profit",
                "gross_loss",
                "win_rate",
                "profit_factor",
                "expectancy",
                "avg_win",
                "avg_loss",
                "max_drawdown",
                "recovery_factor",
                "sharpe",
                "sortino",
                "trade_count",
            )
            if k in metrics and isinstance(metrics[k], (int, float))
        }
        labeled.append(
            {
                "strategy_id": row.get("strategy_id") or row.get("id"),
                "name": row.get("name"),
                "version": row.get("version"),
                "result_class": result_class,
                "metrics": clean_metrics,
                "health": row.get("health"),
                "degradation": row.get("degradation"),
            }
        )

    return {
        "ok": True,
        "module": "strategy_analytics",
        "strategies": labeled,
        "strategy_count": len(labeled),
        "empty": len(labeled) == 0,
        "rules": {
            "never_mix_incompatible_result_classes": True,
            "never_fabricate_missing_metrics": True,
            "distinguish_backtest_paper_live": True,
        },
        "data_quality": data_quality(
            source="caller_or_sic_assembly",
            as_of=_now(),
            missing_fields=[] if labeled else ["strategies"],
        ),
        **isolation_payload(),
    }


def build_risk_overview(
    *,
    ati_alerts: list[dict[str, Any]] | None = None,
    irap: dict[str, Any] | None = None,
    phase5_risk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "module": "predictive_risk",
        "ati_alerts": ati_alerts or [],
        "ati_advisory_only": True,
        "irap": irap or {"status": "unavailable"},
        "phase5_risk": phase5_risk or {},
        "enforcement": {
            "hard_limits_priority": True,
            "ai_cannot_override_hard_constraints": True,
            "ui_cannot_raise_limits": True,
            "backend_authoritative": True,
            "risk_relaxation_requires_approval": True,
        },
        "scenario_analysis": {
            "available": False,
            "note": "Use IRAP/ISE stress desks when populated — no invented scenarios",
        },
        "data_quality": data_quality(
            source="ati.risk_alerts+irap+phase5",
            as_of=_now(),
            missing_fields=[] if (ati_alerts or irap) else ["risk_inputs"],
        ),
        **isolation_payload(),
    }


def build_portfolio_overview(
    *,
    qpm: dict[str, Any] | None = None,
    household: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qpm = qpm or {}
    household = household or {}
    missing: list[str] = []
    equity = household.get("equity")
    balance = household.get("balance")
    if equity is None and balance is None:
        missing.append("equity_or_balance")

    recommendations = qpm.get("recommendations") if isinstance(qpm, dict) else None
    if not isinstance(recommendations, list):
        recommendations = []

    return {
        "ok": True,
        "module": "portfolio_optimization",
        "qpm": {
            "keys": sorted(qpm.keys()) if qpm else [],
            "recommendations": recommendations[:50],
        },
        "household": {
            "equity_present": equity is not None,
            "balance_present": balance is not None,
            # Never invent numeric capital — only echo when provided.
            "equity": equity if isinstance(equity, (int, float)) else None,
            "balance": balance if isinstance(balance, (int, float)) else None,
        },
        "rules": {
            "never_auto_rebalance": True,
            "never_invent_capital": True,
            "recommendations_require_assumptions": True,
        },
        "data_quality": data_quality(
            source="qpm+household",
            as_of=_now(),
            missing_fields=missing,
        ),
        **isolation_payload(),
    }


def build_execution_overview(
    *,
    attempts: list[dict[str, Any]] | None = None,
    eqs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attempts = attempts or []
    total = len(attempts)
    accepted = 0
    rejected = 0
    latencies: list[float] = []
    slippages: list[float] = []
    for row in attempts:
        if not isinstance(row, dict):
            continue
        outcome = str(
            row.get("outcome") or row.get("status") or row.get("state") or ""
        ).lower()
        if outcome in {"accepted", "filled", "success", "executed"}:
            accepted += 1
        elif outcome in {"rejected", "failed", "error", "timeout"}:
            rejected += 1
        for key in ("latency_ms", "execution_latency_ms", "round_trip_ms"):
            raw = row.get(key)
            if isinstance(raw, (int, float)):
                latencies.append(float(raw))
                break
        for key in ("slippage", "slippage_pts", "slippage_pips"):
            raw = row.get(key)
            if isinstance(raw, (int, float)):
                slippages.append(float(raw))
                break

    return {
        "ok": True,
        "module": "execution_optimization",
        "metrics": {
            "attempt_count": total,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "success_rate": (accepted / total) if total else None,
            "rejection_rate": (rejected / total) if total else None,
            "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
            "avg_slippage": (sum(slippages) / len(slippages)) if slippages else None,
            "fabricated": False,
            "source": "persisted_execution_attempts",
        },
        "eqs": eqs or {},
        "empty": total == 0,
        "rules": {
            "signals_are_not_fills": True,
            "dispatch_is_not_fill": True,
            "requires_broker_mt5_confirmation": True,
            "never_auto_change_routing": True,
        },
        "data_quality": data_quality(
            source="execution_attempts",
            as_of=_now(),
            missing_fields=[] if total else ["attempts"],
        ),
        **isolation_payload(),
    }


def build_decision_overview() -> dict[str, Any]:
    store = get_recommendation_store()
    rows = store.list_all(limit=100)
    return {
        "ok": True,
        "module": "decision_intelligence",
        "statuses": list(RECOMMENDATION_STATUSES),
        "recommendations": rows,
        "count": len(rows),
        "rules": {
            "advisory_by_default": True,
            "approved_does_not_authorize_live": True,
            "required_fields": [
                "recommendation",
                "reasoning_summary",
                "supporting_evidence",
                "data_timestamp",
                "confidence",
                "expected_benefits",
                "risks_and_limitations",
                "affected_strategy_or_account",
                "required_approval",
                "status",
            ],
        },
        "deep_links": {
            "legacy_workspace": "/decision-intelligence",
            "qdie": "/quantforg-decision-intelligence",
            "ati": "/ai-trading-intelligence",
            "operations": "/operations",
        },
        "data_quality": data_quality(
            source="recommendation_store",
            as_of=_now(),
        ),
        **isolation_payload(),
    }


def build_reports_overview(
    *,
    catalogs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalogs = [c for c in (catalogs or []) if isinstance(c, dict)]
    return {
        "ok": True,
        "module": "institutional_reports",
        "catalogs": catalogs,
        "catalog_count": len(catalogs),
        "empty": len(catalogs) == 0,
        "rules": {
            "distinguish_actual_backtest_simulated": True,
            "incomplete_must_be_labeled": True,
            "never_present_incomplete_as_complete": True,
        },
        "data_quality": data_quality(
            source="composed_report_catalogs",
            as_of=_now(),
            missing_fields=[] if catalogs else ["catalogs"],
        ),
        **isolation_payload(),
    }


def build_data_quality_overview(
    *,
    qcdm: dict[str, Any] | None = None,
    idw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "module": "model_governance",
        "qcdm": qcdm or {"status": "unavailable"},
        "idw_quality": idw or {"status": "unavailable"},
        "model_version": isolation_payload()["model_version"],
        "evaluation": {
            "claims_accuracy_without_validation": False,
            "note": (
                "Use ATI regime/validation and CVF drift desks "
                "for measurable evaluation"
            ),
        },
        "data_quality": data_quality(
            source="qcdm+idw",
            as_of=_now(),
            missing_fields=[] if (qcdm or idw) else ["governance_sources"],
        ),
        **isolation_payload(),
    }
