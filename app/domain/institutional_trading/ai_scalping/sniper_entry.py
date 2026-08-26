"""XAUUSD sniper entry contract — uses existing snapshot facts only.

Not a second strategy, OMS, or scoring engine. Conflicting or incomplete
evidence returns WAIT. Never flips BUY into SELL or SELL into BUY.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


def _seq(obj: Any, name: str) -> list[Any]:
    raw = getattr(obj, name, None) if obj is not None else None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _upper(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _dec(value: Any) -> Decimal | None:
    try:
        if value is None:
            return None
        nested = getattr(value, "value", value)
        d = Decimal(str(nested))
        return d if d.is_finite() else None
    except (TypeError, ValueError, ArithmeticError):
        return None


def _side_of_break(break_dir: Any) -> TradeDirection | None:
    raw = _upper(break_dir)
    if raw in {"UP", "BULLISH", "BUY", "LONG"}:
        return TradeDirection.BUY
    if raw in {"DOWN", "BEARISH", "SELL", "SHORT"}:
        return TradeDirection.SELL
    return None


def _sweep_side(sweep: Any) -> TradeDirection | None:
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


@dataclass(frozen=True, slots=True)
class SniperEntryDecision:
    passed: bool
    action: str  # BUY | SELL | WAIT
    reasons: tuple[str, ...]
    pillars: dict[str, bool]
    primary_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "action": self.action,
            "reasons": list(self.reasons),
            "pillars": dict(self.pillars),
            "primary_reason": self.primary_reason,
            "never_prefer_buy_only": True,
            "never_flips_direction": True,
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
) -> SniperEntryDecision:
    """Require a high-quality XAUUSD trigger — trend alone is not enough."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
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
    }

    side = direction.direction
    if side not in {TradeDirection.BUY, TradeDirection.SELL}:
        reasons.append(
            f"WAIT — no directional edge "
            f"(bullish={direction.buy_score} bearish={direction.sell_score})"
        )
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason="WAIT_NO_DIRECTIONAL_EDGE",
        )
    pillars["clear_direction"] = True

    setup_raw = str(setup_family_direction or "").strip().upper()
    if setup_raw in {"BUY", "SELL"} and setup_raw != side.value:
        pillars["not_conflicting"] = False
        reasons.append(
            f"WAIT — conflicting evidence setup={setup_raw} vs AI={side.value}"
        )
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason="WAIT_CONFLICTING_BUY_SELL",
        )

    if spread_reject:
        reasons.append("WAIT — abnormal spread")
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason="WAIT_ABNORMAL_SPREAD",
        )

    structure = snapshot.primary_structure
    for br in _seq(structure, "breaks_of_structure")[-3:]:
        mapped = _side_of_break(
            getattr(br, "direction", None) or getattr(br, "bias", None)
        )
        if mapped is side:
            pillars["structure_confirmation"] = True
            reasons.append(f"BOS confirms {side.value}")
            break
    if not pillars["structure_confirmation"]:
        for ch in _seq(structure, "changes_of_character")[-2:]:
            mapped = _side_of_break(
                getattr(ch, "direction", None) or getattr(ch, "bias", None)
            )
            if mapped is side:
                pillars["structure_confirmation"] = True
                reasons.append(f"CHOCH confirms {side.value}")
                break

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

    zone_highs: list[Decimal] = []
    zone_lows: list[Decimal] = []
    displacement_ok = False
    ob_snap = snapshot.order_blocks
    for block in _seq(ob_snap, "order_blocks")[:8]:
        state = _upper(getattr(block, "state", None))
        if state and state not in {"ACTIVE", "VALIDATED", ""}:
            continue
        mapped = _bias_side(block)
        if mapped is not side:
            continue
        pillars["entry_zone"] = True
        quality = getattr(block, "quality", None)
        ratio = _dec(getattr(quality, "displacement_ratio", None) if quality else None)
        if ratio is not None and ratio >= Decimal("1.5"):
            displacement_ok = True
            reasons.append("Displacement-qualified order block")
        zone = getattr(block, "zone", None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        if hi is not None:
            zone_highs.append(hi)
        if lo is not None:
            zone_lows.append(lo)

    fvg_snap = snapshot.fair_value_gaps
    for gap in _seq(fvg_snap, "active_gaps")[:6]:
        mapped = _bias_side(gap)
        if mapped is not side:
            continue
        pillars["entry_zone"] = True
        zone = getattr(gap, "zone", None)
        hi = _dec(getattr(zone, "high_price", None) if zone else None)
        lo = _dec(getattr(zone, "low_price", None) if zone else None)
        if hi is not None:
            zone_highs.append(hi)
        if lo is not None:
            zone_lows.append(lo)
        reasons.append(f"Aligned FVG zone for {side.value}")

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

    if mid is not None and atr is not None and atr > 0 and (zone_highs or zone_lows):
        extension = atr * Decimal("1.5")
        if side is TradeDirection.BUY and zone_highs:
            far = max(zone_highs)
            if mid > far + extension:
                pillars["not_chasing"] = False
                reasons.append("WAIT — chasing BUY after excessive displacement")
        if side is TradeDirection.SELL and zone_lows:
            far = min(zone_lows)
            if mid < far - extension:
                pillars["not_chasing"] = False
                reasons.append("WAIT — chasing SELL after excessive displacement")

    if not pillars["liquidity_event"] and not pillars["structure_confirmation"]:
        reasons.append("WAIT — trend alone is not a sniper trigger")
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason="WAIT_NO_SNIPER_TRIGGER",
        )

    required = (
        pillars["clear_direction"],
        pillars["not_conflicting"],
        pillars["spread_ok"],
        pillars["not_chasing"],
        pillars["invalidation"],
        pillars["risk_reward"],
        pillars["displacement_or_momentum"],
        pillars["liquidity_event"] or pillars["structure_confirmation"],
    )
    if not all(required):
        missing = [k for k, ok in pillars.items() if not ok]
        primary = "WAIT_SNIPER_INCOMPLETE"
        if not pillars["not_chasing"]:
            primary = "WAIT_CHASE"
        elif not pillars["invalidation"]:
            primary = "WAIT_NO_INVALIDATION"
        elif not pillars["risk_reward"]:
            primary = "WAIT_INSUFFICIENT_RR"
        reasons.append(f"WAIT — incomplete sniper pillars {missing}")
        return SniperEntryDecision(
            passed=False,
            action="WAIT",
            reasons=tuple(reasons),
            pillars=pillars,
            primary_reason=primary,
        )

    reasons.append(f"SNIPER {side.value} — liquidity/structure/confirmation aligned")
    return SniperEntryDecision(
        passed=True,
        action=side.value,
        reasons=tuple(reasons),
        pillars=pillars,
        primary_reason=None,
    )
