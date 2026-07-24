"""Observability hooks for production hardening — no architecture change."""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def record_lifecycle(
    *,
    stage: str,
    status: str,
    detail: str,
    trace_id: str | None = None,
    latency_ms: float | None = None,
    symbol: str | None = None,
    ticket: str | None = None,
) -> None:
    try:
        from app.domain.institutional_trading.production_hardening.lifecycle import (
            get_lifecycle_store,
        )

        get_lifecycle_store().record(
            stage=stage,
            status=status,
            detail=detail,
            trace_id=trace_id,
            latency_ms=latency_ms,
            symbol=symbol,
            ticket=ticket,
        )
    except Exception:
        logger.exception("hardening_lifecycle_hook_failed")


def observe_oms_outcome(
    *,
    trace_id: str | None,
    symbol: str | None,
    forwarded: bool,
    success: bool,
    latency_ms: float | None,
    retcode: int | None,
    message: str | None,
    ticket: Any = None,
    slippage: float | None = None,
    spread: float | None = None,
    retries: int = 0,
) -> None:
    try:
        from app.domain.institutional_trading.production_hardening.incidents import (
            get_incident_detector,
        )
        from app.domain.institutional_trading.production_hardening.performance import (
            get_live_performance_monitor,
        )

        mon = get_live_performance_monitor()
        det = get_incident_detector()
        if forwarded:
            mon.record_submit()
            record_lifecycle(
                stage="OMS",
                status="ok" if success else "failed",
                detail=message or ("filled" if success else "rejected"),
                trace_id=trace_id,
                latency_ms=latency_ms,
                symbol=symbol,
                ticket=str(ticket) if ticket is not None else None,
            )
            record_lifecycle(
                stage="MT5_GATEWAY",
                status="ok" if success else "failed",
                detail=f"retcode={retcode}",
                trace_id=trace_id,
                symbol=symbol,
                ticket=str(ticket) if ticket is not None else None,
            )
            record_lifecycle(
                stage="BROKER",
                status="ok" if success else "failed",
                detail=(message or "")[:240],
                trace_id=trace_id,
                symbol=symbol,
                ticket=str(ticket) if ticket is not None else None,
            )
            record_lifecycle(
                stage="CONFIRMATION",
                status="ok" if success else "failed",
                detail="confirmed" if success else "not confirmed",
                trace_id=trace_id,
                symbol=symbol,
                ticket=str(ticket) if ticket is not None else None,
            )
            if success:
                mon.record_fill(latency_ms=latency_ms, slippage=slippage)
                if ticket is not None:
                    record_lifecycle(
                        stage="POSITION_MONITOR",
                        status="started",
                        detail="position registered for PME",
                        trace_id=trace_id,
                        symbol=symbol,
                        ticket=str(ticket),
                    )
            else:
                mon.record_reject(latency_ms=latency_ms)
                det.on_broker_reject(message=message or "", retcode=retcode)
            if retries:
                mon.record_retry(retries)
            if latency_ms is not None:
                det.on_high_latency(latency_ms=latency_ms)
            if slippage is not None:
                det.on_high_slippage(slippage=slippage)
            if spread is not None:
                mon.record_spread(spread)
    except Exception:
        logger.exception("hardening_oms_observe_failed")


def store_trade_explanation(
    *,
    decision: Any,
    ticket: str | None,
    risk_pct: str | None = None,
    extras: dict[str, Any] | None = None,
) -> None:
    try:
        from app.domain.institutional_trading.production_hardening.explainability import (
            build_explanation,
            get_explainability_store,
        )

        conf = getattr(decision, "confidence", None)
        confluence = getattr(decision, "confluence", None)
        if conf is None and confluence is not None:
            conf = getattr(confluence, "confidence", None)
        reasons = tuple(getattr(decision, "reasons", ()) or ())
        symbol = str(getattr(decision, "symbol", "") or "")
        direction = str(
            getattr(getattr(decision, "direction", None), "value", None)
            or getattr(decision, "direction", "")
            or ""
        )
        lots = getattr(decision, "approved_lots", None)
        stop = getattr(decision, "stop_zone", None)
        target = getattr(decision, "target_zone", None)
        session = getattr(decision, "session", None) or getattr(
            decision, "session_label", None
        )
        regime = getattr(decision, "regime", None) or getattr(
            decision, "market_regime", None
        )
        snap = getattr(decision, "snapshot", None)
        if session is None and snap is not None:
            sess = getattr(snap, "session", None)
            session = getattr(sess, "name", None) or getattr(sess, "label", None)
        if regime is None and snap is not None:
            regime = getattr(snap, "regime", None)

        why_entered = "; ".join(str(r) for r in reasons[:8]) or "AI decision approved"
        expl = build_explanation(
            symbol=symbol,
            direction=direction,
            ticket=ticket,
            why_entered=why_entered,
            why_risk_pct=f"risk_per_trade={risk_pct or 'plane/default'}%",
            why_lot_size=f"approved_lots={lots}",
            why_tp=f"target_zone={getattr(target, 'mid', target)}",
            why_sl=f"stop_zone={getattr(stop, 'mid', stop)}",
            why_confidence=f"confidence={conf}",
            why_symbol=f"symbol selected={symbol}",
            why_session=f"session={session or 'unknown'}",
            why_regime=f"regime={regime or 'unknown'}",
            extras=extras,
        )
        get_explainability_store().record(expl)
    except Exception:
        logger.exception("hardening_explainability_failed")
