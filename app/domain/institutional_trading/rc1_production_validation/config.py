"""RC1 Production Validation Mode — feature flags and floors (locked).

Does not modify strategy, Quality/Confidence floors, weights, or risk logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from typing import Any


class ValidationExecutionMode(StrEnum):
    """Broker execution under PRODUCTION_VALIDATION_MODE."""

    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


# Locked institutional floors — never lowered by this package.
QUALITY_FLOOR = 80
CONFIDENCE_FLOOR = 80


@dataclass(frozen=True, slots=True)
class ValidationRuntimeConfig:
    enabled: bool = False
    execution_mode: ValidationExecutionMode = ValidationExecutionMode.PAPER
    quality_floor: int = QUALITY_FLOOR
    confidence_floor: int = CONFIDENCE_FLOOR

    @property
    def blocks_broker_submit(self) -> bool:
        """True when MT5 order_send must not run."""
        return self.enabled and self.execution_mode in {
            ValidationExecutionMode.PAPER,
            ValidationExecutionMode.SHADOW,
        }

    @property
    def simulates_fills(self) -> bool:
        return self.enabled and self.execution_mode is ValidationExecutionMode.PAPER

    @property
    def records_shadow_only(self) -> bool:
        return self.enabled and self.execution_mode is ValidationExecutionMode.SHADOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "PRODUCTION_VALIDATION_MODE": self.enabled,
            "VALIDATION_EXECUTION_MODE": self.execution_mode.value,
            "quality_floor": self.quality_floor,
            "confidence_floor": self.confidence_floor,
            "blocks_broker_submit": self.blocks_broker_submit,
            "simulates_fills": self.simulates_fills,
            "never_modifies_strategy": True,
            "never_lowers_thresholds": True,
            "never_changes_weights": True,
            "never_changes_risk_logic": True,
        }


_OVERRIDE: ValidationRuntimeConfig | None = None
_LOCK = Lock()


def parse_execution_mode(raw: str | None) -> ValidationExecutionMode:
    text = (raw or "paper").strip().lower()
    if text in {"paper", "shadow", "live"}:
        return ValidationExecutionMode(text)
    return ValidationExecutionMode.PAPER


def resolve_validation_runtime(
    *,
    enabled: bool | None = None,
    execution_mode: str | None = None,
) -> ValidationRuntimeConfig:
    """Resolve runtime config from explicit args, test override, or Settings."""
    with _LOCK:
        if _OVERRIDE is not None and enabled is None and execution_mode is None:
            return _OVERRIDE

    if enabled is None or execution_mode is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
            if enabled is None:
                enabled = bool(getattr(settings, "production_validation_mode", False))
            if execution_mode is None:
                execution_mode = str(
                    getattr(settings, "validation_execution_mode", "paper") or "paper"
                )
        except Exception:
            enabled = bool(enabled) if enabled is not None else False
            execution_mode = execution_mode or "paper"

    return ValidationRuntimeConfig(
        enabled=bool(enabled),
        execution_mode=parse_execution_mode(execution_mode),
        quality_floor=QUALITY_FLOOR,
        confidence_floor=CONFIDENCE_FLOOR,
    )


def set_validation_runtime_for_tests(
    *,
    enabled: bool = True,
    execution_mode: str = "paper",
) -> ValidationRuntimeConfig:
    global _OVERRIDE
    cfg = ValidationRuntimeConfig(
        enabled=enabled,
        execution_mode=parse_execution_mode(execution_mode),
    )
    with _LOCK:
        _OVERRIDE = cfg
    return cfg


def clear_validation_runtime_override_for_tests() -> None:
    global _OVERRIDE
    with _LOCK:
        _OVERRIDE = None
