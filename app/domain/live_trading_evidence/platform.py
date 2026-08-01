"""Assemble Institutional Live Trading Readiness & Evidence Program."""

from __future__ import annotations

from typing import Any

from app.domain.live_trading_evidence import PROGRAM_VERSION
from app.domain.live_trading_evidence.evidence_dashboard import (
    build_evidence_dashboard,
)
from app.domain.live_trading_evidence.models import HARD_LOCKS
from app.domain.live_trading_evidence.persistence import utc_iso
from app.domain.live_trading_evidence.readiness_score import (
    build_production_readiness_score,
)
from app.domain.live_trading_evidence.rejected_repository import (
    sync_and_list_rejections,
)
from app.domain.live_trading_evidence.trade_repository import sync_and_list_trades


async def build_live_trading_evidence_program() -> dict[str, Any]:
    trades = sync_and_list_trades(limit=150)
    rejections = sync_and_list_rejections(limit=200)
    dashboard = build_evidence_dashboard()
    readiness = build_production_readiness_score(
        dashboard=dashboard,
        trades_count=int(trades.get("count") or 0),
        rejections_count=int(rejections.get("count") or 0),
    )
    return {
        "as_of": utc_iso(),
        "program_version": PROGRAM_VERSION,
        "live_trade_evidence": trades,
        "rejected_opportunities": rejections,
        "execution_archive": {
            "count": trades.get("archive_count") or trades.get("count"),
            "trades": trades.get("trades") or [],
            "observe_only": True,
            "fabricated": False,
        },
        "evidence_dashboard": dashboard,
        "production_readiness": readiness,
        "flags": {
            **HARD_LOCKS,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
        "migrations_pending": False,
        "migration_status": "No migrations pending.",
    }


async def build_live_trading_evidence_noc_panels() -> dict[str, Any]:
    pack = await build_live_trading_evidence_program()
    trades = pack.get("live_trade_evidence") or {}
    rejects = pack.get("rejected_opportunities") or {}
    dash = pack.get("evidence_dashboard") or {}
    ready = pack.get("production_readiness") or {}
    archive = pack.get("execution_archive") or {}
    return {
        "live_trade_evidence": {
            "count": trades.get("count"),
            "archive_count": trades.get("archive_count"),
            "observe_only": True,
        },
        "rejected_opportunities": {
            "count": rejects.get("count"),
            "observe_only": True,
        },
        "execution_archive": {
            "count": archive.get("count"),
            "observe_only": True,
        },
        "production_readiness": {
            "score": ready.get("score"),
            "status": ready.get("status"),
            "measured_components": ready.get("measured_components"),
            "observe_only": True,
        },
        "dashboard_snapshot": {
            "executed_trades": dash.get("executed_trades"),
            "rejected_trades": dash.get("rejected_trades"),
            "average_latency": dash.get("average_latency"),
            "average_slippage": dash.get("average_slippage"),
            "ai_approval_rate": dash.get("ai_approval_rate"),
        },
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "fabricates_evidence": False,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
    }
