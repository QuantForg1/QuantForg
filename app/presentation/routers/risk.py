"""Risk Management Engine API — evaluate only, never order_send."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.application.dto.risk_engine import RiskCheckCommand
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.risk import CheckRiskDep
from app.presentation.schemas.risk import RiskCheckRequest, RiskCheckResponse

router = APIRouter(prefix="/risk", tags=["risk-engine"])


@router.post("/check", response_model=RiskCheckResponse)
async def risk_check(
    body: RiskCheckRequest,
    request: Request,
    user: CurrentUser,
    check: CheckRiskDep,
) -> RiskCheckResponse:
    """Run the Risk Management Engine before Execution Gateway.

    Returns ALLOW | REDUCE_SIZE | REJECT. Never places an order.
    Never enables EXECUTION_ENABLED.
    """
    ip, ua = get_client_meta(request)
    dto = await check.execute(
        RiskCheckCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            side=body.side,
            requested_lots=body.requested_lots,
            stop_loss_distance=body.stop_loss_distance,
            atr=body.atr,
            sizing_method=body.sizing_method,
            entry_price=body.entry_price,
            peak_equity=body.peak_equity,
            daily_pnl=body.daily_pnl,
            weekly_pnl=body.weekly_pnl,
            monthly_pnl=body.monthly_pnl,
            equity=body.equity,
            balance=body.balance,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return RiskCheckResponse(
        id=dto.id,
        request_id=dto.request_id,
        symbol=dto.symbol,
        side=dto.side,
        decision=dto.decision,
        risk_score=dto.risk_score,
        risk_band=dto.risk_band,
        approved_lots=dto.approved_lots,
        requested_lots=dto.requested_lots,
        sizing_method=dto.sizing_method,
        warnings=list(dto.warnings),
        reasons=list(dto.reasons),
        exposure=dict(dto.exposure),
        drawdown=dict(dto.drawdown),
        checks=dict(dto.checks),
        rules=list(dto.rules),
        assessed_at=dto.assessed_at,
    )
