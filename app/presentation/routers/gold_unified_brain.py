"""Gold Unified Brain API — observe-only coordination. Never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services.gold_unified_brain_service import (
    activation_workflow_document,
    build_gold_brain_status,
    decide_from_score,
    evidence_status,
    micro_account_xauusd_feasibility,
)
from app.domain.trading.gold_unified_brain import inventory_strategies
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/gold-unified-brain", tags=["gold-unified-brain"])


class DecideRequest(BaseModel):
    """Score snapshot for deterministic replay / coordination."""

    score: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
async def gold_brain_status(user: CurrentUser) -> dict[str, Any]:
    """Inventory, activation workflow, worker blockers, evidence honesty."""
    _ = user
    return build_gold_brain_status()


@router.get("/inventory")
async def gold_brain_inventory(user: CurrentUser) -> dict[str, Any]:
    """Live-eligible profiles vs catalog/UI-only modules."""
    _ = user
    return inventory_strategies()


@router.get("/activation-workflow")
async def gold_activation_workflow(user: CurrentUser) -> dict[str, Any]:
    """Official ARM → ENABLE prerequisites. Does not change controller state."""
    _ = user
    return activation_workflow_document()


@router.get("/evidence")
async def gold_evidence(user: CurrentUser) -> dict[str, Any]:
    """Evidence status — never fabricates OOS profitability."""
    _ = user
    return evidence_status()


@router.get("/micro-account-feasibility")
async def gold_micro_feasibility(
    user: CurrentUser,
    equity: str = "50",
) -> dict[str, Any]:
    """XAUUSD min-lot risk feasibility for a given equity."""
    _ = user
    return micro_account_xauusd_feasibility(equity)


@router.post("/decide")
async def gold_decide(
    body: DecideRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Coordinate live-eligible strategies. Advisory only — never ENABLE."""
    _ = user
    return decide_from_score(body.score)
