"""Execution safety domain models — gate only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.execution import ExecutionDecision


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Production policy constraints applied before any execution decision."""

    max_spread: Decimal = Decimal("2.00")  # absolute price units (XAU-aware default)
    max_slippage: int = 20  # points
    trading_hours_start: time = time(0, 0)
    trading_hours_end: time = time(23, 59, 59)
    symbol_whitelist: frozenset[str] = frozenset(
        {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"}
    )
    account_whitelist: frozenset[int] = frozenset()  # empty = all accounts allowed
    max_leverage: Decimal = Decimal("500")
    max_lot: Decimal = Decimal("10")
    min_lot: Decimal = Decimal("0.01")
    duplicate_window_seconds: int = 5
    rapid_submit_limit: int = 3  # max identical fingerprints in window → RETRY/REJECT

    def __post_init__(self) -> None:
        require(self.max_spread >= 0, "max_spread must be >= 0")
        require(self.max_slippage >= 0, "max_slippage must be >= 0")
        require(self.max_lot >= self.min_lot, "max_lot must be >= min_lot")
        require(self.min_lot > 0, "min_lot must be > 0")
        require(self.max_leverage > 0, "max_leverage must be > 0")
        require(
            self.duplicate_window_seconds > 0,
            "duplicate_window_seconds must be > 0",
        )
        require(self.rapid_submit_limit > 0, "rapid_submit_limit must be > 0")
        object.__setattr__(
            self,
            "symbol_whitelist",
            frozenset(s.strip().upper() for s in self.symbol_whitelist if s.strip()),
        )

    def allows_symbol(self, symbol: str) -> bool:
        if not self.symbol_whitelist:
            return True
        return symbol.strip().upper() in self.symbol_whitelist

    def allows_account(self, login: int) -> bool:
        if not self.account_whitelist:
            return True
        return login in self.account_whitelist

    def within_trading_hours(self, now: datetime | None = None) -> bool:
        current = (now or datetime.now(UTC)).astimezone(UTC).time()
        start = self.trading_hours_start
        end = self.trading_hours_end
        if start <= end:
            return start <= current <= end
        # overnight window
        return current >= start or current <= end

    def to_dict(self) -> dict[str, object]:
        return {
            "max_spread": str(self.max_spread),
            "max_slippage": self.max_slippage,
            "trading_hours_start": self.trading_hours_start.isoformat(),
            "trading_hours_end": self.trading_hours_end.isoformat(),
            "symbol_whitelist": sorted(self.symbol_whitelist),
            "account_whitelist": sorted(self.account_whitelist),
            "max_leverage": str(self.max_leverage),
            "max_lot": str(self.max_lot),
            "min_lot": str(self.min_lot),
            "duplicate_window_seconds": self.duplicate_window_seconds,
            "rapid_submit_limit": self.rapid_submit_limit,
        }


@dataclass(frozen=True, slots=True)
class CalculatedRisk:
    """Risk metrics computed during the safety check (no live order)."""

    expected_margin: Decimal = Decimal("0")
    free_margin: Decimal = Decimal("0")
    margin_usage_pct: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    leverage: Decimal = Decimal("0")
    stop_distance_points: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "expected_margin": str(self.expected_margin),
            "free_margin": str(self.free_margin),
            "margin_usage_pct": str(self.margin_usage_pct),
            "spread": str(self.spread),
            "leverage": str(self.leverage),
            "stop_distance_points": str(self.stop_distance_points),
            "volume": str(self.volume),
        }


@dataclass(frozen=True, slots=True)
class RiskPreCheckResult:
    """Outcome of pre-trade risk checks (informational — no execution)."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }


@dataclass(eq=False, kw_only=True)
class ExecutionDecisionRecord(Entity):
    """Persisted execution safety decision — history only, never a live order."""

    user_id: UUID
    request_id: str
    decision: ExecutionDecision
    symbol: str
    side: str
    order_type: str
    volume: Decimal
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    calculated_risk: dict[str, object] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    request_fingerprint: str = ""
    request_snapshot: dict[str, object] = field(default_factory=dict)
    idempotent_replay: bool = False
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.request_id = self.request_id.strip()
        require(len(self.symbol) > 0, "symbol is required")
        require(len(self.request_id) > 0, "request_id is required")
        self.rejection_reasons = [
            r.strip()[:500] for r in self.rejection_reasons if r.strip()
        ][:50]
        self.warnings = [w.strip()[:500] for w in self.warnings if w.strip()][:50]

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        decision: ExecutionDecision,
        symbol: str,
        side: str,
        order_type: str,
        volume: Decimal,
        rejection_reasons: list[str] | None = None,
        warnings: list[str] | None = None,
        calculated_risk: dict[str, object] | None = None,
        checks: dict[str, bool] | None = None,
        request_fingerprint: str = "",
        request_snapshot: dict[str, object] | None = None,
        idempotent_replay: bool = False,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "decision": decision,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "volume": volume,
            "rejection_reasons": list(rejection_reasons or []),
            "warnings": list(warnings or []),
            "calculated_risk": dict(calculated_risk or {}),
            "checks": dict(checks or {}),
            "request_fingerprint": request_fingerprint,
            "request_snapshot": dict(request_snapshot or {}),
            "idempotent_replay": idempotent_replay,
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
                "decision": self.decision.value,
                "symbol": self.symbol,
                "side": self.side,
                "order_type": self.order_type,
                "volume": str(self.volume),
                "rejection_reasons": list(self.rejection_reasons),
                "warnings": list(self.warnings),
                "calculated_risk": dict(self.calculated_risk),
                "checks": dict(self.checks),
                "request_fingerprint": self.request_fingerprint,
                "request_snapshot": dict(self.request_snapshot),
                "idempotent_replay": self.idempotent_replay,
                "decided_at": self.decided_at.isoformat(),
            }
        )
        return base
