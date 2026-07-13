"""Portfolio Intelligence & Risk Laboratory API — analytics only, never order_send."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from app.application.dto.paper import PaperHistoryCommand
from app.domain.portfolio_intelligence import analyze_trades, attribute_returns
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.portfolio import PortfolioDep
from app.presentation.dependencies.portfolio_intelligence import PortfolioIntelDep
from app.presentation.schemas.portfolio_intelligence import (
    LabSnapshotRequest,
    OptimizeRequest,
)
from core.di.container import get_container

router = APIRouter(prefix="/portfolio-intelligence", tags=["portfolio-intelligence"])


def _account_dict(account: Any) -> dict[str, Any]:
    return {
        "equity": account.equity,
        "balance": account.balance,
        "margin": account.margin,
        "free_margin": account.free_margin,
        "leverage": account.leverage,
        "currency": account.currency,
        "profit": account.profit,
    }


def _position_dict(p: Any) -> dict[str, Any]:
    return {
        "ticket": p.ticket,
        "symbol": p.symbol,
        "side": p.side,
        "volume": p.volume,
        "open_price": p.open_price,
        "current_price": p.current_price,
        "profit": p.profit,
        "swap": p.swap,
        "magic": p.magic,
        "comment": p.comment,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
    }


def _deal_dict(d: Any) -> dict[str, Any]:
    return {
        "ticket": d.ticket,
        "symbol": d.symbol,
        "side": d.side,
        "volume": d.volume,
        "price": d.price,
        "profit": d.profit,
        "commission": d.commission,
        "swap": d.swap,
        "deal_type": d.deal_type,
        "time": d.time.isoformat() if d.time else None,
        "comment": getattr(d, "comment", ""),
        "magic": getattr(d, "magic", 0),
    }


async def _load_live_snapshot(
    user_id: UUID, portfolio: Any
) -> tuple[
    bool, str | None, dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]
]:
    try:
        dto = await portfolio.execute(user_id=user_id)
    except Exception as exc:
        return False, str(exc), None, [], []
    account = _account_dict(dto.account)
    positions = [_position_dict(p) for p in dto.positions]
    deals = [_deal_dict(d) for d in dto.history_deals]
    return True, None, account, positions, deals


async def _paper_trades(user_id: UUID) -> list[dict[str, Any]]:
    if getattr(get_container(), "paper_uow_factory", None) is None:
        return []
    try:
        from app.presentation.dependencies.paper import get_paper_history

        uc = get_paper_history()
        dto = await uc.execute(PaperHistoryCommand(user_id=user_id, limit=500))
        trades: list[dict[str, Any]] = []
        for t in dto.trades:
            trades.append(
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "profit": t.pnl,
                    "pnl": t.pnl,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                    "strategy": "paper",
                }
            )
        return trades
    except Exception:
        return []


@router.get("/dashboard")
async def portfolio_intelligence_dashboard(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
    confidence: float = Query(default=0.95, gt=0.5, lt=1.0),
) -> dict[str, Any]:
    """Full risk laboratory snapshot from live MT5 portfolio + deals."""
    ok, reason, account, positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    paper = await _paper_trades(user.id)
    return intel.build_lab(
        account=account,
        positions=positions,
        deals=deals,
        paper_trades=paper,
        confidence=confidence,
        portfolio_available=ok,
        portfolio_unavailable_reason=reason,
    )


@router.post("/analyze")
async def portfolio_intelligence_analyze(
    body: LabSnapshotRequest,
    user: CurrentUser,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    """Offline / supplied-snapshot analysis (caller must provide real data)."""
    _ = user
    available = body.account is not None or bool(body.positions) or bool(body.deals)
    return intel.build_lab(
        account=body.account,
        positions=body.positions,
        deals=body.deals,
        paper_trades=body.paper_trades,
        confidence=body.confidence,
        optimize={
            "max_risk_pct": body.max_risk_pct,
            "max_allocation_pct": body.max_allocation_pct,
            "target_volatility": body.target_volatility,
            "target_return": body.target_return,
        },
        portfolio_available=available,
        portfolio_unavailable_reason=(
            None if available else "Empty snapshot — no invented portfolio"
        ),
    )


@router.get("/risk")
async def portfolio_intelligence_risk(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
    confidence: float = Query(default=0.95, gt=0.5, lt=1.0),
) -> dict[str, Any]:
    ok, reason, account, positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    return intel.compute_risk(
        account=account,
        positions=positions,
        deals=deals,
        confidence=confidence,
        portfolio_available=ok,
        portfolio_unavailable_reason=reason,
    )


@router.get("/stress")
async def portfolio_intelligence_stress(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    ok, _reason, account, positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    return intel.compute_stress(
        account=account,
        positions=positions,
        deals=deals,
        portfolio_available=ok,
    )


@router.get("/correlation")
async def portfolio_intelligence_correlation(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    ok, reason, _account, positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    if not ok:
        return {
            "status": "unavailable",
            "reason": reason,
            "labels": [],
            "matrix": [],
            "heatmap": [],
            "clusters": [],
            "diversification_score": None,
        }
    return intel.compute_correlation(positions=positions, deals=deals)


@router.get("/journal")
async def portfolio_intelligence_journal(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    _ = intel
    ok, _reason, _account, _positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    paper = await _paper_trades(user.id)
    return analyze_trades((deals if ok else []) + paper)


@router.get("/attribution")
async def portfolio_intelligence_attribution(
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    _ = intel
    ok, _reason, _account, _positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    paper = await _paper_trades(user.id)
    return attribute_returns((deals if ok else []) + paper)


@router.post("/optimize")
async def portfolio_intelligence_optimize(
    body: OptimizeRequest,
    user: CurrentUser,
    portfolio: PortfolioDep,
    intel: PortfolioIntelDep,
) -> dict[str, Any]:
    """Deterministic allocation recommendation — never places trades."""
    if body.positions is not None or body.deals is not None or body.account is not None:
        return intel.compute_optimizer(
            positions=body.positions or [],
            deals=body.deals or [],
            max_risk_pct=body.max_risk_pct,
            max_allocation_pct=body.max_allocation_pct,
            target_volatility=body.target_volatility,
            target_return=body.target_return,
        )
    ok, reason, _account, positions, deals = await _load_live_snapshot(
        user.id, portfolio
    )
    if not ok:
        return {
            "status": "unavailable",
            "reason": reason,
            "recommendations": [],
            "autonomous_trading": False,
        }
    return intel.compute_optimizer(
        positions=positions,
        deals=deals,
        max_risk_pct=body.max_risk_pct,
        max_allocation_pct=body.max_allocation_pct,
        target_volatility=body.target_volatility,
        target_return=body.target_return,
    )
