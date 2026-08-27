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
from app.domain.market_data.timeframe import Timeframe

_NOISE_ATR_MULT = Decimal("0.35")


@dataclass(frozen=True, slots=True)
class StructureTargets:
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    stop_distance: Decimal | None
    expected_rr: Decimal | None
    reason: str
    stop_source: str | None = None
    stop_atr: Decimal | None = None

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
            "stop_source": self.stop_source,
            "stop_atr": str(self.stop_atr) if self.stop_atr is not None else None,
        }


def _dec(v: Any) -> Decimal | None:
    """Unwrap Price / Decimal. Never invent a level."""
    current: Any = v
    for _ in range(4):
        if current is None:
            return None
        nested = getattr(current, "value", None)
        if nested is not None and nested is not current:
            current = nested
            continue
        amount = getattr(current, "amount", None)
        if amount is not None and amount is not current:
            current = amount
            continue
        break
    try:
        d = Decimal(str(current))
        return d if d.is_finite() and d > 0 else None
    except (TypeError, ValueError, ArithmeticError):
        return None


def _seq(obj: Any, name: str) -> list[Any]:
    raw = getattr(obj, name, None) if obj is not None else None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _upper(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def select_scalp_stop_distance(
    *,
    structure_distance: Decimal | None,
    atr: Decimal | None,
    stop_atr_mult: Decimal,
    min_atr_mult: Decimal = _NOISE_ATR_MULT,
) -> tuple[Decimal | None, str]:
    """Choose a scalp stop that is structural when tight, ATR-capped when wide.

    Never enlarges risk past ``stop_atr_mult × ATR``. Never uses a stop inside
    the noise floor. Does not change Risk / min-lot math.
    """
    if atr is None or atr <= 0:
        if structure_distance is not None and structure_distance > 0:
            return structure_distance, "structure"
        return None, "none"
    floor = atr * min_atr_mult
    cap = atr * stop_atr_mult
    if cap <= 0:
        return None, "none"
    if structure_distance is None or structure_distance <= 0:
        return cap, "atr_fallback"
    if structure_distance > cap:
        return cap, "atr_cap"
    if structure_distance < floor:
        return floor, "noise_floor"
    return structure_distance, "structure"


def _collect_swings(structure: Any) -> tuple[list[Decimal], list[Decimal]]:
    lows: list[Decimal] = []
    highs: list[Decimal] = []
    if structure is None:
        return lows, highs
    seed_low = _dec(getattr(structure, "last_swing_low", None)) or _dec(
        getattr(structure, "swing_low", None)
    )
    seed_high = _dec(getattr(structure, "last_swing_high", None)) or _dec(
        getattr(structure, "swing_high", None)
    )
    if seed_low is not None:
        lows.append(seed_low)
    if seed_high is not None:
        highs.append(seed_high)
    for swing in _seq(structure, "swings")[-12:]:
        price = _dec(getattr(swing, "price", None))
        kind = _upper(getattr(swing, "kind", None))
        if price is None:
            continue
        if "LOW" in kind:
            lows.append(price)
        if "HIGH" in kind:
            highs.append(price)
    return lows, highs


def _zone_invalidations(
    snapshot: MarketAnalysisSnapshot,
    *,
    side: TradeDirection,
) -> tuple[list[Decimal], list[Decimal]]:
    """FVG/OB far bounds — legitimate tighter invalidation than a distant swing."""
    lows: list[Decimal] = []
    highs: list[Decimal] = []
    ob_snap = getattr(snapshot, "order_blocks", None)
    for block in _seq(ob_snap, "order_blocks")[:24]:
        state = _upper(getattr(block, "state", None))
        if state and state not in {"ACTIVE", "VALIDATED", ""}:
            continue
        bias = _upper(
            getattr(block, "bias", None)
            or getattr(block, "side", None)
            or getattr(block, "direction", None)
        )
        if side is TradeDirection.BUY and not any(
            t in bias for t in ("BUY", "BULL", "UP", "LONG")
        ):
            continue
        if side is TradeDirection.SELL and not any(
            t in bias for t in ("SELL", "BEAR", "DOWN", "SHORT")
        ):
            continue
        zone = getattr(block, "zone", None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        if lo is not None:
            lows.append(lo)
        if hi is not None:
            highs.append(hi)

    fvg_snap = getattr(snapshot, "fair_value_gaps", None)
    for gap in _seq(fvg_snap, "active_gaps")[:24]:
        bias = _upper(
            getattr(gap, "side", None)
            or getattr(gap, "bias", None)
            or getattr(gap, "direction", None)
        )
        if side is TradeDirection.BUY and not any(
            t in bias for t in ("BUY", "BULL", "UP", "LONG")
        ):
            continue
        if side is TradeDirection.SELL and not any(
            t in bias for t in ("SELL", "BEAR", "DOWN", "SHORT")
        ):
            continue
        zone = getattr(gap, "zone", None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        if lo is not None:
            lows.append(lo)
        if hi is not None:
            highs.append(hi)
    return lows, highs


def compute_structure_targets(
    snapshot: MarketAnalysisSnapshot,
    *,
    direction: TradeDirection,
    entry: Decimal | None,
    atr: Decimal | None,
    config: AiScalpingConfig | None = None,
) -> StructureTargets:
    """Place SL behind nearest legitimate invalidation; TP at liquidity / ATR."""
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
    buffer = atr_d * Decimal("0.15") if atr_d else entry * Decimal("0.0001")

    candidate_lows: list[Decimal] = []
    candidate_highs: list[Decimal] = []
    # Prefer M5 execution swings when present; M15 primary is context only.
    smap = getattr(snapshot, "structure_by_tf", None)
    if isinstance(smap, dict):
        m5 = smap.get(Timeframe.M5.value) or smap.get("M5")
        m5_lows, m5_highs = _collect_swings(m5)
        candidate_lows.extend(m5_lows)
        candidate_highs.extend(m5_highs)
    zone_lows, zone_highs = _zone_invalidations(snapshot, side=direction)
    candidate_lows.extend(zone_lows)
    candidate_highs.extend(zone_highs)
    prim_lows, prim_highs = _collect_swings(getattr(snapshot, "primary_structure", None))
    candidate_lows.extend(prim_lows)
    candidate_highs.extend(prim_highs)

    below_entry_lows = [p for p in candidate_lows if p < entry]
    above_entry_highs = [p for p in candidate_highs if p > entry]
    swing_low = max(below_entry_lows) if below_entry_lows else None
    swing_high = min(above_entry_highs) if above_entry_highs else None

    liq = snapshot.liquidity
    liq_high = None
    liq_low = None
    if liq:
        for pool in _seq(liq, "pools")[-6:]:
            price = _dec(getattr(pool, "price", None))
            side = _upper(getattr(pool, "side", None))
            if price is None:
                continue
            if "HIGH" in side or "ASK" in side:
                liq_high = price if liq_high is None else max(liq_high, price)
            if "LOW" in side or "BID" in side:
                liq_low = price if liq_low is None else min(liq_low, price)

    reason_parts: list[str] = []
    raw_distance: Decimal | None = None
    if direction is TradeDirection.BUY:
        if swing_low is not None:
            raw_distance = entry - (swing_low - buffer)
            reason_parts.append("SL behind nearest swing/zone low")
        elif atr_d:
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
    else:
        if swing_high is not None:
            raw_distance = (swing_high + buffer) - entry
            reason_parts.append("SL behind nearest swing/zone high")
        elif atr_d:
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

    stop_distance, source = select_scalp_stop_distance(
        structure_distance=raw_distance,
        atr=atr_d,
        stop_atr_mult=cfg.stop_atr_mult,
    )
    if stop_distance is None or stop_distance <= 0:
        return StructureTargets(
            entry, None, None, None, None, "Non-positive stop distance"
        )
    if source == "atr_cap":
        reason_parts.append(
            f"SL capped to ATR×{cfg.stop_atr_mult} (structure stop too wide for scalp)"
        )
    elif source == "noise_floor":
        reason_parts.append("SL lifted to noise floor")
    elif source == "atr_fallback":
        reason_parts.append(f"SL ATR×{cfg.stop_atr_mult}")

    if direction is TradeDirection.BUY:
        sl = entry - stop_distance
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
        sl = entry + stop_distance
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

    reward = abs(tp - entry)
    expected_rr = (reward / stop_distance).quantize(Decimal("0.01"))
    return StructureTargets(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        stop_distance=stop_distance,
        expected_rr=expected_rr,
        reason="; ".join(reason_parts),
        stop_source=source,
        stop_atr=atr_d,
    )
