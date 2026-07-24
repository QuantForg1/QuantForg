"""Candidate Validation API — offline research A/B only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/candidate-validation", tags=["candidate-validation"])

_last_report: dict[str, Any] | None = None


class RunBody(BaseModel):
    days: int = Field(default=90, ge=1, le=365)
    max_evaluations: int = Field(default=120, ge=1, le=500)


@router.get("/status")
async def status(_user: CurrentUser) -> dict[str, Any]:
    if _last_report is None:
        return {
            "status": "empty",
            "message": "No candidate validation run yet.",
            "never_modifies_production": True,
        }
    return {
        "status": "available",
        "generated_at": _last_report.get("generated_at"),
        "decision": _last_report.get("decision"),
        "never_modifies_production": True,
    }


@router.post("/run")
async def run_validation(body: RunBody, _user: CurrentUser) -> dict[str, Any]:
    global _last_report
    from app.application.services.candidate_validation import run_candidate_validation

    report = await run_candidate_validation(
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
            "message": "POST /candidate-validation/run first.",
            "never_modifies_production": True,
        }
    return _last_report


@router.get("/export.pdf")
async def export_pdf(_user: CurrentUser) -> Response:
    from app.application.services.candidate_validation import build_pdf_bytes

    body = build_pdf_bytes(
        _last_report
        or {
            "generated_at": None,
            "symbol": "XAUUSD",
            "source_evaluations": 0,
            "production": {"quality_gate": 80, "confluence_gate": 80},
            "candidate": {"quality_gate": 70, "confluence_gate": 75},
            "comparison": [],
            "decision": {
                "summary": "Recommend keeping Q80/C80. No run yet."
            },
        }
    )
    return Response(
        content=body,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=candidate_validation.pdf"
        },
    )
