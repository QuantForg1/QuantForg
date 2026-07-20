"""Application DTOs for the Risk Management Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.risk_engine import RiskAssessment


@dataclass(frozen=True, slots=True)
class RiskCheckCommand:
    user_id: UUID
    request_id: str
    symbol: str
    side: str
    requested_lots: str | None = None
    stop_loss_distance: str | None = None
    atr: str | None = None
    spread: str | None = None
    sizing_method: str = "percentage_risk"
    entry_price: str = "1.0"
    peak_equity: str | None = None
    daily_pnl: str = "0"
    weekly_pnl: str = "0"
    monthly_pnl: str = "0"
    # Optional account overrides when MT5 not connected (tests)
    equity: str | None = None
    balance: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class RiskCheckDTO:
    id: UUID
    request_id: str
    symbol: str
    side: str
    decision: str
    risk_score: int
    risk_band: str
    approved_lots: str
    requested_lots: str
    sizing_method: str
    warnings: list[str]
    reasons: list[str]
    exposure: dict[str, object]
    drawdown: dict[str, object]
    checks: dict[str, bool]
    rules: list[dict[str, object]]
    assessed_at: datetime

    @classmethod
    def from_entity(cls, entity: RiskAssessment) -> RiskCheckDTO:
        rules = list(entity.rules)
        if not rules:
            snap = entity.request_snapshot or {}
            raw = snap.get("rules")
            if isinstance(raw, list):
                rules = [dict(r) for r in raw if isinstance(r, dict)]
        return cls(
            id=entity.id,
            request_id=entity.request_id,
            symbol=entity.symbol,
            side=entity.side,
            decision=entity.decision.value,
            risk_score=entity.risk_score,
            risk_band=entity.risk_band.value,
            approved_lots=str(entity.approved_lots),
            requested_lots=str(entity.requested_lots),
            sizing_method=entity.sizing_method,
            warnings=list(entity.warnings),
            reasons=list(entity.reasons),
            exposure=dict(entity.exposure),
            drawdown=dict(entity.drawdown),
            checks=dict(entity.checks),
            rules=rules,
            assessed_at=entity.assessed_at,
        )
