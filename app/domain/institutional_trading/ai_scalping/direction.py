"""Balanced BUY/SELL direction from institutional structure — never BUY-only."""

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
from app.domain.market_structure.enums import StructureBreakKind, TrendDirection


@dataclass(frozen=True, slots=True)
class DirectionDecision:
    direction: TradeDirection
    buy_score: int
    sell_score: int
    reasons: tuple[str, ...]
    structure_score: int
    factors: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "reasons": list(self.reasons),
            "structure_score": self.structure_score,
            "factors": dict(self.factors),
            "bullish_score": self.buy_score,
            "bearish_score": self.sell_score,
            "never_prefer_buy_only": True,
        }


def _side_of_break(_kind: Any, break_dir: Any) -> TradeDirection | None:
    """Map BOS/CHOCH break direction to trade side."""
    raw = str(getattr(break_dir, "value", break_dir) or "").upper()
    if raw in {"UP", "BULLISH", "BUY", "LONG"}:
        return TradeDirection.BUY
    if raw in {"DOWN", "BEARISH", "SELL", "SHORT"}:
        return TradeDirection.SELL
    return None


def decide_scalping_direction(
    snapshot: MarketAnalysisSnapshot,
    *,
    config: AiScalpingConfig | None = None,
) -> DirectionDecision:
    """Highest-probability BUY or SELL from H1 bias + M15 structure events.

    Never defaults to BUY. Tie → NONE (reject).
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    assert cfg.never_prefer_buy_only is True
    reasons: list[str] = []
    buy = 0
    sell = 0
    factors: dict[str, int] = {}

    trend = snapshot.trend
    # H1 / macro bias
    if trend.macro_bias is TrendDirection.UP:
        buy += 28
        factors["h1_bias"] = 28
        reasons.append(f"{cfg.direction_tf.value} bias UP")
    elif trend.macro_bias is TrendDirection.DOWN:
        sell += 28
        factors["h1_bias"] = 28
        reasons.append(f"{cfg.direction_tf.value} bias DOWN")
    else:
        factors["h1_bias"] = 0
        reasons.append(f"No clear {cfg.direction_tf.value} bias")

    # M15 alignment
    if trend.primary is TrendDirection.UP:
        buy += 14
        factors["m15_structure"] = 14
    elif trend.primary is TrendDirection.DOWN:
        sell += 14
        factors["m15_structure"] = 14
    else:
        factors["m15_structure"] = 0

    structure = snapshot.primary_structure
    bos_n = len(structure.breaks_of_structure) if structure else 0
    choch_n = len(structure.changes_of_character) if structure else 0
    factors["bos"] = min(20, bos_n * 10)
    factors["choch"] = min(18, choch_n * 9)

    if structure:
        for br in list(structure.breaks_of_structure)[-3:]:
            side = _side_of_break(
                getattr(br, "kind", StructureBreakKind.BOS),
                getattr(br, "direction", None) or getattr(br, "bias", None),
            )
            if side is TradeDirection.BUY:
                buy += 12
                reasons.append("BOS supports BUY")
            elif side is TradeDirection.SELL:
                sell += 12
                reasons.append("BOS supports SELL")
        for ch in list(structure.changes_of_character)[-2:]:
            side = _side_of_break(
                StructureBreakKind.CHOCH,
                getattr(ch, "direction", None) or getattr(ch, "bias", None),
            )
            if side is TradeDirection.BUY:
                buy += 10
                reasons.append("CHOCH supports BUY")
            elif side is TradeDirection.SELL:
                sell += 10
                reasons.append("CHOCH supports SELL")

    # Liquidity sweeps — typically fade into opposite / continue with bias
    liq = snapshot.liquidity
    raw_sweeps = getattr(liq, "sweeps", None) if liq else None
    sweeps = list(raw_sweeps) if isinstance(raw_sweeps, (list, tuple)) else []
    factors["liquidity_sweep"] = min(20, len(sweeps) * 8)
    for sw in sweeps[-2:]:
        side_raw = str(
            getattr(getattr(sw, "side", None), "value", getattr(sw, "side", "")) or ""
        ).upper()
        # Sweep of lows → often BUY; sweep of highs → often SELL
        if any(t in side_raw for t in ("LOW", "BID", "BUY", "BULL")):
            buy += 10
            reasons.append("Liquidity sweep of lows → BUY bias")
        elif any(t in side_raw for t in ("HIGH", "ASK", "SELL", "BEAR")):
            sell += 10
            reasons.append("Liquidity sweep of highs → SELL bias")

    eq_highs = getattr(liq, "equal_highs", None) if liq else None
    eq_lows = getattr(liq, "equal_lows", None) if liq else None
    if isinstance(eq_highs, (list, tuple)) and eq_highs:
        sell += 8
        reasons.append("Equal highs — bearish liquidity")
        factors["equal_highs"] = 8
    if isinstance(eq_lows, (list, tuple)) and eq_lows:
        buy += 8
        reasons.append("Equal lows — bullish liquidity")
        factors["equal_lows"] = 8

    # Order blocks
    ob = snapshot.order_blocks
    raw_obs = getattr(ob, "order_blocks", None) if ob else None
    obs = list(raw_obs) if isinstance(raw_obs, (list, tuple)) else []
    if obs:
        for b in obs[:5]:
            state = str(getattr(getattr(b, "state", None), "value", b.state)).lower()
            if state not in {"active", "validated"}:
                continue
            bias = str(
                getattr(getattr(b, "bias", None), "value", getattr(b, "side", "")) or ""
            ).upper()
            if "BUY" in bias or "BULL" in bias:
                buy += 8
                reasons.append("Active bullish order block")
            elif "SELL" in bias or "BEAR" in bias:
                sell += 8
                reasons.append("Active bearish order block")
            quality = getattr(b, "quality", None)
            ratio = getattr(quality, "displacement_ratio", None) if quality else None
            try:
                disp = Decimal(str(getattr(ratio, "value", ratio)))
            except (TypeError, ValueError, ArithmeticError):
                disp = Decimal("0")
            if ratio is not None and disp >= Decimal("1.5"):
                if "BUY" in bias or "BULL" in bias:
                    buy += 4
                    reasons.append("Bullish displacement")
                elif "SELL" in bias or "BEAR" in bias:
                    sell += 4
                    reasons.append("Bearish displacement")
    factors["order_block"] = 8 if buy != sell else 0

    # FVG
    fvg = snapshot.fair_value_gaps
    raw_gaps = getattr(fvg, "active_gaps", None) if fvg else None
    gaps = list(raw_gaps) if isinstance(raw_gaps, (list, tuple)) else []
    for g in gaps[:3]:
        bias = str(
            getattr(getattr(g, "bias", None), "value", getattr(g, "direction", ""))
            or ""
        ).upper()
        if "UP" in bias or "BULL" in bias or "BUY" in bias:
            buy += 6
            reasons.append("Bullish FVG")
        elif "DOWN" in bias or "BEAR" in bias or "SELL" in bias:
            sell += 6
            reasons.append("Bearish FVG")
    factors["fvg"] = min(18, len(gaps) * 6)

    # Momentum / volume from quality components (real factors, not missing attr)
    from app.domain.institutional_trading.quality_components import (
        quality_components,
    )

    q_components = quality_components(snapshot.trade_quality)
    mom = int(
        q_components.get("momentum")
        or q_components.get("trend_strength")
        or getattr(snapshot.trend, "alignment_score", 0)
        or 0
    )
    mom_floor = int(cfg.min_momentum_score)
    if mom >= mom_floor:
        if buy > sell:
            buy += 8
            reasons.append("Momentum confirms BUY side")
        elif sell > buy:
            sell += 8
            reasons.append("Momentum confirms SELL side")
        else:
            reasons.append("Momentum present but sides tied")
    factors["momentum"] = mom

    # Session — no directional preference, only quality
    reasons.append("Session scored separately (no BUY preference)")

    buy = max(0, min(100, buy))
    sell = max(0, min(100, sell))
    structure_score = max(
        factors.get("bos", 0)
        + factors.get("choch", 0)
        + factors.get("m15_structure", 0),
        int(trend.alignment_score),
    )
    structure_score = max(0, min(100, structure_score))

    edge = max(1, int(getattr(cfg, "direction_edge_margin", 5) or 5))
    if buy > sell + edge:
        direction = TradeDirection.BUY
        reasons.append(f"Highest probability BUY ({buy} vs SELL {sell})")
    elif sell > buy + edge:
        direction = TradeDirection.SELL
        reasons.append(f"Highest probability SELL ({sell} vs BUY {buy})")
    else:
        direction = TradeDirection.NONE
        reasons.append(f"No edge — BUY {buy} ≈ SELL {sell} (reject)")

    return DirectionDecision(
        direction=direction,
        buy_score=buy,
        sell_score=sell,
        reasons=tuple(reasons),
        structure_score=structure_score,
        factors=factors,
    )
