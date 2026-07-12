"""Liquidity Engine — equal highs/lows, pools, zones, sweeps.

Pure domain package. No trading, AI, MetaTrader, signals, SQL, or REST.
Distinct from market_context session ``LiquidityProfile``.

Import engines/services from their modules (e.g. ``liquidity.engine``) to
avoid circular imports with domain ports. Models and enums are re-exported
here for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.liquidity.enums import (
    LiquidityPoolStatus,
    LiquiditySide,
    LiquidityStateKind,
    SweepKind,
)
from app.domain.liquidity.models import (
    EqualHighs,
    EqualLows,
    LiquidityPool,
    LiquiditySnapshot,
    LiquidityState,
    LiquiditySweep,
    LiquidityZone,
)

if TYPE_CHECKING:
    from app.domain.liquidity.engine import LiquidityEngine, LiquidityResult
    from app.domain.liquidity.equal_high_detector import EqualHighDetector
    from app.domain.liquidity.equal_low_detector import EqualLowDetector
    from app.domain.liquidity.sweep_detector import (
        LiquiditySweepDetector,
        SweepDetectionResult,
    )
    from app.domain.liquidity.zone_builder import LiquidityZoneBuilder, ZoneBuildResult

__all__ = [
    "EqualHighDetector",
    "EqualHighs",
    "EqualLowDetector",
    "EqualLows",
    "LiquidityEngine",
    "LiquidityPool",
    "LiquidityPoolStatus",
    "LiquidityResult",
    "LiquiditySide",
    "LiquiditySnapshot",
    "LiquidityState",
    "LiquidityStateKind",
    "LiquiditySweep",
    "LiquiditySweepDetector",
    "LiquidityZone",
    "LiquidityZoneBuilder",
    "SweepDetectionResult",
    "SweepKind",
    "ZoneBuildResult",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "EqualHighDetector": (".equal_high_detector", "EqualHighDetector"),
    "EqualLowDetector": (".equal_low_detector", "EqualLowDetector"),
    "LiquidityEngine": (".engine", "LiquidityEngine"),
    "LiquidityResult": (".engine", "LiquidityResult"),
    "LiquiditySweepDetector": (".sweep_detector", "LiquiditySweepDetector"),
    "SweepDetectionResult": (".sweep_detector", "SweepDetectionResult"),
    "LiquidityZoneBuilder": (".zone_builder", "LiquidityZoneBuilder"),
    "ZoneBuildResult": (".zone_builder", "ZoneBuildResult"),
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
