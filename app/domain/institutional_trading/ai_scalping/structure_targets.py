"""Dynamic SL behind structure / TP toward liquidity & ATR — never fixed pips."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


@dataclass(frozen=True, slots=True)
class StructureTargets:
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    stop_distance: Decimal | None
    expected_rr: Decimal | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": str(self.entry) if self.entry is not None else None,
            "stop_loss": str(self.stop_loss) if self.stop_loss is not None else None,
            "take_profit": (
                str(self.take_profit) if self.take_profit is not None else None
            ),
            "stop_distance": (
                str(self.stop_distance) if self.stop_distance is not None else None
            ),
            "expected_rr": (
                str(self.expected_rr) if self.expected_rr is not None else None
            ),
            "reason": self.reason,
            "fixed_stop": False,
        }


def _dec(v: Any) -> Decimal | None:
    try:
        if v is None:
            return None
        d = Decimal(str(v))
        return d if d > 0 else None
    except Exception:
        return None


def compute_structure_targets(
    snapshot: MarketAnalysisSnapshot,
    *,
    direction: TradeDirection,
    entry: Decimal | None,
    atr: Decimal | None,
    config: AiScalpingConfig | None = None,
) -> StructureTargets:
    """Place SL behind structure; TP at liquidity / nearby structure / ATR expansion."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if direction not in {TradeDirection.BUY, TradeDirection.SELL} or entry is None:
        return StructureTargets(
            entry=entry,
            stop_loss=None,
            take_profit=None,
            stop_distance=None,
            expected_rr=None,
            reason="No direction/entry for structure targets",
        )

    atr_d = atr if atr and atr > 0 else None
    fallback_dist = (atr_d * cfg.stop_atr_mult) if atr_d else None
    # Structure SL must stay scalp-scale. Farthest-swing SL (e.g. 40–100 pts on
    # XAUUSD) blows micro hard_max (~5%) on $180 desks and deadlocks LIVE
    # order_send even when ATR stop (~1.1×ATR) would be tradable.
    max_structure_stop = (atr_d * Decimal("2.5")) if atr_d else None

    structure = snapshot.primary_structure
    candidate_lows: list[Decimal] = []
    candidate_highs: list[Decimal] = []
    if structure:
        seed_low = _dec(getattr(structure, "last_swing_low", None)) or _dec(
            getattr(structure, "swing_low", None)
        )
        seed_high = _dec(getattr(structure, "last_swing_high", None)) or _dec(
            getattr(structure, "swing_high", None)
        )
        if seed_low is not None:
            candidate_lows.append(seed_low)
        if seed_high is not None:
            candidate_highs.append(seed_high)
        # Collect swings — pick NEAREST protective level later (not min/max of all).
        swings = list(getattr(structure, "swings", ()) or ())
        for s in swings[-12:]:
            price = _dec(getattr(s, "price", None))
            kind = str(getattr(getattr(s, "kind", None), "value", s.kind) or "").upper()
            if price is None:
                continue
            if "LOW" in kind:
                candidate_lows.append(price)
            if "HIGH" in kind:
                candidate_highs.append(price)

    # Nearest swing low below entry / nearest swing high above entry.
    below_entry_lows = [p for p in candidate_lows if p < entry]
    above_entry_highs = [p for p in candidate_highs if p > entry]
    swing_low = max(below_entry_lows) if below_entry_lows else None
    swing_high = min(above_entry_highs) if above_entry_highs else None

    liq = snapshot.liquidity
    liq_high = None
    liq_low = None
    if liq:
        for pool in list(getattr(liq, "pools", ()) or ())[-6:]:
            price = _dec(getattr(pool, "price", None))
            side = str(
                getattr(getattr(pool, "side", None), "value", getattr(pool, "side", ""))
                or ""
            ).upper()
            if price is None:
                continue
            if "HIGH" in side or "ASK" in side:
                liq_high = price if liq_high is None else max(liq_high, price)
            if "LOW" in side or "BID" in side:
                liq_low = price if liq_low is None else min(liq_low, price)

    reason_parts: list[str] = []
    if direction is TradeDirection.BUY:
        # SL behind nearest structure low (not the farthest historical low).
        if swing_low is not None and swing_low < entry:
            sl = swing_low - (
                atr_d * Decimal("0.15") if atr_d else entry * Decimal("0.0001")
            )
            reason_parts.append("SL behind nearest swing low")
        elif fallback_dist:
            sl = entry - fallback_dist
            reason_parts.append("SL ATR fallback (no swing low)")
        else:
            return StructureTargets(
                entry,
                None,
                None,
                None,
                None,
                "Cannot place BUY SL without structure/ATR",
            )
        stop_distance = entry - sl
        if (
            max_structure_stop is not None
            and fallback_dist is not None
            and stop_distance > max_structure_stop
        ):
            sl = entry - fallback_dist
            stop_distance = fallback_dist
            reason_parts.append(
                f"SL capped to ATR×{cfg.stop_atr_mult} "
                f"(structure stop > {max_structure_stop})"
            )
        # TP priority: fixed-R (optional) → liquidity → swing → ATR expansion
        fixed_r = cfg.fixed_tp_r
        if fixed_r is not None and fixed_r > 0:
            tp = entry + stop_distance * fixed_r
            reason_parts.append(f"TP fixed {fixed_r}R")
        elif liq_high is not None and liq_high > entry:
            tp = liq_high
            reason_parts.append("TP liquidity high")
        elif swing_high is not None and swing_high > entry:
            tp = swing_high
            reason_parts.append("TP nearby swing high")
        elif atr_d:
            tp = entry + atr_d * cfg.atr_tp_mult
            reason_parts.append("TP ATR expansion")
        else:
            tp = entry + stop_distance * Decimal("1.5")
            reason_parts.append("TP 1.5R structure distance")
    else:
        if swing_high is not None and swing_high > entry:
            sl = swing_high + (
                atr_d * Decimal("0.15") if atr_d else entry * Decimal("0.0001")
            )
            reason_parts.append("SL behind nearest swing high")
        elif fallback_dist:
            sl = entry + fallback_dist
            reason_parts.append("SL ATR fallback (no swing high)")
        else:
            return StructureTargets(
                entry,
                None,
                None,
                None,
                None,
                "Cannot place SELL SL without structure/ATR",
            )
        stop_distance = sl - entry
        if (
            max_structure_stop is not None
            and fallback_dist is not None
            and stop_distance > max_structure_stop
        ):
            sl = entry + fallback_dist
            stop_distance = fallback_dist
            reason_parts.append(
                f"SL capped to ATR×{cfg.stop_atr_mult} "
                f"(structure stop > {max_structure_stop})"
            )
        fixed_r = cfg.fixed_tp_r
        if fixed_r is not None and fixed_r > 0:
            tp = entry - stop_distance * fixed_r
            reason_parts.append(f"TP fixed {fixed_r}R")
        elif liq_low is not None and liq_low < entry:
            tp = liq_low
            reason_parts.append("TP liquidity low")
        elif swing_low is not None and swing_low < entry:
            tp = swing_low
            reason_parts.append("TP nearby swing low")
        elif atr_d:
            tp = entry - atr_d * cfg.atr_tp_mult
            reason_parts.append("TP ATR expansion")
        else:
            tp = entry - stop_distance * Decimal("1.5")
            reason_parts.append("TP 1.5R structure distance")

    if stop_distance <= 0:
        return StructureTargets(
            entry, None, None, None, None, "Non-positive stop distance"
        )
    reward = abs(tp - entry)
    expected_rr = (reward / stop_distance).quantize(Decimal("0.01"))
    return StructureTargets(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        stop_distance=stop_distance,
        expected_rr=expected_rr,
        reason="; ".join(reason_parts),
    )
