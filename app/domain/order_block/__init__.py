"""Order Block Engine — detect, validate, mitigate, break, quality.

Pure domain package. No trading, AI, MetaTrader, signals, SQL, or REST.

Import engines/services from their modules to avoid circular imports with
domain ports. Models and enums are re-exported here for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.order_block.enums import (
    MitigationKind,
    OrderBlockOrigin,
    OrderBlockSide,
    OrderBlockState,
    QualityGrade,
)
from app.domain.order_block.models import (
    ORDER_BLOCK_TRANSITIONS,
    BreakerBlock,
    MitigationBlock,
    OrderBlock,
    OrderBlockQuality,
    OrderBlockSnapshot,
    OrderBlockZone,
)

if TYPE_CHECKING:
    from app.domain.order_block.breaker_detector import (
        BreakerDetectionResult,
        BreakerDetector,
    )
    from app.domain.order_block.detector import OrderBlockDetector
    from app.domain.order_block.engine import OrderBlockEngine, OrderBlockResult
    from app.domain.order_block.mitigation_detector import (
        MitigationDetectionResult,
        MitigationDetector,
    )
    from app.domain.order_block.strength_evaluator import OrderBlockStrengthEvaluator
    from app.domain.order_block.validator import OrderBlockValidator, ValidationResult

__all__ = [
    "ORDER_BLOCK_TRANSITIONS",
    "BreakerBlock",
    "BreakerDetectionResult",
    "BreakerDetector",
    "MitigationBlock",
    "MitigationDetectionResult",
    "MitigationDetector",
    "MitigationKind",
    "OrderBlock",
    "OrderBlockDetector",
    "OrderBlockEngine",
    "OrderBlockOrigin",
    "OrderBlockQuality",
    "OrderBlockResult",
    "OrderBlockSide",
    "OrderBlockSnapshot",
    "OrderBlockState",
    "OrderBlockStrengthEvaluator",
    "OrderBlockValidator",
    "OrderBlockZone",
    "QualityGrade",
    "ValidationResult",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "BreakerDetectionResult": (".breaker_detector", "BreakerDetectionResult"),
    "BreakerDetector": (".breaker_detector", "BreakerDetector"),
    "MitigationDetectionResult": (".mitigation_detector", "MitigationDetectionResult"),
    "MitigationDetector": (".mitigation_detector", "MitigationDetector"),
    "OrderBlockDetector": (".detector", "OrderBlockDetector"),
    "OrderBlockEngine": (".engine", "OrderBlockEngine"),
    "OrderBlockResult": (".engine", "OrderBlockResult"),
    "OrderBlockStrengthEvaluator": (
        ".strength_evaluator",
        "OrderBlockStrengthEvaluator",
    ),
    "OrderBlockValidator": (".validator", "OrderBlockValidator"),
    "ValidationResult": (".validator", "ValidationResult"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_ATTRS:
        module_name, attr = _LAZY_ATTRS[name]
        from importlib import import_module

        module = import_module(module_name, __name__)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
