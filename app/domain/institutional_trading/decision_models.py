"""Phase B decision contracts — confluence, eligibility, trade decision.

Deterministic. Never sends orders. Never calls OMS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class TradeDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class DecisionAction(StrEnum):
    NO_TRADE = "NO_TRADE"
    WATCH = "WATCH"
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class PriceZone:
    low: Decimal
    high: Decimal
    mid: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "low": str(self.low),
            "high": str(self.high),
            "mid": str(self.mid) if self.mid is not None else None,
        }


@dataclass(frozen=True, slots=True)
class ConfluenceResult:
    """Canonical confluence judgment — final score before risk/eligibility."""

    confidence: int  # 0–100
    direction: TradeDirection
    reasons: tuple[str, ...]
    rejected_rules: tuple[str, ...]
    input_hash: str
    band: str = "reject"  # reject | tradable | high_confidence
    passed: bool = False  # confidence >= min_confluence
    factors: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "direction": self.direction.value,
            "reasons": list(self.reasons),
            "rejected_rules": list(self.rejected_rules),
            "input_hash": self.input_hash,
            "band": self.band,
            "passed": self.passed,
            "factors": dict(self.factors),
        }


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Pre-OMS gate — if not eligible, decision must be NO_TRADE."""

    eligible: bool
    checks: dict[str, bool]
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "checks": dict(self.checks),
            "rejection_reasons": list(self.rejection_reasons),
        }


@dataclass(frozen=True, slots=True)
class TradeDecision:
    """Institutional trade decision — never an order."""

    action: DecisionAction
    direction: TradeDirection
    confidence: int
    quality: int
    risk_score: int
    reasons: tuple[str, ...]
    invalidations: tuple[str, ...]
    entry_zone: PriceZone | None
    stop_zone: PriceZone | None
    target_zone: PriceZone | None
    estimated_rr: Decimal | None
    expected_duration: str
    confluence: ConfluenceResult
    eligibility: EligibilityResult
    input_hash: str
    config_version: str
    symbol: str
    as_of: datetime
    id: UUID = field(default_factory=uuid4)
    schema_version: str = "1.0.0"
    approved_lots: Decimal | None = None
    risk_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "action": self.action.value,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "quality": self.quality,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "invalidations": list(self.invalidations),
            "entry_zone": self.entry_zone.to_dict() if self.entry_zone else None,
            "stop_zone": self.stop_zone.to_dict() if self.stop_zone else None,
            "target_zone": self.target_zone.to_dict() if self.target_zone else None,
            "estimated_rr": str(self.estimated_rr) if self.estimated_rr else None,
            "expected_duration": self.expected_duration,
            "confluence": self.confluence.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "input_hash": self.input_hash,
            "config_version": self.config_version,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "approved_lots": str(self.approved_lots) if self.approved_lots else None,
            "risk_reasons": list(self.risk_reasons),
        }


@dataclass(frozen=True, slots=True)
class AccountRiskState:
    """External account / book facts for risk + eligibility (caller-supplied)."""

    equity: Decimal
    peak_equity: Decimal | None = None
    daily_pnl: Decimal = Decimal("0")
    weekly_pnl: Decimal = Decimal("0")
    open_positions: int = 0
    already_in_trade: bool = False
    consecutive_losses: int = 0
    cooldown_active: bool = False
    cooldown_remaining_minutes: int = 0
    market_open: bool = True
    atr: Decimal | None = None
    mid_price: Decimal | None = None
    free_margin: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity": str(self.equity),
            "peak_equity": str(self.peak_equity) if self.peak_equity else None,
            "daily_pnl": str(self.daily_pnl),
            "weekly_pnl": str(self.weekly_pnl),
            "open_positions": self.open_positions,
            "already_in_trade": self.already_in_trade,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_active": self.cooldown_active,
            "cooldown_remaining_minutes": self.cooldown_remaining_minutes,
            "market_open": self.market_open,
            "atr": str(self.atr) if self.atr is not None else None,
            "mid_price": str(self.mid_price) if self.mid_price is not None else None,
            "free_margin": str(self.free_margin) if self.free_margin else None,
        }
