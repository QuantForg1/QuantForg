"""OpenAI advisor API — advisory only; never order_send / never Gemini."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services.openai_advisor_service import advice_cannot_bypass_risk
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.openai_advisor import OpenAIAdvisorDep

router = APIRouter(prefix="/openai", tags=["openai-advisor"])


class AdviseRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market_snapshot: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
async def openai_status(
    user: CurrentUser,
    advisor: OpenAIAdvisorDep,
) -> dict[str, Any]:
    """Provider configuration status — never returns the API key."""
    _ = user
    payload = advisor.provider_status().to_dict()
    payload["gemini"] = False
    return payload


@router.post("/advise")
async def openai_advise(
    body: AdviseRequest,
    user: CurrentUser,
    advisor: OpenAIAdvisorDep,
) -> dict[str, Any]:
    """Structured advisory recommendation. Does not authorize execution."""
    _ = user
    advice = await advisor.advise(
        symbol=body.symbol,
        market_snapshot=body.market_snapshot,
    )
    assert advice_cannot_bypass_risk(advice)
    payload = advice.to_dict()
    payload["authorizes_trade"] = False
    payload["execution_hint"] = (
        "Advice is non-authoritative. Risk Engine and EXECUTION_ENABLED gates "
        "remain authoritative; AI cannot place orders."
    )
    return payload
