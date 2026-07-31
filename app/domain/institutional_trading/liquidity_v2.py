"""AI Decision Engine v2 — institutional liquidity context.

Expands what counts as valid liquidity *context* without inflating scores.

Valid context (any one is enough to clear ``no_liquidity_context``):
  - validated / active Order Block
  - respected (active) Fair Value Gap / imbalance
  - mitigation record
  - displacement-qualified OB (displacement_ratio ≥ 1.5)
  - liquidity sweep
  - EQH / EQL
  - liquidity pools
  - premium / discount reaction (only when explicitly present on snapshot)

Score policy (no inflation vs prior ceilings):
  - sweeps present → 85 (unchanged)
  - other validated context without sweeps → 65 (same as prior pools-only)
  - no context → 20 + ``no_liquidity_context``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.order_block.enums import OrderBlockState

# Match OrderBlockValidator.min_displacement_ratio
_MIN_DISPLACEMENT_RATIO = Decimal("1.5")


@dataclass(frozen=True, slots=True)
class LiquidityV2Assessment:
    score: int
    has_context: bool
    sources: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    rejected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "has_context": self.has_context,
            "sources": list(self.sources),
            "reasons": list(self.reasons),
            "rejected": self.rejected,
        }


def _ob_displacement_qualified(ob_snap: Any) -> bool:
    if ob_snap is None:
        return False
    for block in getattr(ob_snap, "order_blocks", ()) or ():
        quality = getattr(block, "quality", None)
        if quality is None:
            continue
        ratio = getattr(quality, "displacement_ratio", None)
        if ratio is None:
            continue
        try:
            if Decimal(str(ratio)) >= _MIN_DISPLACEMENT_RATIO:
                return True
        except Exception:
            continue
    return False


def _premium_discount_reaction(snapshot: Any) -> bool:
    """Only recognise explicit premium/discount artefacts — never fabricate."""
    # Optional advisory fields some snapshots may carry; absent → False.
    for key in ("premium_discount", "premium_discount_reaction", "pd_array"):
        val = getattr(snapshot, key, None)
        if val is None and isinstance(snapshot, dict):
            val = snapshot.get(key)
        if val in (None, False, "", (), [], {}):
            continue
        if isinstance(val, dict) and val.get("reaction"):
            return True
        if val is True:
            return True
        if isinstance(val, (list, tuple)) and len(val) > 0:
            return True
    return False


def evaluate_liquidity_v2(snapshot: Any) -> LiquidityV2Assessment:
    """Assess institutional liquidity context from a market analysis snapshot."""
    sources: list[str] = []
    reasons: list[str] = []

    liq = getattr(snapshot, "liquidity", None)
    sweeps = tuple(getattr(liq, "sweeps", ()) or ()) if liq else ()
    pools = tuple(getattr(liq, "pools", ()) or ()) if liq else ()
    eqh = tuple(getattr(liq, "equal_highs", ()) or ()) if liq else ()
    eql = tuple(getattr(liq, "equal_lows", ()) or ()) if liq else ()

    if sweeps:
        sources.append("liquidity_sweep")
        reasons.append(f"Liquidity sweeps={len(sweeps)}")
    if pools:
        sources.append("liquidity_pool")
        reasons.append(f"Liquidity pools={len(pools)}")
    if eqh:
        sources.append("eqh")
        reasons.append(f"EQH={len(eqh)}")
    if eql:
        sources.append("eql")
        reasons.append(f"EQL={len(eql)}")

    ob = getattr(snapshot, "order_blocks", None)
    active_ob = 0
    if ob:
        active_ob = sum(
            1
            for b in (getattr(ob, "order_blocks", ()) or ())
            if getattr(b, "state", None)
            in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
        )
    if active_ob:
        sources.append("validated_order_block")
        reasons.append(f"Validated/active order blocks={active_ob}")

    mitigations = tuple(getattr(ob, "mitigations", ()) or ()) if ob else ()
    if mitigations:
        sources.append("mitigation")
        reasons.append(f"Mitigations={len(mitigations)}")

    if _ob_displacement_qualified(ob):
        sources.append("displacement")
        reasons.append("Displacement-qualified order block present")

    fvg = getattr(snapshot, "fair_value_gaps", None)
    open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
    if open_fvg:
        sources.append("respected_fvg")
        sources.append("imbalance_reaction")
        reasons.append(f"Respected/active FVGs (imbalance)={open_fvg}")

    if _premium_discount_reaction(snapshot):
        sources.append("premium_discount_reaction")
        reasons.append("Premium/discount reaction present")

    # Deduplicate while preserving order
    sources = list(dict.fromkeys(sources))
    has_context = len(sources) > 0

    if not has_context:
        return LiquidityV2Assessment(
            score=20,
            has_context=False,
            sources=(),
            reasons=("No institutional liquidity context",),
            rejected=True,
        )

    # No score inflation: sweeps keep prior ceiling 85; other context = 65.
    score = 85 if "liquidity_sweep" in sources else 65
    return LiquidityV2Assessment(
        score=score,
        has_context=True,
        sources=tuple(sources),
        reasons=tuple(reasons),
        rejected=False,
    )


def evaluate_liquidity_v1_legacy(snapshot: Any) -> LiquidityV2Assessment:
    """Pre-v2 liquidity rule: sweeps/pools/EQH/EQL only."""
    liq = getattr(snapshot, "liquidity", None)
    if liq and (
        getattr(liq, "sweeps", None)
        or getattr(liq, "pools", None)
        or getattr(liq, "equal_highs", None)
        or getattr(liq, "equal_lows", None)
    ):
        sweep_n = len(getattr(liq, "sweeps", ()) or ())
        score = 85 if sweep_n else 65
        return LiquidityV2Assessment(
            score=score,
            has_context=True,
            sources=("legacy_liq",),
            reasons=(f"Legacy liquidity sweeps={sweep_n}",),
            rejected=False,
        )
    return LiquidityV2Assessment(
        score=20,
        has_context=False,
        sources=(),
        reasons=("No liquidity context (legacy)",),
        rejected=True,
    )
