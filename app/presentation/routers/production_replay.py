"""Production Replay & Validation API — simulation only; never order_send."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.application.services.production_replay_validation import (
    report_to_markdown,
    run_production_replay,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/production-replay", tags=["production-replay"])

_last_report: dict[str, Any] | None = None


class RunReplayBody(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    max_evaluations: int = Field(default=120, ge=1, le=2000)


@router.get("/status")
async def production_replay_status(_user: CurrentUser) -> dict[str, Any]:
    """Summary of the last replay run, or an empty state — never fabricated."""
    if _last_report is None:
        return {
            "status": "empty",
            "message": "No production replay run yet.",
            "simulation_only": True,
        }
    stats = _last_report.get("statistics") or {}
    return {
        "status": "available",
        "generated_at": _last_report.get("generated_at"),
        "symbol": _last_report.get("symbol"),
        "params": _last_report.get("params"),
        "total_evaluations": stats.get("total_evaluations", 0),
        "signals": stats.get("signals", 0),
        "rejected": stats.get("rejected", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
        "simulation_only": True,
        "order_send_called": False,
    }


@router.post("/run")
async def production_replay_run(
    body: RunReplayBody, _user: CurrentUser
) -> dict[str, Any]:
    """Run a bounded simulation-only replay. Never calls order_send."""
    global _last_report
    report = await run_production_replay(
        days=body.days,
        max_evaluations=body.max_evaluations,
        equity=Decimal("10000"),
    )
    _last_report = report
    return report


@router.get("/report")
async def production_replay_report(_user: CurrentUser) -> dict[str, Any]:
    """Last full replay report — empty state until a run has occurred."""
    if _last_report is None:
        return {
            "status": "empty",
            "message": (
                "No production replay report yet. "
                "POST /production-replay/run first."
            ),
            "simulation_only": True,
        }
    return _last_report


@router.get("/report.md")
async def production_replay_report_markdown(_user: CurrentUser) -> Response:
    """Markdown export of the last replay report."""
    if _last_report is None:
        body = (
            "# Production Replay & Validation Report\n\n"
            "_No report yet — run POST /production-replay/run first._\n"
        )
    else:
        body = report_to_markdown(_last_report)
    return Response(content=body, media_type="text/markdown")
