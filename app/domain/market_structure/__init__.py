"""Market Structure Engine — swings, BOS/CHoCH, trend classification.

Pure domain package. No trading, AI, MetaTrader, indicators-as-signals,
SQL, or REST.

Import engines/services from their modules to avoid circular imports with
domain ports. Models and enums are re-exported here for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.market_structure.enums import (
    StructureBreakKind,
    StructureRole,
    SwingKind,
    TrendDirection,
)
from app.domain.market_structure.models import (
    BreakOfStructure,
    ChangeOfCharacter,
    StructureNode,
    StructureSnapshot,
    SwingPoint,
    TrendState,
)

if TYPE_CHECKING:
    from app.domain.market_structure.engine import (
        MarketStructureEngine,
        MarketStructureResult,
    )
    from app.domain.market_structure.structure_analyzer import (
        StructureAnalysisResult,
        StructureAnalyzer,
    )
    from app.domain.market_structure.swing_detector import SwingDetector
    from app.domain.market_structure.trend_classifier import TrendClassifier

__all__ = [
    "BreakOfStructure",
    "ChangeOfCharacter",
    "MarketStructureEngine",
    "MarketStructureResult",
    "StructureAnalysisResult",
    "StructureAnalyzer",
    "StructureBreakKind",
    "StructureNode",
    "StructureRole",
    "StructureSnapshot",
    "SwingDetector",
    "SwingKind",
    "SwingPoint",
    "TrendClassifier",
    "TrendDirection",
    "TrendState",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "MarketStructureEngine": (".engine", "MarketStructureEngine"),
    "MarketStructureResult": (".engine", "MarketStructureResult"),
    "StructureAnalysisResult": (".structure_analyzer", "StructureAnalysisResult"),
    "StructureAnalyzer": (".structure_analyzer", "StructureAnalyzer"),
    "SwingDetector": (".swing_detector", "SwingDetector"),
    "TrendClassifier": (".trend_classifier", "TrendClassifier"),
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
