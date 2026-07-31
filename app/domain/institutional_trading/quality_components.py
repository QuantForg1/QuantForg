"""Map TradeQualityScore factors → component dict for scalping overlays.

Production used ``getattr(quality, "components", {})`` but
``TradeQualityScore`` historically only exposed ``factors`` — so momentum/volume
always fell back to hard-coded defaults below the momentum gate.
"""

from __future__ import annotations

from typing import Any


def quality_components(quality: Any) -> dict[str, int]:
    """Return 0-100 component scores keyed by factor code + aliases.

    Never invokes a ``components`` property (that may call this helper).
    Prefers ``factors``; accepts a plain mapping attribute on test doubles.
    """
    if quality is None:
        return {}

    out: dict[str, int] = {}

    factors = getattr(quality, "factors", None) or ()
    for factor in factors:
        code = str(getattr(factor, "code", "") or "").strip()
        if not code:
            continue
        try:
            score = max(0, min(100, int(getattr(factor, "score", 0) or 0)))
        except (TypeError, ValueError):
            continue
        out[code] = score

    if not out:
        # Test doubles may set a plain mapping without a factors tuple.
        # Skip @property descriptors to avoid recursion with TradeQualityScore.
        cls_attr = getattr(type(quality), "components", None)
        raw: Any = None
        if not isinstance(cls_attr, property):
            raw = getattr(quality, "components", None)
        if isinstance(raw, dict) and raw:
            for key, value in raw.items():
                try:
                    out[str(key)] = max(0, min(100, int(value)))
                except (TypeError, ValueError):
                    continue

    # Aliases consumed by scoring / direction / PA confluence
    if "momentum" not in out:
        if "trend" in out:
            out["momentum"] = out["trend"]
        elif "trend_strength" in out:
            out["momentum"] = out["trend_strength"]
        elif "market_structure" in out:
            out["momentum"] = out["market_structure"]
    if "trend_strength" not in out and "trend" in out:
        out["trend_strength"] = out["trend"]
    if "volume" not in out and "liquidity" in out:
        out["volume"] = out["liquidity"]
    if "vol" not in out and "volume" in out:
        out["vol"] = out["volume"]
    return out
