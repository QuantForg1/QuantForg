"""Automatic incident detection for production reliability."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
    ProductionHardeningConfig,
)
from app.domain.institutional_trading.reliability.models import IncidentSeverity
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProductionIncidentDetector:
    config: ProductionHardeningConfig = field(default_factory=lambda: DEFAULT_HARDENING_CONFIG)
    _recent_rejects: deque[datetime] = field(default_factory=deque, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _last_titles: set[str] = field(default_factory=set, repr=False)

    def _raise(
        self,
        *,
        title: str,
        detail: str,
        severity: IncidentSeverity = IncidentSeverity.WARNING,
        source: str = "production_hardening",
    ) -> dict[str, Any] | None:
        minute_key = f"{datetime.now(UTC).strftime('%Y%m%d%H%M')}:{severity.value}:{title}"
        with self._lock:
            if minute_key in self._last_titles:
                return None
            self._last_titles.add(minute_key)
            if len(self._last_titles) > 200:
                self._last_titles = set(list(self._last_titles)[-80:])
        logger.warning(
            "production_incident",
            title=title,
            detail=detail,
            severity=severity.value,
            source=source,
        )
        try:
            from app.domain.institutional_trading.reliability.platform import (
                get_reliability_platform,
            )

            inc = get_reliability_platform().incidents.open(
                severity=severity,
                title=title,
                detail=detail,
                source=source,
            )
            return inc.to_dict() if hasattr(inc, "to_dict") else {"title": title}
        except Exception:
            logger.exception("production_incident_raise_failed")
            return {"title": title, "detail": detail, "severity": severity.value}

    def on_broker_reject(self, *, message: str, retcode: int | None = None) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._recent_rejects.append(now)
            while (
                self._recent_rejects
                and (now - self._recent_rejects[0]).total_seconds() > 120
            ):
                self._recent_rejects.popleft()
            burst = len(self._recent_rejects)
        if burst >= self.config.reject_burst_threshold:
            self._raise(
                title="Repeated broker rejects",
                detail=f"{burst} rejects in 120s — last retcode={retcode} msg={message[:200]}",
                severity=IncidentSeverity.ERROR,
            )

    def on_mt5_disconnect(self, *, detail: str = "MT5 disconnected") -> None:
        self._raise(
            title="MT5 disconnect",
            detail=detail,
            severity=IncidentSeverity.CRITICAL,
        )

    def on_gateway_reconnect_loop(self, *, attempts: int, detail: str = "") -> None:
        if attempts >= 5:
            self._raise(
                title="Gateway reconnect loop",
                detail=f"attempts={attempts} {detail}",
                severity=IncidentSeverity.ERROR,
            )

    def on_high_latency(self, *, latency_ms: float) -> None:
        if latency_ms >= self.config.high_latency_ms:
            self._raise(
                title="High execution latency",
                detail=f"latency_ms={latency_ms}",
                severity=IncidentSeverity.WARNING,
            )

    def on_high_slippage(self, *, slippage: float) -> None:
        if abs(slippage) >= self.config.high_slippage:
            self._raise(
                title="High slippage",
                detail=f"slippage={slippage}",
                severity=IncidentSeverity.WARNING,
            )

    def on_database_failure(self, *, detail: str) -> None:
        self._raise(
            title="Database failure",
            detail=detail,
            severity=IncidentSeverity.CRITICAL,
        )

    def on_position_sync_failure(self, *, detail: str) -> None:
        self._raise(
            title="Position sync failure",
            detail=detail,
            severity=IncidentSeverity.ERROR,
        )


_DET: ProductionIncidentDetector | None = None
_LOCK = Lock()


def get_incident_detector() -> ProductionIncidentDetector:
    global _DET
    with _LOCK:
        if _DET is None:
            _DET = ProductionIncidentDetector()
        return _DET
