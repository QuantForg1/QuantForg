"""XAUUSD sniper entry contract — uses existing snapshot facts only.

Not a second strategy, OMS, or scoring engine. Conflicting or incomplete
evidence returns WAIT. Never flips BUY into SELL or SELL into BUY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    iter_scalp_structure_entries,
    iter_scalp_structures,
    structure_event_side,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot

# Structure TF for scalping FVG is M15; ATR is computed on entry TF (M5).
# Chase must compare distance in the *zone* timeframe, not a faster ATR.
_TF_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}
_STALE_FRESHNESS_BARS = 40
_STALE_MAX_AGE = timedelta(hours=12)
_CHASE_ATR_MULT = Decimal("1.5")


def _seq(obj: Any, name: str) -> list[Any]:
    raw = getattr(obj, name, None) if obj is not None else None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _upper(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _dec(value: Any) -> Decimal | None:
    """Unwrap Price / Decimal / numeric zone bounds. Never invent a price."""
    current: Any = value
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
        return d if d.is_finite() else None
    except (TypeError, ValueError, ArithmeticError):
        return None


def _intish(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _tf_minutes(raw: Any) -> int | None:
    token = str(getattr(raw, "value", raw) or "").strip().upper()
    return _TF_MINUTES.get(token)


def _atr_for_zone(
    atr: Decimal,
    *,
    atr_timeframe: str | None,
    zone_timeframe: Any,
    source: str | None = None,
) -> Decimal:
    """Scale ATR to the FVG/OB timeframe so M5 ATR is not used as M15 chase.

    Production FVG/OB are detected on structure TF (M15). Entry ATR is M5.
    Missing FVG or OB timeframe still scales M5→M15. Never compare an
    M15 structure zone against unscaled M5 distance.
    """
    src = _tf_minutes(atr_timeframe) or _tf_minutes("M5")
    dst = _tf_minutes(zone_timeframe)
    if dst is None and source in {"fvg", "ob", "order_block"}:
        dst = _tf_minutes("M15")
    if dst is None:
        dst = src
    if src is None or dst is None or dst <= src or atr <= 0:
        return atr
    ratio = (Decimal(dst) / Decimal(src)).sqrt()
    scaled = atr * ratio
    return scaled if scaled.is_finite() and scaled > 0 else atr


_CANONICAL_BLOCKER = {
    "WAIT_ABNORMAL_SPREAD": "WAIT_SPREAD",
    "WAIT_STALE_FVG": "WAIT_STALE",
    "WAIT_STALE_DATA": "WAIT_STALE",
    "WAIT_CONFLICTING_BUY_SELL": "WAIT_CONFLICT",
    "WAIT_SNIPER_INCOMPLETE": "WAIT_CONFIRMATION",
    "WAIT_NO_SNIPER_TRIGGER": "WAIT_CONFIRMATION",
    "WAIT_NO_DIRECTIONAL_EDGE": "WAIT_CONFIRMATION",
}


def canonical_sniper_blocker(primary: str | None) -> str | None:
    if not primary:
        return None
    return _CANONICAL_BLOCKER.get(primary, primary)


def _side_of_break(break_dir: Any) -> TradeDirection | None:
    raw = _upper(break_dir)
    if raw in {"UP", "BULLISH", "BUY", "LONG"}:
        return TradeDirection.BUY
    if raw in {"DOWN", "BEARISH", "SELL", "SHORT"}:
        return TradeDirection.SELL
    return None


def _sweep_side(sweep: Any) -> TradeDirection | None:
    kind = _upper(getattr(sweep, "kind", None))
    if "LOW" in kind:
        return TradeDirection.BUY
    if "HIGH" in kind:
        return TradeDirection.SELL
    raw = _upper(getattr(sweep, "side", None) or getattr(sweep, "bias", None))
    if any(t in raw for t in ("LOW", "BID", "BUY", "BULL")):
        return TradeDirection.BUY
    if any(t in raw for t in ("HIGH", "ASK", "SELL", "BEAR")):
        return TradeDirection.SELL
    return None


def _bias_side(raw_obj: Any) -> TradeDirection | None:
    raw = _upper(
        getattr(raw_obj, "bias", None)
        or getattr(raw_obj, "side", None)
        or getattr(raw_obj, "direction", None)
        or raw_obj
    )
    if "BUY" in raw or "BULL" in raw or raw in {"UP", "LONG"}:
        return TradeDirection.BUY
    if "SELL" in raw or "BEAR" in raw or raw in {"DOWN", "SHORT"}:
        return TradeDirection.SELL
    return None


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class _AlignedZone:
    high: Decimal
    low: Decimal
    timeframe: Any
    freshness_bars: int | None
    formed_at: datetime | None
    source: str
    stale: bool


def _zone_is_stale(
    *,
    freshness_bars: int | None,
    formed_at: datetime | None,
    now: datetime,
) -> bool:
    if freshness_bars is not None and freshness_bars > _STALE_FRESHNESS_BARS:
        return True
    ts = _as_utc(formed_at)
    if ts is None:
        return False
    return (now - ts) > _STALE_MAX_AGE


def _iter_zone_snapshots(snapshot: Any, primary_attr: str, extra_attr: str) -> list[Any]:
    """Primary M15 snapshot plus optional LTF (M1/M5) snapshots."""
    snaps: list[Any] = []
    primary = getattr(snapshot, primary_attr, None)
    if primary is not None:
        snaps.append(primary)
    extra = getattr(snapshot, extra_attr, None)
    if isinstance(extra, (list, tuple)):
        snaps.extend(s for s in extra if s is not None and s is not primary)
    return snaps


def _append_ob_zones(
    out: list[_AlignedZone],
    ob_snap: Any,
    side: TradeDirection,
    *,
    now: datetime,
) -> None:
    for block in _seq(ob_snap, "order_blocks")[:24]:
        state = _upper(getattr(block, "state", None))
        if state and state not in {"ACTIVE", "VALIDATED", ""}:
            continue
        if _bias_side(block) is not side:
            continue
        zone = getattr(block, "zone", None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        if hi is None or lo is None:
            continue
        freshness = _intish(
            getattr(getattr(block, "quality", None), "freshness_bars", None)
        )
        formed = getattr(zone, "formed_at", None) or getattr(block, "formed_at", None)
        tf = getattr(zone, "timeframe", None) or getattr(block, "timeframe", None)
        out.append(
            _AlignedZone(
                high=max(hi, lo),
                low=min(hi, lo),
                timeframe=tf,
                freshness_bars=freshness,
                formed_at=_as_utc(formed),
                source="ob",
                stale=_zone_is_stale(
                    freshness_bars=freshness, formed_at=formed, now=now
                ),
            )
        )


def _append_fvg_zones(
    out: list[_AlignedZone],
    fvg_snap: Any,
    side: TradeDirection,
    *,
    now: datetime,
) -> None:
    for gap in _seq(fvg_snap, "active_gaps")[:24]:
        if _bias_side(gap) is not side:
            continue
        zone = getattr(gap, "zone", None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        if hi is None or lo is None:
            continue
        quality = getattr(gap, "quality", None)
        freshness = _intish(
            getattr(quality, "freshness_bars", None) if quality else None
        )
        formed = (
            getattr(zone, "formed_at", None)
            or getattr(gap, "formed_at", None)
            or getattr(getattr(gap, "lifecycle", None), "detected_at", None)
        )
        tf = getattr(zone, "timeframe", None) or getattr(gap, "timeframe", None)
        out.append(
            _AlignedZone(
                high=max(hi, lo),
                low=min(hi, lo),
                timeframe=tf,
                freshness_bars=freshness,
                formed_at=_as_utc(formed),
                source="fvg",
                stale=_zone_is_stale(
                    freshness_bars=freshness, formed_at=formed, now=now
                ),
            )
        )


def _collect_aligned_zones(
    snapshot: MarketAnalysisSnapshot,
    side: TradeDirection,
    *,
    now: datetime,
) -> list[_AlignedZone]:
    out: list[_AlignedZone] = []
    for ob_snap in _iter_zone_snapshots(
        snapshot, "order_blocks", "ltf_order_blocks"
    ):
        _append_ob_zones(out, ob_snap, side, now=now)
    for fvg_snap in _iter_zone_snapshots(
        snapshot, "fair_value_gaps", "ltf_fair_value_gaps"
    ):
        _append_fvg_zones(out, fvg_snap, side, now=now)
    return out


def _chase_distance(
    *,
    side: TradeDirection,
    ref: Decimal,
    zone: _AlignedZone,
    atr: Decimal,
    atr_timeframe: str | None,
) -> tuple[Decimal, Decimal, bool, str]:
    """Return (distance, extension, is_chase, entry_state).

    INSIDE / RETEST / EARLY are never chase. EXTENDED is chase only beyond
    1.5× zone-timeframe ATR.
    """
    zone_atr = _atr_for_zone(
        atr,
        atr_timeframe=atr_timeframe,
        zone_timeframe=zone.timeframe,
        source=zone.source,
    )
    extension = zone_atr * _CHASE_ATR_MULT
    if side is TradeDirection.BUY:
        if zone.low <= ref <= zone.high:
            return Decimal("0"), extension, False, "RETEST"
        if ref < zone.low:
            return Decimal("0"), extension, False, "EARLY"
        distance = ref - zone.high
        if distance > extension:
            return distance, extension, True, "EXTENDED"
        return distance, extension, False, "CONTROLLED"
    if zone.low <= ref <= zone.high:
        return Decimal("0"), extension, False, "RETEST"
    if ref > zone.high:
        return Decimal("0"), extension, False, "EARLY"
    distance = zone.low - ref
    if distance > extension:
        return distance, extension, True, "EXTENDED"
    return distance, extension, False, "CONTROLLED"


def _nearest_zone(
    zones: list[_AlignedZone],
    *,
    side: TradeDirection,
    ref: Decimal,
) -> _AlignedZone | None:
    if not zones:
        return None

    def _key(zone: _AlignedZone) -> Decimal:
        if zone.low <= ref <= zone.high:
            return Decimal("0")
        if side is TradeDirection.BUY:
            if ref > zone.high:
                return ref - zone.high
            return zone.low - ref
        if ref < zone.low:
            return zone.low - ref
        return ref - zone.high

    return min(zones, key=_key)


def _evidence_families(
    snapshot: MarketAnalysisSnapshot,
    side: TradeDirection,
    *,
    now: datetime,
    standing_levels: bool = True,
) -> list[str]:
    """Independent families present for one side. Discovery only — not TAKE.

    ``standing_levels=False`` skips equal highs/lows. Those persist across
    cycles and must not globally mark BUY+SELL as CONFLICT when the real
    blocker is an insufficient LTF edge.
    """
    families: list[str] = []
    for structure in iter_scalp_structures(snapshot):
        found = False
        for br in _seq(structure, "breaks_of_structure")[-3:]:
            mapped = structure_event_side(br) or _side_of_break(
                getattr(br, "direction", None)
            )
            if mapped is side:
                families.append("structure")
                found = True
                break
        if found:
            break
        for ch in _seq(structure, "changes_of_character")[-2:]:
            mapped = structure_event_side(ch)
            if mapped is side:
                families.append("structure")
                found = True
                break
        if found:
            break
    liq = snapshot.liquidity
    for sw in _seq(liq, "sweeps")[-3:]:
        if _sweep_side(sw) is side:
            families.append("liquidity")
            break
    if standing_levels and "liquidity" not in families:
        eqh = _seq(liq, "equal_highs")
        eql = _seq(liq, "equal_lows")
        if side is TradeDirection.SELL and eqh:
            families.append("liquidity")
        elif side is TradeDirection.BUY and eql:
            families.append("liquidity")
    if any(not z.stale for z in _collect_aligned_zones(snapshot, side, now=now)):
        families.append("zone")
    return families


def _confluence_class(*, take: bool, independent: list[str], setup_state: str) -> str:
    if take:
        return "HIGH_CONFLUENCE" if len(independent) >= 3 else "STANDARD"
    if setup_state in {"SETUP_FORMING", "SETUP_READY"}:
        return "WEAK"
    return "INVALID"


@dataclass(frozen=True, slots=True)
class SniperEntryDecision:
    passed: bool
    action: str  # BUY | SELL | WAIT
    reasons: tuple[str, ...]
    pillars: dict[str, bool]
    primary_reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "action": self.action,
            "reasons": list(self.reasons),
            "pillars": dict(self.pillars),
            "primary_reason": self.primary_reason,
            "never_prefer_buy_only": True,
            "never_flips_direction": True,
            **dict(self.diagnostics or {}),
        }


def evaluate_sniper_entry(
    snapshot: MarketAnalysisSnapshot,
    *,
    direction: DirectionDecision,
    mid: Decimal | None = None,
    atr: Decimal | None = None,
    expected_rr: Decimal | None = None,
    min_expected_rr: Decimal | None = None,
    stop_loss: Decimal | None = None,
    setup_family_direction: str | None = None,
    spread_reject: bool = False,
    pa_score: int = 0,
    momentum: int = 0,
    min_momentum: int | None = None,
    config: AiScalpingConfig | None = None,
    bid: Decimal | None = None,
    ask: Decimal | None = None,
    atr_timeframe: str | None = None,
    spread_score: int = 0,
    now: datetime | None = None,
) -> SniperEntryDecision:
    """Require a high-quality XAUUSD trigger — trend alone is not enough."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    reasons: list[str] = []
    pillars = {
        "clear_direction": False,
        "liquidity_event": False,
        "structure_confirmation": False,
        "displacement_or_momentum": False,
        "entry_zone": False,
        "invalidation": False,
        "risk_reward": False,
        "not_chasing": True,
        "not_conflicting": True,
        "spread_ok": not spread_reject,
        "fresh_zone": True,
    }
    diagnostics: dict[str, Any] = {
        "chase_distance": None,
        "chase_extension": None,
        "zone_bound": None,
        "atr_used": str(atr) if atr is not None else None,
        "atr_timeframe": atr_timeframe,
        "ref_price": None,
        "fvg_age_bars": None,
        "zone_timeframe": None,
        "zone_source": None,
        "entry_state": None,
        "normalized_extension": None,
        "sniper_tier": None,
        "market_mid": str(mid) if mid is not None else None,
        "bid": str(bid) if bid is not None else None,
        "ask": str(ask) if ask is not None else None,
        "directional_edge": int(getattr(direction, "directional_edge", 0) or 0),
        "edge_margin": int(getattr(direction, "edge_margin", 5) or 5),
        "ltf_buy_score": int(getattr(direction, "ltf_buy_score", 0) or 0),
        "ltf_sell_score": int(getattr(direction, "ltf_sell_score", 0) or 0),
        "signal_created_at": moment.isoformat(),
        "confluence_class": "INVALID",
    }

    def _wait(primary: str, *, setup_state: str | None = None) -> SniperEntryDecision:
        canon = canonical_sniper_blocker(primary)
        diagnostics["canonical_blocker"] = canon
        if setup_state:
            diagnostics["setup_state"] = setup_state
        elif primary == "WAIT_CHASE":
            diagnostics["setup_state"] = "CHASING"
        elif primary in {"WAIT_STALE_FVG", "WAIT_STALE_DATA"}:
            diagnostics["setup_state"] = "STALE"
        elif primary == "WAIT_CONFLICTING_BUY_SELL":
            diagnostics["setup_state"] = "CONFLICT"
        elif primary == "WAIT_NO_DIRECTIONAL_EDGE":
            diagnostics["setup_state"] = "NO_SETUP"
        elif pillars.get("clear_direction") and (
            pillars.get("liquidity_event")
            or pillars.get("structure_confirmation")
            or pillars.get("entry_zone")
        ):
            diagnostics["setup_state"] = "SETUP_FORMING"
        else:
            diagnostics["setup_state"] = "WAIT"
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason=primary,
            diagnostics=diagnostics,
        )

    side = direction.direction
    if side not in {TradeDirection.BUY, TradeDirection.SELL}:
        buy_fams = _evidence_families(
            snapshot, TradeDirection.BUY, now=moment, standing_levels=False
        )
        sell_fams = _evidence_families(
            snapshot, TradeDirection.SELL, now=moment, standing_levels=False
        )
        diagnostics["buy_families"] = buy_fams
        diagnostics["sell_families"] = sell_fams
        reasons.append(
            f"WAIT — no directional edge "
            f"(bullish={direction.buy_score} bearish={direction.sell_score} "
            f"ltf={diagnostics['ltf_buy_score']}/{diagnostics['ltf_sell_score']} "
            f"margin={diagnostics['edge_margin']})"
        )
        if buy_fams and sell_fams:
            diagnostics["confluence_class"] = _confluence_class(
                take=False, independent=[], setup_state="CONFLICT"
            )
            # Scores are too close for a side. Do not label this as a
            # directional conflict that suppresses the slightly-leading side.
            return _wait("WAIT_NO_DIRECTIONAL_EDGE", setup_state="CONFLICT")
        if buy_fams or sell_fams:
            diagnostics["confluence_class"] = _confluence_class(
                take=False, independent=buy_fams or sell_fams, setup_state="SETUP_FORMING"
            )
            return _wait("WAIT_NO_DIRECTIONAL_EDGE", setup_state="SETUP_FORMING")
        diagnostics["confluence_class"] = "INVALID"
        return _wait("WAIT_NO_DIRECTIONAL_EDGE")
    pillars["clear_direction"] = True

    setup_raw = str(setup_family_direction or "").strip().upper()
    if setup_raw in {"BUY", "SELL"} and setup_raw != side.value:
        pillars["not_conflicting"] = False
        reasons.append(
            f"WAIT — conflicting evidence setup={setup_raw} vs AI={side.value}"
        )
        return _wait("WAIT_CONFLICTING_BUY_SELL")

    if spread_reject:
        reasons.append("WAIT — abnormal spread")
        return _wait("WAIT_ABNORMAL_SPREAD")

    structure_tf: str | None = None
    structure_event_at: datetime | None = None
    for tf, structure in iter_scalp_structure_entries(snapshot):
        if pillars["structure_confirmation"]:
            break
        for br in _seq(structure, "breaks_of_structure")[-3:]:
            mapped = structure_event_side(br) or _side_of_break(
                getattr(br, "direction", None)
            )
            if mapped is side:
                pillars["structure_confirmation"] = True
                structure_tf = tf
                structure_event_at = _as_utc(
                    getattr(br, "detected_at", None)
                    or getattr(br, "formed_at", None)
                    or getattr(br, "timestamp", None)
                )
                reasons.append(f"BOS confirms {side.value} ({tf})")
                break
        if pillars["structure_confirmation"]:
            break
        for ch in _seq(structure, "changes_of_character")[-2:]:
            mapped = structure_event_side(ch)
            if mapped is side:
                pillars["structure_confirmation"] = True
                structure_tf = tf
                structure_event_at = _as_utc(
                    getattr(ch, "detected_at", None)
                    or getattr(ch, "formed_at", None)
                    or getattr(ch, "timestamp", None)
                )
                reasons.append(f"CHOCH confirms {side.value} ({tf})")
                break
    diagnostics["structure_timeframe"] = structure_tf
    diagnostics["entry_timeframe"] = structure_tf or "M5"

    liq = snapshot.liquidity
    for sw in _seq(liq, "sweeps")[-3:]:
        mapped = _sweep_side(sw)
        if mapped is side:
            pillars["liquidity_event"] = True
            reasons.append(f"Liquidity sweep supports {side.value}")
            break
    if not pillars["liquidity_event"]:
        eqh = _seq(liq, "equal_highs")
        eql = _seq(liq, "equal_lows")
        if side is TradeDirection.SELL and eqh:
            pillars["liquidity_event"] = True
            reasons.append("Equal highs — bearish liquidity")
        elif side is TradeDirection.BUY and eql:
            pillars["liquidity_event"] = True
            reasons.append("Equal lows — bullish liquidity")

    displacement_ok = False
    for ob_snap in _iter_zone_snapshots(
        snapshot, "order_blocks", "ltf_order_blocks"
    ):
        for block in _seq(ob_snap, "order_blocks")[:24]:
            state = _upper(getattr(block, "state", None))
            if state and state not in {"ACTIVE", "VALIDATED", ""}:
                continue
            if _bias_side(block) is not side:
                continue
            quality = getattr(block, "quality", None)
            ratio = _dec(
                getattr(quality, "displacement_ratio", None) if quality else None
            )
            if ratio is not None and ratio >= Decimal("1.5"):
                displacement_ok = True
                reasons.append("Displacement-qualified order block")
                break
        if displacement_ok:
            break

    aligned = _collect_aligned_zones(snapshot, side, now=moment)
    fresh_zones = [z for z in aligned if not z.stale]
    stale_zones = [z for z in aligned if z.stale]
    used_stale_only = bool(stale_zones) and not fresh_zones
    diagnostics["stale_zone_count"] = len(stale_zones)
    diagnostics["fresh_zone_count"] = len(fresh_zones)
    diagnostics["stale_zone_ignored"] = False
    if fresh_zones:
        pillars["entry_zone"] = True
        if any(z.source == "fvg" for z in fresh_zones):
            reasons.append(f"Aligned FVG zone for {side.value}")
        elif any(z.source == "ob" for z in fresh_zones):
            reasons.append(f"Aligned order-block zone for {side.value}")
        diagnostics["stale_zone_ignored"] = bool(stale_zones)
    elif used_stale_only:
        diagnostics["stale_zone_ignored"] = True

    # FVG/OB is an independent zone family. Do not auto-count it as liquidity —
    # that double-counted the same evidence and then still AND-gated momentum.

    mom_floor = (
        int(min_momentum) if min_momentum is not None else int(cfg.min_momentum_score)
    )
    pa_floor = int(cfg.min_pa_confluence_score)
    if displacement_ok or momentum >= mom_floor or int(pa_score) >= pa_floor:
        pillars["displacement_or_momentum"] = True
        if not displacement_ok:
            reasons.append("Momentum/PA confirmation")

    if stop_loss is not None:
        pillars["invalidation"] = True
    else:
        reasons.append("WAIT — missing invalidation / stop")

    min_rr = min_expected_rr if min_expected_rr is not None else cfg.min_expected_rr
    if expected_rr is not None and expected_rr >= min_rr:
        pillars["risk_reward"] = True
    else:
        reasons.append(f"WAIT — insufficient RR ({expected_rr} < {min_rr})")

    ref = None
    if side is TradeDirection.BUY:
        ref = ask if ask is not None else mid
    elif side is TradeDirection.SELL:
        ref = bid if bid is not None else mid
    else:
        ref = mid
    diagnostics["ref_price"] = str(ref) if ref is not None else None

    # Measure chase only against a FRESH zone. A stale FVG must not be used
    # for TAKE and must not set a global chase/veto for other families.
    chase_zones = fresh_zones
    if used_stale_only:
        diagnostics["stale_fvg_present"] = True

    if (
        ref is not None
        and atr is not None
        and atr > 0
        and chase_zones
    ):
        nearest = _nearest_zone(chase_zones, side=side, ref=ref)
        if nearest is not None:
            distance, extension, chasing, entry_state = _chase_distance(
                side=side,
                ref=ref,
                zone=nearest,
                atr=atr,
                atr_timeframe=atr_timeframe,
            )
            zone_atr = _atr_for_zone(
                atr,
                atr_timeframe=atr_timeframe,
                zone_timeframe=nearest.timeframe,
                source=nearest.source,
            )
            diagnostics["chase_distance"] = str(distance)
            diagnostics["chase_extension"] = str(extension)
            diagnostics["atr_used"] = str(zone_atr)
            diagnostics["entry_state"] = entry_state
            diagnostics["normalized_extension"] = (
                str((distance / zone_atr).quantize(Decimal("0.01")))
                if zone_atr > 0
                else None
            )
            diagnostics["zone_bound"] = (
                str(nearest.high) if side is TradeDirection.BUY else str(nearest.low)
            )
            diagnostics["fvg_age_bars"] = nearest.freshness_bars
            diagnostics["zone_timeframe"] = str(
                getattr(nearest.timeframe, "value", nearest.timeframe) or ""
            ) or None
            diagnostics["zone_source"] = nearest.source
            diagnostics["zone_atr"] = str(zone_atr)
            diagnostics["zone_created_at"] = (
                nearest.formed_at.isoformat() if nearest.formed_at else None
            )
            diagnostics["zone_age_ms"] = (
                int((moment - nearest.formed_at).total_seconds() * 1000)
                if nearest.formed_at is not None
                else None
            )
            diagnostics["bars_since_structure_event"] = nearest.freshness_bars
            diagnostics["chase"] = {
                "zone_timeframe": diagnostics["zone_timeframe"],
                "atr_timeframe": atr_timeframe,
                "atr_value": str(zone_atr),
                "zone_distance": str(distance),
                "normalized_extension": diagnostics["normalized_extension"],
                "entry_state": entry_state,
            }
            if chasing:
                pillars["not_chasing"] = False
                reasons.append(
                    f"WAIT — chasing {side.value} after excessive displacement "
                    f"(distance={distance} > 1.5 ATR={extension} "
                    f"tf={diagnostics['zone_timeframe'] or 'M15'} "
                    f"state={entry_state})"
                )

    if (
        not pillars["liquidity_event"]
        and not pillars["structure_confirmation"]
        and not pillars["entry_zone"]
    ):
        if used_stale_only:
            pillars["fresh_zone"] = False
            diagnostics["stale_zone_ignored"] = False
            reasons.append("WAIT — stale FVG")
            diagnostics["setup_family"] = "stale_fvg"
            return _wait("WAIT_STALE_FVG", setup_state="STALE")
        reasons.append(
            "WAIT — no BOS/CHOCH/sweep/FVG/OB trigger (trend alone is not enough)"
        )
        return _wait("WAIT_NO_SNIPER_TRIGGER")

    independent: list[str] = []
    if pillars["structure_confirmation"]:
        independent.append("structure")
    if pillars["liquidity_event"]:
        independent.append("liquidity")
    if pillars["entry_zone"]:
        independent.append("zone")
    if pillars["displacement_or_momentum"]:
        independent.append("momentum")
    timing_state = str(diagnostics.get("entry_state") or "")
    if timing_state in {"RETEST", "INSIDE", "CONTROLLED"}:
        independent.append("timing")
    structural = [f for f in independent if f in {"structure", "liquidity", "zone"}]
    diagnostics["independent_evidence"] = independent
    diagnostics["independent_count"] = len(independent)
    diagnostics["structural_families"] = structural
    zone_src = diagnostics.get("zone_source")
    if pillars["entry_zone"] and zone_src in {"fvg", "ob"}:
        diagnostics["setup_family"] = str(zone_src)
    elif independent:
        diagnostics["setup_family"] = "+".join(independent)
    else:
        diagnostics["setup_family"] = None
    origin = structure_event_at
    zone_created = diagnostics.get("zone_created_at")
    if origin is None and isinstance(zone_created, str):
        origin = _as_utc(datetime.fromisoformat(zone_created.replace("Z", "+00:00")))
    diagnostics["structure_event_at"] = (
        structure_event_at.isoformat() if structure_event_at else None
    )
    diagnostics["confirmation_at"] = moment.isoformat()
    if origin is not None:
        diagnostics["signal_age_ms"] = max(
            0, int((moment - origin).total_seconds() * 1000)
        )
    else:
        diagnostics["signal_age_ms"] = 0

    buy_components = dict(getattr(direction, "buy_components", {}) or {})
    sell_components = dict(getattr(direction, "sell_components", {}) or {})
    aligned_components = (
        buy_components if side is TradeDirection.BUY else sell_components
    )
    if pillars["risk_reward"]:
        aligned_components["rr"] = int(aligned_components.get("rr") or 0) + 10
    if timing_state == "RETEST":
        aligned_components["retest"] = int(aligned_components.get("retest") or 0) + 10
    elif timing_state in {"CONTROLLED", "INSIDE"}:
        aligned_components["rejection"] = (
            int(aligned_components.get("rejection") or 0) + 6
        )
    diagnostics["buy_components"] = buy_components
    diagnostics["sell_components"] = sell_components

    core_ok = (
        pillars["clear_direction"]
        and pillars["not_conflicting"]
        and pillars["spread_ok"]
        and pillars["not_chasing"]
        and pillars["invalidation"]
        and pillars["risk_reward"]
    )
    take_ok = core_ok and len(independent) >= 2 and bool(structural)
    tight_spread = int(spread_score) >= 85
    if take_ok:
        if pillars["entry_zone"] and pillars["displacement_or_momentum"]:
            diagnostics["sniper_tier"] = "A"
            label = f"SNIPER {side.value} — Tier A"
        elif tight_spread and int(momentum) >= 70:
            diagnostics["sniper_tier"] = "C"
            label = f"MICRO SCALP {side.value} — Tier C"
        else:
            diagnostics["sniper_tier"] = "B"
            label = f"CONFIRMED SCALP {side.value} — Tier B"
        diagnostics["setup_state"] = "TAKE"
        diagnostics["canonical_blocker"] = None
        diagnostics["confluence_class"] = _confluence_class(
            take=True, independent=independent, setup_state="TAKE"
        )
        reasons.append(label)
        return SniperEntryDecision(
            passed=True,
            action=side.value,
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason=None,
            diagnostics=diagnostics,
        )

    missing = [k for k, ok in pillars.items() if not ok]
    primary = "WAIT_SNIPER_INCOMPLETE"
    setup_state: str | None = None
    if not pillars["not_chasing"]:
        primary = "WAIT_CHASE"
        setup_state = "CHASING"
    elif used_stale_only and (len(independent) < 2 or not structural):
        primary = "WAIT_STALE_FVG"
        setup_state = "STALE"
        pillars["fresh_zone"] = False
        diagnostics["stale_zone_ignored"] = False
        reasons.append("WAIT — stale FVG")
    elif not pillars["invalidation"]:
        primary = "WAIT_NO_INVALIDATION"
        setup_state = "SETUP_FORMING"
    elif not pillars["risk_reward"]:
        primary = "WAIT_INSUFFICIENT_RR"
        setup_state = "SETUP_FORMING"
    elif core_ok and structural:
        primary = "WAIT_SNIPER_INCOMPLETE"
        setup_state = "SETUP_READY"
        reasons.append(
            "SETUP_READY — waiting independent confirmation or M1/M5 trigger"
        )
    reasons.append(f"WAIT — incomplete sniper pillars {missing}")
    diagnostics["confluence_class"] = _confluence_class(
        take=False, independent=independent, setup_state=setup_state or "WAIT"
    )
    return _wait(primary, setup_state=setup_state)
