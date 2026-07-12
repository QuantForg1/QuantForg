"""Fair Value Gap Engine — detect, fill, invalidate, quality.

Pure domain package. No trading, AI, MetaTrader, signals, SQL, or REST.

Import engines/services from their modules to avoid circular imports with
domain ports. Models and enums are re-exported here for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.fair_value_gap.enums import (
    FairValueGapSide,
    FairValueGapState,
    FillKind,
    QualityGrade,
)
from app.domain.fair_value_gap.models import (
    GAP_TRANSITIONS,
    FairValueGap,
    FairValueGapSnapshot,
    FairValueGapZone,
    GapFill,
    GapLifecycle,
    GapQuality,
)

if TYPE_CHECKING:
    from app.domain.fair_value_gap.detector import FairValueGapDetector
    from app.domain.fair_value_gap.engine import FairValueGapEngine, FairValueGapResult
    from app.domain.fair_value_gap.fill_detector import GapFillDetector, GapFillResult
    from app.domain.fair_value_gap.invalidation_detector import (
        GapInvalidationDetector,
        GapInvalidationResult,
        InvalidationEvent,
    )
    from app.domain.fair_value_gap.quality_evaluator import GapQualityEvaluator

__all__ = [
    "GAP_TRANSITIONS",
    "FairValueGap",
    "FairValueGapDetector",
    "FairValueGapEngine",
    "FairValueGapResult",
    "FairValueGapSide",
    "FairValueGapSnapshot",
    "FairValueGapState",
    "FairValueGapZone",
    "FillKind",
    "GapFill",
    "GapFillDetector",
    "GapFillResult",
    "GapInvalidationDetector",
    "GapInvalidationResult",
    "GapLifecycle",
    "GapQuality",
    "GapQualityEvaluator",
    "InvalidationEvent",
    "QualityGrade",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "FairValueGapDetector": (".detector", "FairValueGapDetector"),
    "FairValueGapEngine": (".engine", "FairValueGapEngine"),
    "FairValueGapResult": (".engine", "FairValueGapResult"),
    "GapFillDetector": (".fill_detector", "GapFillDetector"),
    "GapFillResult": (".fill_detector", "GapFillResult"),
    "GapInvalidationDetector": (".invalidation_detector", "GapInvalidationDetector"),
    "GapInvalidationResult": (".invalidation_detector", "GapInvalidationResult"),
    "InvalidationEvent": (".invalidation_detector", "InvalidationEvent"),
    "GapQualityEvaluator": (".quality_evaluator", "GapQualityEvaluator"),
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
