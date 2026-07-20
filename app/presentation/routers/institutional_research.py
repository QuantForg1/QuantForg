"""ITE Research Platform API — Phase E operator surface (read/run research only)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.application.services.institutional_research_platform import (
    InstitutionalResearchPlatform,
)
from app.domain.institutional_trading.research.models import (
    ResearchBar,
    WalkForwardMode,
)
from app.domain.institutional_trading.research.simulation_engine import (
    RuleSignalProvider,
)

router = APIRouter(prefix="/ite/research", tags=["ite-research"])

_platform = InstitutionalResearchPlatform()


class BarDTO(BaseModel):
    time: str
    open: str
    high: str
    low: str
    close: str
    session: str = ""


class SimulateRequest(BaseModel):
    bars: list[BarDTO]
    persist: bool = True


def _parse_bars(raw: list[BarDTO]) -> list[ResearchBar]:
    from datetime import datetime

    out: list[ResearchBar] = []
    for b in raw:
        out.append(
            ResearchBar(
                time=datetime.fromisoformat(b.time.replace("Z", "+00:00")),
                open=Decimal(b.open),
                high=Decimal(b.high),
                low=Decimal(b.low),
                close=Decimal(b.close),
                session=b.session,
            )
        )
    return out


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "E", "engine": "ite-research"}


@router.post("/simulate")
def simulate(body: SimulateRequest) -> dict[str, Any]:
    if not body.bars:
        raise HTTPException(status_code=400, detail="bars required")
    bars = _parse_bars(body.bars)
    result = _platform.run_simulation(bars, RuleSignalProvider(), persist=body.persist)
    return result.to_dict()


@router.get("/versions")
def list_versions(limit: int = 50) -> dict[str, Any]:
    return {
        "runs": _platform.versions.list(limit=limit),
        "count": _platform.versions.count(),
    }


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    return _platform.operator_dashboard()


class PromoteRequest(BaseModel):
    # Operator supplies analytics snapshot from a stored run
    trade_count: int
    profit_factor: str | None = None
    max_drawdown_pct: str = "0"
    expectancy: str = "0"
    walk_forward_passed: bool = False
    monte_carlo_passed: bool = False


@router.post("/promotion/evaluate")
def evaluate_promotion(body: PromoteRequest) -> dict[str, Any]:
    from app.domain.institutional_trading.research.models import AnalyticsReport

    analytics = AnalyticsReport(
        win_rate=Decimal("0"),
        expectancy=Decimal(body.expectancy),
        profit_factor=Decimal(body.profit_factor) if body.profit_factor else None,
        average_rr=None,
        max_drawdown_pct=Decimal(body.max_drawdown_pct),
        sharpe=None,
        sortino=None,
        calmar=None,
        recovery_factor=None,
        average_hold_seconds=0.0,
        best_session="n/a",
        worst_session="n/a",
        longest_win_streak=0,
        longest_loss_streak=0,
        mae_avg=Decimal("0"),
        mfe_avg=Decimal("0"),
        trade_count=body.trade_count,
        win_count=0,
        loss_count=0,
        total_return_pct=Decimal("0"),
    )
    # Build minimal WF/MC stubs
    from app.domain.institutional_trading.research.monte_carlo import MonteCarloReport
    from app.domain.institutional_trading.research.walk_forward import WalkForwardReport

    wf = WalkForwardReport(
        mode=WalkForwardMode.ROLLING,
        folds=(),
        passed=body.walk_forward_passed,
        pass_ratio=Decimal("1") if body.walk_forward_passed else Decimal("0"),
    )
    mc = MonteCarloReport(
        iterations=100,
        seed=0,
        median_final_equity=Decimal("10000"),
        p05_final_equity=Decimal("10000"),
        p95_final_equity=Decimal("10000"),
        median_profit_factor=Decimal("1.5"),
        median_max_dd=Decimal("5"),
        passed=body.monte_carlo_passed,
        distribution_final_equity=(),
    )
    report = _platform.promotion.evaluate(analytics, walk_forward=wf, monte_carlo=mc)
    return report.to_dict()
