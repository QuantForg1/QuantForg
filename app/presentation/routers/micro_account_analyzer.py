"""Micro Account Analyzer API — Operations desk (never mutates Institutional Mode)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/micro-account-analyzer", tags=["micro-account-analyzer"])


class AnalyzeBody(BaseModel):
    balance: str = Field(default="50")
    risk_pct: str = Field(default="2.00")
    atr: str | None = None
    use_live_broker: bool = True
    use_live_atr: bool = True


def _dec(value: str | None, default: Decimal) -> Decimal:
    if value is None or str(value).strip() == "":
        return default
    try:
        d = Decimal(str(value).strip())
        return d if d > 0 else default
    except (InvalidOperation, ValueError):
        return default


@router.get("/profiles")
async def profiles(_user: CurrentUser) -> dict[str, Any]:
    from app.domain.institutional_trading.micro_account_analyzer import (
        institutional_profile_dict,
        micro_profile_dict,
    )

    return {
        "INSTITUTIONAL": institutional_profile_dict(),
        "MICRO_ACCOUNT_MODE": micro_profile_dict(),
        "institutional_mode_modified": False,
    }


@router.get("/analyze")
async def analyze_get(
    _user: CurrentUser,
    balance: str = Query(default="50"),
    risk_pct: str = Query(default="2.00"),
    atr: str | None = Query(default=None),
    use_live_broker: bool = Query(default=True),
    use_live_atr: bool = Query(default=True),
) -> dict[str, Any]:
    from app.application.services.micro_account_analyzer import (
        run_micro_account_analyzer,
    )

    return run_micro_account_analyzer(
        balance=_dec(balance, Decimal("50")),
        risk_pct=_dec(risk_pct, Decimal("2.00")),
        atr=_dec(atr, Decimal("0")) if atr else None,
        use_live_broker=use_live_broker,
        use_live_atr=use_live_atr,
    )


@router.post("/analyze")
async def analyze_post(body: AnalyzeBody, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.micro_account_analyzer import (
        run_micro_account_analyzer,
    )

    atr_val: Decimal | None = None
    if body.atr is not None and str(body.atr).strip():
        atr_val = _dec(body.atr, Decimal("0"))
        if atr_val <= 0:
            atr_val = None
    return run_micro_account_analyzer(
        balance=_dec(body.balance, Decimal("50")),
        risk_pct=_dec(body.risk_pct, Decimal("2.00")),
        atr=atr_val,
        use_live_broker=body.use_live_broker,
        use_live_atr=body.use_live_atr,
    )
