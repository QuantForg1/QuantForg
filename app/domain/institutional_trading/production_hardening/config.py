"""Production hardening config — all knobs configurable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProductionHardeningConfig:
    version: str = "production-hardening-v6.0.0"

    # Retry — transient MT5 only
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_base_backoff_ms: int = 150
    retry_max_backoff_ms: int = 2_000
    retry_jitter_ratio: float = 0.15
    # MetaTrader transient retcodes
    retryable_retcodes: tuple[int, ...] = (
        10004,  # REQUOTE
        10012,  # TIMEOUT
        10020,  # PRICE_CHANGED
        10021,  # PRICE_OFF
        10024,  # ORDER_LOCKED (transient lock)
        10031,  # CONNECTION / trade server
    )
    # Permanent — never retry
    permanent_retcodes: tuple[int, ...] = (
        10014,  # INVALID_VOLUME
        10015,  # INVALID_PRICE
        10016,  # INVALID_STOPS
        10017,  # TRADE_DISABLED
        10018,  # MARKET_CLOSED
        10019,  # NO_MONEY
        90001,  # QuantForg synthetic blocked
    )
    retryable_message_tokens: tuple[str, ...] = (
        "requote",
        "trade context is busy",
        "timeout",
        "timed out",
        "gateway delay",
        "network",
        "connection",
        "no connection",
    )

    # Lifecycle / explainability
    lifecycle_max_events: int = 5_000
    explainability_max_records: int = 5_000

    # Incidents
    reject_burst_window: int = 10
    reject_burst_threshold: int = 5
    high_latency_ms: float = 2_000.0
    high_slippage: float = 1.5

    # Learning
    learning_enabled: bool = True
    learning_weight_step: float = 0.02  # gradual
    learning_weight_min: float = 0.5
    learning_weight_max: float = 1.5

    # Position recovery
    recovery_on_startup: bool = True
    pme_state_filename: str = "pme_recovery_state.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "retry_enabled": self.retry_enabled,
            "retry_max_attempts": self.retry_max_attempts,
            "retry_base_backoff_ms": self.retry_base_backoff_ms,
            "retry_max_backoff_ms": self.retry_max_backoff_ms,
            "retryable_retcodes": list(self.retryable_retcodes),
            "permanent_retcodes": list(self.permanent_retcodes),
            "learning_enabled": self.learning_enabled,
            "learning_weight_step": self.learning_weight_step,
            "recovery_on_startup": self.recovery_on_startup,
            "high_latency_ms": self.high_latency_ms,
            "high_slippage": self.high_slippage,
        }


DEFAULT_HARDENING_CONFIG = ProductionHardeningConfig()
