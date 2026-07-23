"""Threshold Performance Analysis API — offline research only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/threshold-performance-analysis",
    tags=["threshold-performance-analysis"],
)

_last_report: dict[str, Any] | None = None


class RunBody(BaseModel):
    days: int = Field(default=90, ge=1, le=365)
    max_evaluations: int = Field(default=120, ge=1, le=500)


@router.get("/status")
async def status(_user: CurrentUser) -> dict[str, Any]:
    if _last_report is None:
        return {
            "status": "empty",
            "message": "No threshold performance analysis run yet.",
            "research_only": True,
            "never_modifies_thresholds": True,
        }
    return {
        "status": "available",
        "generated_at": _last_report.get("generated_at"),
        "evaluations": _last_report.get("evaluations"),
        "recommendation": _last_report.get("recommendation"),
        "research_only": True,
        "never_modifies_thresholds": True,
    }


@router.post("/run")
async def run_analysis(body: RunBody, _user: CurrentUser) -> dict[str, Any]:
    """Independent gate-matrix replay. Never mutates live engines/thresholds."""
    global _last_report
    from app.application.services.threshold_performance_analysis import (
        run_threshold_performance_analysis,
    )

    report = await run_threshold_performance_analysis(
        days=body.days,
        max_evaluations=body.max_evaluations,
    )
    _last_report = report
    return report


@router.get("/report")
async def get_report(_user: CurrentUser) -> dict[str, Any]:
    if _last_report is None:
        return {
            "status": "empty",
            "message": "POST /threshold-performance-analysis/run first.",
            "research_only": True,
        }
    return _last_report


@router.get("/export.csv")
async def export_csv(_user: CurrentUser) -> Response:
    from app.application.services.threshold_performance_analysis import matrix_to_csv

    if _last_report is None:
        return Response(
            content="quality_gate,confluence_gate\n",
            media_type="text/csv",
        )
    return Response(
        content=matrix_to_csv(_last_report),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=threshold_performance.csv"
        },
    )


@router.get("/export.pdf")
async def export_pdf(_user: CurrentUser) -> Response:
    from app.application.services.threshold_performance_analysis import build_pdf_bytes

    if _last_report is None:
        empty = {
            "generated_at": None,
            "symbol": "XAUUSD",
            "evaluations": 0,
            "recommendation": {
                "summary": "Keep production thresholds unchanged. No run yet."
            },
            "rankings": {},
            "matrix": [],
            "params": {},
        }
        body = build_pdf_bytes(empty)
    else:
        body = build_pdf_bytes(_last_report)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=threshold_performance.pdf"
        },
    )
