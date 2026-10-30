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
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MIN_REWARD_RISK,
    OWNER_TP_MAX_STRUCTURE_LEVELS,
    owner_stop_distance,
    reward_risk_after_spread,
)
from app.domain.market_data.timeframe import Timeframe
from core.logging import get_logger

logger = get_logger(__name__)

_NOISE_ATR_MULT = Decimal("0.35")


def atr_scalp_geometry_rr(config: AiScalpingConfig | None = None) -> Decimal | None:
    """Natural ATR-target RR (atr_tp_mult / stop_atr_mult). Never a manufactured TP.

    Regime / sniper floors must not demand more than this when TP is the
    profile ATR expansion. Does not change Risk, Safety, or the RR > 1 gate.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    stop_mult = cfg.stop_atr_mult
    tp_mult = cfg.atr_tp_mult
    if stop_mult is None or stop_mult <= 0 or tp_mult is None or tp_mult <= 0:
        return None
    return (tp_mult / stop_mult).quantize(Decimal("0.01"))


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
    # Owner TP: which structure level (1 or 2) and what kind of level it was.
    tp_level: int | None = None
    tp_source: str | None = None

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
            "tp_level": self.tp_level,
            "tp_source": self.tp_source,
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

    Never enlarges risk past ``stop_atr_mult x ATR``. Never uses a stop inside
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


def choose_strategy_stop_distance(
    snapshot: MarketAnalysisSnapshot | None,
    *,
    direction: TradeDirection,
    entry: Decimal | None,
    atr: Decimal | None,
    stop_atr_mult: Decimal,
    ai_stop_distance: Decimal | None = None,
    config: AiScalpingConfig | None = None,
) -> tuple[Decimal | None, str]:
    """Structure-first scalp stop; ATR is a cap/fallback.

    Prefers the tightest already-valid strategy stop (swing / FVG / AI
    invalidation / ATR x mult). Never clamps to a min-lot max-stop to
    manufacture eligibility.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if cfg.stop_atr_mult != stop_atr_mult:
        from dataclasses import replace

        cfg = replace(cfg, stop_atr_mult=stop_atr_mult)

    candidates: list[tuple[Decimal, str]] = []
    if (
        snapshot is not None
        and direction in {TradeDirection.BUY, TradeDirection.SELL}
        and entry is not None
        and entry > 0
    ):
        targets = compute_structure_targets(
            snapshot,
            direction=direction,
            entry=entry,
            atr=atr,
            config=cfg,
        )
        if targets.stop_distance is not None and targets.stop_distance > 0:
            src = targets.stop_source or "structure"
            if cfg.owner_atr_stop:
                # Owner policy: max(k x ATR, structure + spread) is final — a
                # tighter candidate would shrink the stop to fit.
                return targets.stop_distance, src
            candidates.append((targets.stop_distance, src))
    if cfg.owner_atr_stop:
        return None, "none"

    if ai_stop_distance is not None and ai_stop_distance > 0:
        chosen, source = select_scalp_stop_distance(
            structure_distance=ai_stop_distance,
            atr=atr,
            stop_atr_mult=stop_atr_mult,
        )
        if chosen is not None and chosen > 0:
            candidates.append((chosen, source if source != "structure" else "ai"))

    atr_chosen, atr_source = select_scalp_stop_distance(
        structure_distance=None,
        atr=atr,
        stop_atr_mult=stop_atr_mult,
    )
    if atr_chosen is not None and atr_chosen > 0:
        candidates.append((atr_chosen, atr_source))

    if not candidates:
        return None, "none"
    # Tightest legitimate invalidation — never a min-lot clamp.
    return min(candidates, key=lambda item: item[0])


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


@dataclass(frozen=True, slots=True)
class OwnerTpChoice:
    """Owner TP pick among real structure levels beyond entry."""

    level: int | None
    price: Decimal | None
    source: str | None
    rr_after_spread: Decimal | None
    considered: tuple[tuple[int, Decimal, str, Decimal | None], ...]


def owner_tp_levels(
    levels: list[tuple[Decimal, str]],
    *,
    direction: TradeDirection,
    entry: Decimal,
    merge_tolerance: Decimal,
) -> list[tuple[Decimal, str]]:
    """Real structure levels beyond entry, nearest first.

    Levels within ``merge_tolerance`` of the previous kept level are the same
    level at execution (the spread) and are merged, keeping the nearer price.
    """
    if direction is TradeDirection.BUY:
        beyond = sorted((p, s) for p, s in levels if p > entry)
    else:
        beyond = sorted(((p, s) for p, s in levels if p < entry), reverse=True)
    merged: list[tuple[Decimal, str]] = []
    for price, src in beyond:
        if merged and abs(price - merged[-1][0]) <= merge_tolerance:
            kept_price, kept_src = merged[-1]
            if src not in kept_src.split("+"):
                merged[-1] = (kept_price, f"{kept_src}+{src}")
            continue
        merged.append((price, src))
    return merged


def select_owner_structure_tp(
    levels: list[tuple[Decimal, str]],
    *,
    entry: Decimal,
    stop_distance: Decimal,
    spread: Decimal,
    min_rr: Decimal = OWNER_MIN_REWARD_RISK,
    max_levels: int = OWNER_TP_MAX_STRUCTURE_LEVELS,
) -> OwnerTpChoice:
    """Nearest of the first ``max_levels`` levels with RR after spread >= min.

    ``levels`` come from :func:`owner_tp_levels` (nearest first). Never looks
    past the second level and never stretches a TP beyond a real level.
    """
    considered: list[tuple[int, Decimal, str, Decimal | None]] = []
    for idx, (price, src) in enumerate(levels[:max_levels], start=1):
        rr = reward_risk_after_spread(
            tp_distance=abs(price - entry),
            stop_distance=stop_distance,
            spread=spread,
        )
        considered.append((idx, price, src, rr))
        if rr is not None and rr >= min_rr:
            return OwnerTpChoice(idx, price, src, rr, tuple(considered))
    return OwnerTpChoice(None, None, None, None, tuple(considered))


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
    spread = _dec(getattr(snapshot, "spread", None))
    if cfg.owner_atr_stop and spread is not None and spread > 0:
        # Owner policy: the stop sits beyond structure by the spread.
        buffer = spread

    candidate_lows: list[Decimal] = []
    candidate_highs: list[Decimal] = []
    # Owner TP candidates, labelled by kind of structure level.
    tp_lows: list[tuple[Decimal, str]] = []
    tp_highs: list[tuple[Decimal, str]] = []
    # Prefer M5 execution swings when present; M15 primary is context only.
    # The owner policy also uses M1 swings (nearest M1/M5 structure).
    smap = getattr(snapshot, "structure_by_tf", None)
    if isinstance(smap, dict):
        tfs = ("M5", "M1") if cfg.owner_atr_stop else ("M5",)
        for tf in tfs:
            tf_structure = smap.get(Timeframe(tf).value) or smap.get(tf)
            tf_lows, tf_highs = _collect_swings(tf_structure)
            candidate_lows.extend(tf_lows)
            candidate_highs.extend(tf_highs)
            tp_lows.extend((p, f"swing_{tf}") for p in tf_lows)
            tp_highs.extend((p, f"swing_{tf}") for p in tf_highs)
    zone_lows, zone_highs = _zone_invalidations(snapshot, side=direction)
    candidate_lows.extend(zone_lows)
    candidate_highs.extend(zone_highs)
    prim_lows, prim_highs = _collect_swings(
        getattr(snapshot, "primary_structure", None)
    )
    candidate_lows.extend(prim_lows)
    candidate_highs.extend(prim_highs)
    tp_lows.extend((p, "swing_primary") for p in prim_lows)
    tp_highs.extend((p, "swing_primary") for p in prim_highs)
    # Zones as targets: the near edge of any active OB/FVG beyond entry.
    opposite = (
        TradeDirection.SELL if direction is TradeDirection.BUY else TradeDirection.BUY
    )
    opp_lows, opp_highs = _zone_invalidations(snapshot, side=opposite)
    tp_highs.extend((p, "zone") for p in [*zone_lows, *opp_lows])
    tp_lows.extend((p, "zone") for p in [*zone_highs, *opp_highs])

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
                tp_highs.append((price, "liquidity"))
            if "LOW" in side or "BID" in side:
                liq_low = price if liq_low is None else min(liq_low, price)
                tp_lows.append((price, "liquidity"))

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

    if cfg.owner_atr_stop:
        stop_distance = owner_stop_distance(
            atr=atr_d,
            structure_distance=raw_distance,
            multiplier=cfg.owner_stop_atr_mult,
        )
        if stop_distance is not None and atr_d is not None:
            floor = atr_d * cfg.owner_stop_atr_mult
            source = (
                "owner_structure"
                if raw_distance is not None and stop_distance > floor
                else "owner_atr"
            )
            reason_parts.append(
                f"SL = max({cfg.owner_stop_atr_mult} x ATR, structure + spread)"
            )
        else:
            source = "none"
    else:
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
            f"SL capped to ATRx{cfg.stop_atr_mult} (structure stop too wide for scalp)"
        )
    elif source == "noise_floor":
        reason_parts.append("SL lifted to noise floor")
    elif source == "atr_fallback":
        reason_parts.append(f"SL ATRx{cfg.stop_atr_mult}")

    if cfg.owner_atr_stop:
        return _owner_targets(
            direction=direction,
            entry=entry,
            stop_distance=stop_distance,
            spread=spread or Decimal("0"),
            tp_levels=tp_highs if direction is TradeDirection.BUY else tp_lows,
            reason_parts=reason_parts,
            stop_source=source,
            atr=atr_d,
        )

    if direction is TradeDirection.BUY:
        sl = entry - stop_distance
        if liq_high is not None and liq_high > entry:
            tp = liq_high
            reason_parts.append("TP liquidity high")
        elif swing_high is not None and swing_high > entry:
            tp = swing_high
            reason_parts.append("TP nearby swing high")
        elif atr_d:
            tp = entry + atr_d * cfg.atr_tp_mult
            reason_parts.append("TP ATR expansion")
        else:
            return StructureTargets(
                entry,
                sl,
                None,
                stop_distance,
                None,
                "Cannot place BUY TP without structure/liquidity/ATR",
                stop_source=source,
                stop_atr=atr_d,
            )
    else:
        sl = entry + stop_distance
        if liq_low is not None and liq_low < entry:
            tp = liq_low
            reason_parts.append("TP liquidity low")
        elif swing_low is not None and swing_low < entry:
            tp = swing_low
            reason_parts.append("TP nearby swing low")
        elif atr_d:
            tp = entry - atr_d * cfg.atr_tp_mult
            reason_parts.append("TP ATR expansion")
        else:
            return StructureTargets(
                entry,
                sl,
                None,
                stop_distance,
                None,
                "Cannot place SELL TP without structure/liquidity/ATR",
                stop_source=source,
                stop_atr=atr_d,
            )

    reward = abs(tp - entry)
    expected_rr = (reward / stop_distance).quantize(Decimal("0.01"))
    min_rr = cfg.min_expected_rr if cfg.min_expected_rr is not None else Decimal("1")
    if min_rr < Decimal("1"):
        min_rr = Decimal("1")
    atr_tp = None
    atr_rr = None
    if atr_d is not None and atr_d > 0:
        atr_tp = (
            entry + atr_d * cfg.atr_tp_mult
            if direction is TradeDirection.BUY
            else entry - atr_d * cfg.atr_tp_mult
        )
        atr_reward = abs(atr_tp - entry)
        atr_rr = (atr_reward / stop_distance).quantize(Decimal("0.01"))
    # Nearby swing/liquidity inside the stop (RR<=1) is never a valid scalp TP.
    # Structural TP below the profile min RR is poor asymmetry — prefer ATR
    # when it is market-plausible (RR>1). Do not stretch to preferred fixed_tp_r.
    if expected_rr <= Decimal("1") or expected_rr < min_rr:
        if (
            atr_tp is not None
            and atr_rr is not None
            and atr_rr > Decimal("1")
            and atr_rr > expected_rr
        ):
            tp = atr_tp
            reward = abs(tp - entry)
            expected_rr = atr_rr
            reason_parts.append(
                "TP ATR expansion "
                "(structure/liquidity target did not exceed SL risk "
                "or profile min RR)"
            )
        if expected_rr <= Decimal("1"):
            return StructureTargets(
                entry,
                sl,
                None,
                stop_distance,
                expected_rr,
                "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
                f"planned TP reward {reward} <= SL risk {stop_distance}",
                stop_source=source,
                stop_atr=atr_d,
            )
        if expected_rr < min_rr:
            return StructureTargets(
                entry,
                sl,
                None,
                stop_distance,
                expected_rr,
                "TP_INSUFFICIENT_ASYMMETRY: "
                f"expected_rr {expected_rr} < min_expected_rr {min_rr} "
                "(do not stretch TP; WAIT)",
                stop_source=source,
                stop_atr=atr_d,
            )
    preferred = cfg.fixed_tp_r
    if preferred is not None and preferred > 0 and expected_rr >= preferred:
        reason_parts.append(f"TP structural {expected_rr}R (>= preferred {preferred}R)")
    else:
        reason_parts.append(
            f"TP structural {expected_rr}R (not stretched to preferred)"
        )
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


def _owner_targets(
    *,
    direction: TradeDirection,
    entry: Decimal,
    stop_distance: Decimal,
    spread: Decimal,
    tp_levels: list[tuple[Decimal, str]],
    reason_parts: list[str],
    stop_source: str,
    atr: Decimal | None,
) -> StructureTargets:
    """Owner TP: nearest structure level clearing 1.50 RR, at most level 2."""
    if direction is TradeDirection.BUY:
        sl = entry - stop_distance
    else:
        sl = entry + stop_distance
    levels = owner_tp_levels(
        tp_levels,
        direction=direction,
        entry=entry,
        merge_tolerance=spread if spread > 0 else Decimal("0.01"),
    )
    choice = select_owner_structure_tp(
        levels, entry=entry, stop_distance=stop_distance, spread=spread
    )
    tried = ", ".join(
        f"L{idx} {src} {price} RR "
        f"{rr.quantize(Decimal('0.01')) if rr is not None else 'n/a'}"
        for idx, price, src, rr in choice.considered
    )
    if choice.price is None:
        best = max((abs(p - entry) for _, p, _, _ in choice.considered), default=None)
        return StructureTargets(
            entry,
            sl,
            None,
            stop_distance,
            (best / stop_distance).quantize(Decimal("0.01")) if best else None,
            "OWNER_TP_NO_STRUCTURE_RR: no structure level within "
            f"{OWNER_TP_MAX_STRUCTURE_LEVELS} gives RR after spread >= "
            f"{OWNER_MIN_REWARD_RISK} ({tried or 'no level beyond entry'}); "
            "TP not stretched",
            stop_source=stop_source,
            stop_atr=atr,
        )
    tp = choice.price
    expected_rr = (abs(tp - entry) / stop_distance).quantize(Decimal("0.01"))
    rr_after = (choice.rr_after_spread or Decimal("0")).quantize(Decimal("0.01"))
    reason_parts.append(
        f"TP structure level {choice.level} ({choice.source} {tp}) "
        f"RR after spread {rr_after} [{tried}]"
    )
    logger.info(
        "owner_tp_level_selected",
        direction=direction.value,
        entry=str(entry),
        stop_loss=str(sl),
        take_profit=str(tp),
        tp_level=choice.level,
        tp_source=choice.source,
        rr_after_spread=str(rr_after),
        stop_distance=str(stop_distance),
        spread=str(spread),
    )
    return StructureTargets(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        stop_distance=stop_distance,
        expected_rr=expected_rr,
        reason="; ".join(reason_parts),
        stop_source=stop_source,
        stop_atr=atr,
        tp_level=choice.level,
        tp_source=choice.source,
    )
