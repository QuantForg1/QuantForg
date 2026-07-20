"""Risk Management Engine domain models — evaluate only, never execute."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.risk import (
    PositionSizingMethod,
    RiskDecision,
    RiskScoreBand,
)


@dataclass(frozen=True, slots=True)
class RiskEngineConfig:
    """Runtime limits for a risk check (defaults + optional profile overrides)."""

    max_lot: Decimal = Decimal("10")
    min_lot: Decimal = Decimal("0.01")
    lot_step: Decimal = Decimal("0.01")
    max_risk_per_trade_pct: Decimal = Decimal("1")  # % of equity
    max_daily_loss_pct: Decimal = Decimal("5")
    max_weekly_loss_pct: Decimal = Decimal("10")
    max_monthly_loss_pct: Decimal = Decimal("20")
    max_drawdown_pct: Decimal = Decimal("25")
    max_symbol_exposure_pct: Decimal = Decimal("30")
    max_asset_class_exposure_pct: Decimal = Decimal("50")
    max_total_exposure_pct: Decimal = Decimal("80")
    max_correlated_exposure_pct: Decimal = Decimal("40")
    max_open_positions: int = 5
    default_sizing: PositionSizingMethod = PositionSizingMethod.PERCENTAGE_RISK
    fixed_lot: Decimal = Decimal("0.10")
    fixed_dollar_risk: Decimal = Decimal("100")
    atr_multiplier: Decimal = Decimal("1.5")
    # FX default. Metals/crypto must use symbol-aware size via contract_size_for_symbol().
    contract_size: Decimal = Decimal("100000")
    exposure_leverage: Decimal = Decimal("100")  # fallback when account.leverage unset
    # --- Institutional extensions (Phase B) ---
    max_consecutive_losses: int = 3
    cooldown_minutes_after_loss_streak: int = 60
    max_spread: Decimal = Decimal("2.00")
    min_atr: Decimal = Decimal("0")  # 0 = disabled
    max_atr: Decimal = Decimal("0")  # 0 = disabled
    max_atr_pct_of_price: Decimal = Decimal("3.0")  # reject if ATR/price*100 > this
    enforce_session: bool = True
    enforce_spread: bool = True
    enforce_atr: bool = True

    def __post_init__(self) -> None:
        require(self.max_lot >= self.min_lot, "max_lot must be >= min_lot")
        require(self.min_lot > 0, "min_lot must be > 0")
        require(self.lot_step > 0, "lot_step must be > 0")
        require(self.exposure_leverage > 0, "exposure_leverage must be > 0")
        require(self.max_consecutive_losses >= 0, "max_consecutive_losses >= 0")
        require(self.max_open_positions >= 1, "max_open_positions >= 1")


def contract_size_for_symbol(symbol: str, *, default: Decimal = Decimal("100000")) -> Decimal:
    """Broker contract size by instrument class — never apply FX 100k to gold."""
    u = symbol.strip().upper()
    if u.startswith("XAU") or "GOLD" in u:
        return Decimal("100")
    if u.startswith("XAG") or "SILVER" in u:
        return Decimal("5000")
    if "BTC" in u or "ETH" in u:
        return Decimal("1")
    return default


@dataclass(frozen=True, slots=True)
class RiskRuleResult:
    """One evaluated risk rule for transparent PASS/FAIL UI."""

    id: str
    name: str
    status: str  # pass | fail | n/a
    current: str
    threshold: str
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "current": self.current,
            "threshold": self.threshold,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    """Computed position size before / after risk adjustments."""

    method: PositionSizingMethod
    requested_lots: Decimal
    approved_lots: Decimal
    capped: bool = False
    dollar_risk: Decimal = Decimal("0")
    stop_distance: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method.value,
            "requested_lots": str(self.requested_lots),
            "approved_lots": str(self.approved_lots),
            "capped": self.capped,
            "dollar_risk": str(self.dollar_risk),
            "stop_distance": str(self.stop_distance),
        }


@dataclass(frozen=True, slots=True)
class ExposureBreakdown:
    """Account exposure snapshot used by the exposure engine."""

    by_symbol: dict[str, Decimal] = field(default_factory=dict)
    by_asset_class: dict[str, Decimal] = field(default_factory=dict)
    total: Decimal = Decimal("0")
    long_exposure: Decimal = Decimal("0")
    short_exposure: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "by_symbol": {k: str(v) for k, v in self.by_symbol.items()},
            "by_asset_class": {k: str(v) for k, v in self.by_asset_class.items()},
            "total": str(self.total),
            "long_exposure": str(self.long_exposure),
            "short_exposure": str(self.short_exposure),
        }


@dataclass(frozen=True, slots=True)
class DrawdownState:
    """Drawdown / loss-limit state relative to peak and period P&L."""

    equity: Decimal
    peak_equity: Decimal
    current_drawdown_pct: Decimal
    daily_loss_pct: Decimal
    weekly_loss_pct: Decimal
    monthly_loss_pct: Decimal
    equity_protected: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "equity": str(self.equity),
            "peak_equity": str(self.peak_equity),
            "current_drawdown_pct": str(self.current_drawdown_pct),
            "daily_loss_pct": str(self.daily_loss_pct),
            "weekly_loss_pct": str(self.weekly_loss_pct),
            "monthly_loss_pct": str(self.monthly_loss_pct),
            "equity_protected": self.equity_protected,
        }


@dataclass(eq=False, kw_only=True)
class RiskAssessment(Entity):
    """Persisted risk-engine outcome — history only, never an order."""

    user_id: UUID
    request_id: str
    symbol: str
    side: str
    decision: RiskDecision
    risk_score: int
    risk_band: RiskScoreBand
    approved_lots: Decimal
    requested_lots: Decimal
    sizing_method: str
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    exposure: dict[str, object] = field(default_factory=dict)
    drawdown: dict[str, object] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    rules: list[dict[str, object]] = field(default_factory=list)
    request_snapshot: dict[str, object] = field(default_factory=dict)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        require(len(self.symbol) > 0, "symbol is required")
        require(0 <= self.risk_score <= 100, "risk_score must be 0-100")
        self.warnings = [w.strip()[:500] for w in self.warnings if w.strip()][:50]
        self.reasons = [r.strip()[:500] for r in self.reasons if r.strip()][:50]
        self.rules = [dict(r) for r in self.rules][:40]

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        decision: RiskDecision,
        risk_score: int,
        risk_band: RiskScoreBand,
        approved_lots: Decimal,
        requested_lots: Decimal,
        sizing_method: str,
        warnings: list[str] | None = None,
        reasons: list[str] | None = None,
        exposure: dict[str, object] | None = None,
        drawdown: dict[str, object] | None = None,
        checks: dict[str, bool] | None = None,
        rules: list[dict[str, object]] | None = None,
        request_snapshot: dict[str, object] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "symbol": symbol,
            "side": side,
            "decision": decision,
            "risk_score": risk_score,
            "risk_band": risk_band,
            "approved_lots": approved_lots,
            "requested_lots": requested_lots,
            "sizing_method": sizing_method,
            "warnings": list(warnings or []),
            "reasons": list(reasons or []),
            "exposure": dict(exposure or {}),
            "drawdown": dict(drawdown or {}),
            "checks": dict(checks or {}),
            "rules": list(rules or []),
            "request_snapshot": dict(request_snapshot or {}),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "side": self.side,
                "decision": self.decision.value,
                "risk_score": self.risk_score,
                "risk_band": self.risk_band.value,
                "approved_lots": str(self.approved_lots),
                "requested_lots": str(self.requested_lots),
                "sizing_method": self.sizing_method,
                "warnings": list(self.warnings),
                "reasons": list(self.reasons),
                "exposure": dict(self.exposure),
                "drawdown": dict(self.drawdown),
                "checks": dict(self.checks),
                "rules": list(self.rules),
                "request_snapshot": dict(self.request_snapshot),
                "assessed_at": self.assessed_at.isoformat(),
            }
        )
        return base
