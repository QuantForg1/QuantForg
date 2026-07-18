"""Execution Intelligence API — lifecycle + analytics.

Never order_send / never flip EXECUTION_ENABLED.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.application.dto.paper import PaperHistoryCommand
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.execution import get_execution_uow_factory
from app.presentation.dependencies.execution_intelligence import ExecutionIntelDep
from app.presentation.schemas.execution_intelligence import (
    ChecklistRequest,
    ObserveLifecycleRequest,
    PostTradeRequest,
)
from core.config.settings import get_settings
from core.di.container import get_container

router = APIRouter(prefix="/execution-intelligence", tags=["execution-intelligence"])


async def _load_attempts(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        factory = get_execution_uow_factory()
    except RuntimeError:
        return []
    try:
        async with factory() as uow:
            rows = await uow.attempts.list_for_user(user_id, limit=limit)
            return [a.to_dict() for a in rows]
    except Exception:
        return []


async def _load_decisions(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        factory = get_execution_uow_factory()
    except RuntimeError:
        return []
    try:
        async with factory() as uow:
            rows = await uow.decisions.list_recent_for_user(user_id, limit=limit)
            return [d.to_dict() for d in rows]
    except Exception:
        return []


async def _load_paper_trades(user_id: UUID) -> list[dict[str, Any]]:
    if getattr(get_container(), "paper_uow_factory", None) is None:
        return []
    try:
        from app.presentation.dependencies.paper import get_paper_history

        uc = get_paper_history()
        dto = await uc.execute(PaperHistoryCommand(user_id=user_id, limit=200))
        out: list[dict[str, Any]] = []
        for t in dto.trades:
            out.append(
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "pnl": t.pnl,
                    "profit": t.pnl,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "fill_price": t.exit_price,
                    "requested_price": t.entry_price,
                    "slippage": t.slippage,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                    "data_source": "paper_trades",
                }
            )
        return out
    except Exception:
        return []


async def _mt5_broker_facts(user_id: UUID) -> dict[str, Any]:
    container = get_container()
    adapter = getattr(container, "mt5_adapter", None)
    mt5_uow = getattr(container, "mt5_uow_factory", None)
    connected: bool | None = None
    status: str | None = None
    latency_ms: float | None = None
    last_hb: str | None = None
    last_err: str | None = None
    reconnects: list[dict[str, Any]] = []
    uptime: float | None = None

    if adapter is not None:
        try:
            connected = bool(adapter.is_live_session)
        except Exception:
            connected = None

    if mt5_uow is not None:
        try:
            async with mt5_uow() as uow:
                conn = await uow.connections.get_active_for_user(user_id)
                if conn is not None:
                    connected = bool(conn.connected)
                    status = str(
                        conn.status.value
                        if hasattr(conn.status, "value")
                        else conn.status
                    )
                    latency_ms = (
                        float(conn.latency_ms)
                        if getattr(conn, "latency_ms", None) is not None
                        else None
                    )
                    if getattr(conn, "last_heartbeat_at", None):
                        last_hb = conn.last_heartbeat_at.isoformat()
                    last_err = getattr(conn, "last_error", "") or None
                    history = getattr(conn, "history", None) or []
                    for h in history:
                        if isinstance(h, dict):
                            reconnects.append(h)
                        else:
                            reconnects.append({"event": str(h)})
        except Exception:
            # Optional enrichment — leave diagnostics unavailable
            connected = connected

    return {
        "connected": connected,
        "status": status,
        "latency_ms": latency_ms,
        "last_heartbeat_at": last_hb,
        "last_disconnect_reason": last_err,
        "reconnect_events": reconnects,
        "uptime_seconds": uptime,
    }


@router.get("/dashboard")
async def execution_intelligence_dashboard(
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    """Full execution intelligence snapshot (read-only analytics)."""
    settings = get_settings()
    attempts = await _load_attempts(user.id)
    decisions = await _load_decisions(user.id)
    trades = await _load_paper_trades(user.id)
    broker = await _mt5_broker_facts(user.id)
    fills = [
        {
            "slippage": t.get("slippage"),
            "requested_price": t.get("requested_price"),
            "fill_price": t.get("fill_price"),
        }
        for t in trades
    ]
    checklist_facts = {
        "broker_connected": broker.get("connected"),
        "market_open": None,
        "risk_passed": None,
        "margin_sufficient": None,
        "strategy_signal_valid": None,
    }
    # Derive soft facts from latest decision when present
    if decisions:
        latest = decisions[0]
        checklist_facts["risk_passed"] = (
            str(latest.get("decision", "")).lower() == "allow"
        )
        calc = latest.get("calculated_risk") or {}
        if isinstance(calc, dict) and calc.get("free_margin") is not None:
            try:
                checklist_facts["margin_sufficient"] = float(calc["free_margin"]) > 0
            except (TypeError, ValueError):
                checklist_facts["margin_sufficient"] = None
        checks = latest.get("checks") or {}
        if isinstance(checks, dict) and "trading_hours" in checks:
            checklist_facts["market_open"] = bool(checks.get("trading_hours"))

    return intel.dashboard(
        user_id=str(user.id),
        attempts=attempts,
        decisions=decisions,
        fills=fills,
        trades=trades,
        checklist_facts=checklist_facts,
        broker_facts=broker,
        execution_enabled=bool(settings.execution_enabled),
        recent_risk=decisions,
    )


@router.get("/lifecycle")
async def execution_lifecycle_list(
    user: CurrentUser,
    intel: ExecutionIntelDep,
    limit: int = Query(default=50, ge=1, le=200),
    include_archived: bool = Query(default=True),
) -> dict[str, Any]:
    attempts = await _load_attempts(user.id)
    decisions = await _load_decisions(user.id)
    intel.ingest_decisions(user_id=str(user.id), decisions=decisions)
    intel.ingest_attempts(user_id=str(user.id), attempts=attempts)
    items = intel.store.list_for_user(
        str(user.id), limit=limit, include_archived=include_archived
    )
    return {"items": items, "count": len(items)}


@router.get("/lifecycle/{request_id}")
async def execution_lifecycle_get(
    request_id: str,
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    rec = intel.store.get(str(user.id), request_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Lifecycle not found")
    return rec


@router.post("/lifecycle/observe")
async def execution_lifecycle_observe(
    body: ObserveLifecycleRequest,
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    """Record a real lifecycle transition (never places orders)."""
    result = intel.observe(
        user_id=str(user.id),
        request_id=body.request_id,
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        volume=body.volume,
        state=body.state,
        reason=body.reason,
        source=body.source,
        meta=body.meta,
        force=body.force,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "observe failed",
        )
    return result


@router.post("/checklist")
async def execution_pretrade_checklist(
    body: ChecklistRequest,
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    """Deterministic pre-trade checklist — does not enable execution."""
    _ = user
    settings = get_settings()
    broker = body.broker_connected
    if broker is None:
        facts = await _mt5_broker_facts(user.id)
        broker = facts.get("connected")
    return intel.checklist(
        broker_connected=broker,
        market_open=body.market_open,
        risk_passed=body.risk_passed,
        margin_sufficient=body.margin_sufficient,
        strategy_signal_valid=body.strategy_signal_valid,
        execution_enabled=bool(settings.execution_enabled),
    )


@router.get("/analytics")
async def execution_analytics(
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    attempts = await _load_attempts(user.id)
    trades = await _load_paper_trades(user.id)
    fills = [
        {
            "slippage": t.get("slippage"),
            "requested_price": t.get("requested_price"),
            "fill_price": t.get("fill_price"),
        }
        for t in trades
    ]
    return intel.analytics(attempts=attempts, fills=fills)


@router.get("/post-trade")
async def execution_post_trade(
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    trades = await _load_paper_trades(user.id)
    return intel.post_trade(trades=trades)


@router.post("/post-trade/analyze")
async def execution_post_trade_analyze(
    body: PostTradeRequest,
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    _ = user
    return intel.post_trade(trades=body.trades)


@router.get("/broker")
async def execution_broker_diagnostics(
    user: CurrentUser,
    intel: ExecutionIntelDep,
) -> dict[str, Any]:
    facts = await _mt5_broker_facts(user.id)
    return intel.broker_diagnostics(**facts)
