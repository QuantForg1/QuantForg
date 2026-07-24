"""Validation alerts — observational; never auto-stops trading."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.ai_validation.config import (
    DEFAULT_AI_VALIDATION_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationAlert:
    id: str
    at: str
    kind: str
    severity: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "severity": self.severity,
            "detail": self.detail,
            "auto_halt": False,
        }


@dataclass
class ValidationAlerter:
    _alerts: list[ValidationAlert] = field(default_factory=list)
    _consecutive_losses: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _emit(self, *, kind: str, detail: str, severity: str = "WARNING") -> ValidationAlert:
        alert = ValidationAlert(
            id=str(uuid4()),
            at=datetime.now(UTC).isoformat(),
            kind=kind,
            severity=severity,
            detail=detail[:500],
        )
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > DEFAULT_AI_VALIDATION_CONFIG.max_alerts:
                self._alerts = self._alerts[-DEFAULT_AI_VALIDATION_CONFIG.max_alerts :]
        logger.warning(
            "ai_validation_alert",
            kind=kind,
            severity=severity,
            detail=detail,
            auto_halt=False,
        )
        return alert

    def on_win_rate(self, win_rate: float | None) -> None:
        cfg = DEFAULT_AI_VALIDATION_CONFIG
        if win_rate is not None and win_rate < cfg.alert_win_rate_floor:
            self._emit(
                kind="win_rate_drop",
                detail=f"Win rate {win_rate}% below floor {cfg.alert_win_rate_floor}%",
            )

    def on_drawdown(self, drawdown_pct: float | None) -> None:
        cfg = DEFAULT_AI_VALIDATION_CONFIG
        if drawdown_pct is not None and drawdown_pct >= cfg.alert_drawdown_pct:
            self._emit(
                kind="drawdown",
                detail=f"Drawdown {drawdown_pct}% exceeds {cfg.alert_drawdown_pct}%",
                severity="ERROR",
            )

    def on_slippage_spike(self, *, slippage: float, symbol: str) -> None:
        self._emit(
            kind="slippage_spike",
            detail=f"{symbol} entry slippage={slippage}",
        )

    def on_latency_spike(self, *, latency_ms: float) -> None:
        cfg = DEFAULT_AI_VALIDATION_CONFIG
        if latency_ms >= cfg.alert_latency_spike_ms:
            self._emit(
                kind="latency_spike",
                detail=f"Execution latency {latency_ms}ms >= {cfg.alert_latency_spike_ms}ms",
            )

    def on_trade_result(self, *, win: bool) -> None:
        cfg = DEFAULT_AI_VALIDATION_CONFIG
        with self._lock:
            if win:
                self._consecutive_losses = 0
                return
            self._consecutive_losses += 1
            n = self._consecutive_losses
        if n >= cfg.alert_consecutive_losses:
            self._emit(
                kind="consecutive_losses",
                detail=f"{n} consecutive losses (limit {cfg.alert_consecutive_losses})",
                severity="ERROR",
            )

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._alerts[-max(1, limit) :]
        return [a.to_dict() for a in reversed(rows)]


_ALERTER: ValidationAlerter | None = None
_LOCK = threading.Lock()


def get_validation_alerter() -> ValidationAlerter:
    global _ALERTER
    with _LOCK:
        if _ALERTER is None:
            _ALERTER = ValidationAlerter()
        return _ALERTER
