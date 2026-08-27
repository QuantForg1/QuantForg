"""Balanced BUY/SELL direction from institutional structure — never BUY-only."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_structure.enums import TrendDirection

# Scalping: H1 is context only. M15 is structure. M5/M1 are timing.
_H1_CONTEXT = 10
_M15_STRUCTURE = 14
_M5_ENTRY = 12
_M1_EXECUTION = 10
_SCALP_STRUCTURE_TFS = ("M1", "M5", "M15")
_COMPONENT_KEYS = (
    "structure",
    "bos",
    "choch",
    "liquidity",
    "fvg",
    "ob",
    "momentum",
    "displacement",
    "rejection",
    "retest",
    "session",
    "rr",
)


def _empty_components() -> dict[str, int]:
    return {key: 0 for key in _COMPONENT_KEYS}


def _seq(obj: Any, name: str) -> list[Any]:
    raw = getattr(obj, name, None) if obj is not None else None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def iter_scalp_structure_entries(
    snapshot: MarketAnalysisSnapshot,
) -> list[tuple[str, Any]]:
    """(timeframe, structure) for M1/M5/M15. H1 is context and is omitted."""
    seen: set[int] = set()
    out: list[tuple[str, Any]] = []
    smap = getattr(snapshot, "structure_by_tf", None)
    wanted = set(_SCALP_STRUCTURE_TFS)
    if isinstance(smap, dict):
        for key, struct in smap.items():
            token = str(getattr(key, "value", key) or "").strip().upper()
            if token not in wanted or struct is None:
                continue
            ident = id(struct)
            if ident in seen:
                continue
            seen.add(ident)
            out.append((token, struct))
        for token in _SCALP_STRUCTURE_TFS:
            struct = smap.get(token)
            if struct is None:
                continue
            ident = id(struct)
            if ident in seen:
                continue
            seen.add(ident)
            out.append((token, struct))
    primary = getattr(snapshot, "primary_structure", None)
    if primary is not None and id(primary) not in seen:
        out.append(("M15", primary))
    return out


def iter_scalp_structures(snapshot: MarketAnalysisSnapshot) -> list[Any]:
    """M1/M5/M15 structure snapshots. H1 is context and is not required."""
    return [struct for _, struct in iter_scalp_structure_entries(snapshot)]


def structure_tfs_for_side(
    snapshot: MarketAnalysisSnapshot,
    side: TradeDirection,
) -> set[str]:
    """Timeframes that have a BOS/CHOCH aligned to ``side``. Discovery only."""
    if side not in {TradeDirection.BUY, TradeDirection.SELL}:
        return set()
    out: set[str] = set()
    for tf, structure in iter_scalp_structure_entries(snapshot):
        events = _seq(structure, "breaks_of_structure")[-3:]
        events.extend(_seq(structure, "changes_of_character")[-2:])
        for event in events:
            if structure_event_side(event) is side:
                out.add(tf)
                break
    return out


def _trend_matches(value: Any, expected: TrendDirection) -> bool:
    if value == expected:
        return True
    token = str(getattr(value, "value", value) or "").strip().upper()
    if not token or token.startswith("<") or "MAGICMOCK" in token:
        return False
    if expected is TrendDirection.UP:
        return token in {"UP", "BULLISH"}
    if expected is TrendDirection.DOWN:
        return token in {"DOWN", "BEARISH"}
    return False


@dataclass(frozen=True, slots=True)
class DirectionDecision:
    direction: TradeDirection
    buy_score: int
    sell_score: int
    reasons: tuple[str, ...]
    structure_score: int
    factors: dict[str, int]
    buy_components: dict[str, int] = field(default_factory=_empty_components)
    sell_components: dict[str, int] = field(default_factory=_empty_components)
    directional_edge: int = 0
    edge_margin: int = 5
    ltf_buy_score: int = 0
    ltf_sell_score: int = 0
    htf_context_buy: int = 0
    htf_context_sell: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "reasons": list(self.reasons),
            "structure_score": self.structure_score,
            "factors": dict(self.factors),
            "buy_components": dict(self.buy_components),
            "sell_components": dict(self.sell_components),
            "directional_edge": self.directional_edge,
            "edge_margin": self.edge_margin,
            "ltf_buy_score": self.ltf_buy_score,
            "ltf_sell_score": self.ltf_sell_score,
            "htf_context_buy": self.htf_context_buy,
            "htf_context_sell": self.htf_context_sell,
            "bullish_score": self.buy_score,
            "bearish_score": self.sell_score,
            "never_prefer_buy_only": True,
        }


def _usable_dir_token(value: Any) -> str:
    """Extract a real direction token; skip MagicMock / empty placeholders."""
    nested = getattr(value, "value", value)
    text = str(nested or "").strip().upper()
    if not text or text.startswith("<") or "MAGICMOCK" in text:
        return ""
    return text


def map_structure_side(value: Any) -> TradeDirection | None:
    """Map UP/DOWN/BULLISH/BEARISH tokens to BUY/SELL."""
    raw = _usable_dir_token(value)
    if raw in {"UP", "BULLISH", "BUY", "LONG"}:
        return TradeDirection.BUY
    if raw in {"DOWN", "BEARISH", "SELL", "SHORT"}:
        return TradeDirection.SELL
    return None


def _side_of_break(_kind: Any, break_dir: Any) -> TradeDirection | None:
    """Map BOS/CHOCH break direction to trade side."""
    return map_structure_side(break_dir)


def structure_event_side(event: Any) -> TradeDirection | None:
    """Read production BOS/CHOCH fields (trend_direction / previous_trend).

    ``BreakOfStructure.trend_direction`` is the continuation side.
    ``ChangeOfCharacter.previous_trend`` is the trend that was broken, so the
    new character is the opposite side. Fixture mocks that only set
    ``direction`` / ``bias`` still map.
    """
    if event is None:
        return None
    kind = _usable_dir_token(getattr(event, "kind", None))
    prev = map_structure_side(getattr(event, "previous_trend", None))
    if kind == "CHOCH" and prev is not None:
        if prev is TradeDirection.BUY:
            return TradeDirection.SELL
        if prev is TradeDirection.SELL:
            return TradeDirection.BUY
    for name in ("trend_direction", "direction", "bias", "side"):
        mapped = map_structure_side(getattr(event, name, None))
        if mapped is not None:
            return mapped
    if prev is not None and kind != "BOS":
        if prev is TradeDirection.BUY:
            return TradeDirection.SELL
        if prev is TradeDirection.SELL:
            return TradeDirection.BUY
    return None


def decide_scalping_direction(
    snapshot: MarketAnalysisSnapshot,
    *,
    config: AiScalpingConfig | None = None,
) -> DirectionDecision:
    """Independent BUY and SELL scores every cycle. Never inherit prior direction.

    Scalping hierarchy: H1 = macro context, M15 = structure, M5/M1 = timing.
    H1 must not veto a valid M5/M1 scalp by overweighting.
    Tie → NONE (reject). Never defaults to BUY.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    assert cfg.never_prefer_buy_only is True
    reasons: list[str] = []
    buy = 0
    sell = 0
    factors: dict[str, int] = {}
    buy_c = _empty_components()
    sell_c = _empty_components()
    core_buy = 0
    core_sell = 0
    htf_buy = 0
    htf_sell = 0
    buy_core_ev = False
    sell_core_ev = False

    def _add(
        side: TradeDirection,
        points: int,
        component: str,
        reason: str,
        *,
        core: bool = False,
        htf: bool = False,
    ) -> None:
        nonlocal buy, sell, core_buy, core_sell, htf_buy, htf_sell
        nonlocal buy_core_ev, sell_core_ev
        if points <= 0:
            return
        if side is TradeDirection.BUY:
            buy += points
            buy_c[component] = int(buy_c.get(component, 0)) + points
            if core:
                core_buy += points
                buy_core_ev = True
            if htf:
                htf_buy += points
        elif side is TradeDirection.SELL:
            sell += points
            sell_c[component] = int(sell_c.get(component, 0)) + points
            if core:
                core_sell += points
                sell_core_ev = True
            if htf:
                htf_sell += points
        reasons.append(reason)

    trend = snapshot.trend
    # H1 is display/context only — never used for the scalping edge test.
    if _trend_matches(trend.macro_bias, TrendDirection.UP):
        _add(
            TradeDirection.BUY,
            _H1_CONTEXT,
            "structure",
            f"{cfg.direction_tf.value} context UP",
            htf=True,
        )
        factors["h1_bias"] = _H1_CONTEXT
    elif _trend_matches(trend.macro_bias, TrendDirection.DOWN):
        _add(
            TradeDirection.SELL,
            _H1_CONTEXT,
            "structure",
            f"{cfg.direction_tf.value} context DOWN",
            htf=True,
        )
        factors["h1_bias"] = _H1_CONTEXT
    else:
        factors["h1_bias"] = 0
        reasons.append(f"No clear {cfg.direction_tf.value} bias")

    # M15 is higher-timeframe context. It can inform score but cannot veto M1/M5.
    if _trend_matches(trend.primary, TrendDirection.UP):
        _add(
            TradeDirection.BUY,
            _M15_STRUCTURE,
            "structure",
            "M15 structure UP",
            core=False,
        )
        factors["m15_structure"] = _M15_STRUCTURE
    elif _trend_matches(trend.primary, TrendDirection.DOWN):
        _add(
            TradeDirection.SELL,
            _M15_STRUCTURE,
            "structure",
            "M15 structure DOWN",
            core=False,
        )
        factors["m15_structure"] = _M15_STRUCTURE
    else:
        factors["m15_structure"] = 0

    m5_up = _trend_matches(getattr(trend, "entry", None), TrendDirection.UP)
    m5_down = _trend_matches(getattr(trend, "entry", None), TrendDirection.DOWN)
    m1_up = _trend_matches(getattr(trend, "execution", None), TrendDirection.UP)
    m1_down = _trend_matches(getattr(trend, "execution", None), TrendDirection.DOWN)
    if m5_up:
        factors["m5_entry"] = _M5_ENTRY
    elif m5_down:
        factors["m5_entry"] = _M5_ENTRY
    else:
        factors["m5_entry"] = 0
    if m1_up:
        factors["m1_execution"] = _M1_EXECUTION
    elif m1_down:
        factors["m1_execution"] = _M1_EXECUTION
    else:
        factors["m1_execution"] = 0

    buy_m1m5_struct = m5_up or m1_up
    sell_m1m5_struct = m5_down or m1_down
    buy_m15_struct = False
    sell_m15_struct = False
    bos_n = 0
    choch_n = 0
    for tf, structure in iter_scalp_structure_entries(snapshot):
        bos_events = _seq(structure, "breaks_of_structure")
        choch_events = _seq(structure, "changes_of_character")
        bos_n += len(bos_events)
        choch_n += len(choch_events)
        for br in bos_events[-3:]:
            side = structure_event_side(br)
            if side is TradeDirection.BUY:
                if tf in {"M1", "M5"}:
                    buy_m1m5_struct = True
                else:
                    buy_m15_struct = True
            elif side is TradeDirection.SELL:
                if tf in {"M1", "M5"}:
                    sell_m1m5_struct = True
                else:
                    sell_m15_struct = True
        for ch in choch_events[-2:]:
            side = structure_event_side(ch)
            if side is TradeDirection.BUY:
                if tf in {"M1", "M5"}:
                    buy_m1m5_struct = True
                else:
                    buy_m15_struct = True
            elif side is TradeDirection.SELL:
                if tf in {"M1", "M5"}:
                    sell_m1m5_struct = True
                else:
                    sell_m15_struct = True
    # One STRUCTURE family credit per side — M5 BOS + M1 BOS is not two families.
    # M15 BOS/CHOCH is still a real structure event (core), not H1 context.
    if buy_m1m5_struct:
        _add(TradeDirection.BUY, 16, "bos", "M1/M5 BOS/CHOCH supports BUY", core=True)
        if m5_up:
            reasons.append("M5 entry UP")
        if m1_up:
            reasons.append("M1 execution UP")
    elif buy_m15_struct:
        _add(
            TradeDirection.BUY,
            8,
            "bos",
            "M15 BOS/CHOCH supports BUY",
            core=True,
        )
    elif m5_up or m1_up:
        _add(
            TradeDirection.BUY,
            10,
            "structure",
            "M5/M1 trend supports BUY",
            core=True,
        )
    if sell_m1m5_struct:
        _add(TradeDirection.SELL, 16, "bos", "M1/M5 BOS/CHOCH supports SELL", core=True)
        if m5_down:
            reasons.append("M5 entry DOWN")
        if m1_down:
            reasons.append("M1 execution DOWN")
    elif sell_m15_struct:
        _add(
            TradeDirection.SELL,
            8,
            "bos",
            "M15 BOS/CHOCH supports SELL",
            core=True,
        )
    elif m5_down or m1_down:
        _add(
            TradeDirection.SELL,
            10,
            "structure",
            "M5/M1 trend supports SELL",
            core=True,
        )
    factors["bos"] = 85 if bos_n else 20
    factors["choch"] = 80 if choch_n else 20

    # Liquidity sweeps — typically fade into opposite / continue with bias
    liq = snapshot.liquidity
    raw_sweeps = getattr(liq, "sweeps", None) if liq else None
    sweeps = list(raw_sweeps) if isinstance(raw_sweeps, (list, tuple)) else []
    factors["liquidity_sweep"] = min(20, len(sweeps) * 8)
    for sw in sweeps[-2:]:
        kind_raw = str(
            getattr(getattr(sw, "kind", None), "value", getattr(sw, "kind", "")) or ""
        ).upper()
        side_raw = str(
            getattr(getattr(sw, "side", None), "value", getattr(sw, "side", "")) or ""
        ).upper()
        token = f"{kind_raw} {side_raw}"
        # Sweep of lows → often BUY; sweep of highs → often SELL
        if any(t in token for t in ("LOW", "BID", "BUY", "BULL")):
            _add(
                TradeDirection.BUY,
                12,
                "liquidity",
                "Liquidity sweep of lows → BUY bias",
                core=True,
            )
        elif any(t in token for t in ("HIGH", "ASK", "SELL", "BEAR")):
            _add(
                TradeDirection.SELL,
                12,
                "liquidity",
                "Liquidity sweep of highs → SELL bias",
                core=True,
            )

    eq_highs = getattr(liq, "equal_highs", None) if liq else None
    eq_lows = getattr(liq, "equal_lows", None) if liq else None
    if isinstance(eq_highs, (list, tuple)) and eq_highs:
        _add(
            TradeDirection.SELL,
            8,
            "liquidity",
            "Equal highs — bearish liquidity",
            core=True,
        )
        factors["equal_highs"] = 8
    if isinstance(eq_lows, (list, tuple)) and eq_lows:
        _add(
            TradeDirection.BUY,
            8,
            "liquidity",
            "Equal lows — bullish liquidity",
            core=True,
        )
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
            bias = _usable_dir_token(
                getattr(b, "side", None)
                or getattr(b, "bias", None)
                or getattr(b, "direction", None)
            )
            if "BUY" in bias or "BULL" in bias:
                _add(TradeDirection.BUY, 8, "ob", "Active bullish order block", core=True)
            elif "SELL" in bias or "BEAR" in bias:
                _add(
                    TradeDirection.SELL, 8, "ob", "Active bearish order block", core=True
                )
            quality = getattr(b, "quality", None)
            ratio = getattr(quality, "displacement_ratio", None) if quality else None
            try:
                disp = Decimal(str(getattr(ratio, "value", ratio)))
            except (TypeError, ValueError, ArithmeticError):
                disp = Decimal("0")
            if ratio is not None and disp >= Decimal("1.5"):
                if "BUY" in bias or "BULL" in bias:
                    _add(
                        TradeDirection.BUY,
                        4,
                        "displacement",
                        "Bullish displacement",
                        core=True,
                    )
                elif "SELL" in bias or "BEAR" in bias:
                    _add(
                        TradeDirection.SELL,
                        4,
                        "displacement",
                        "Bearish displacement",
                        core=True,
                    )
    factors["order_block"] = 8 if buy != sell else 0

    # FVG
    fvg = snapshot.fair_value_gaps
    raw_gaps = getattr(fvg, "active_gaps", None) if fvg else None
    gaps = list(raw_gaps) if isinstance(raw_gaps, (list, tuple)) else []
    buy_fvg = False
    sell_fvg = False
    for g in gaps[:3]:
        gap_side = map_structure_side(
            getattr(g, "side", None)
            or getattr(g, "bias", None)
            or getattr(g, "direction", None)
        )
        if gap_side is TradeDirection.BUY and not buy_fvg:
            _add(TradeDirection.BUY, 8, "fvg", "Bullish FVG", core=True)
            buy_fvg = True
        elif gap_side is TradeDirection.SELL and not sell_fvg:
            _add(TradeDirection.SELL, 8, "fvg", "Bearish FVG", core=True)
            sell_fvg = True
    factors["fvg"] = 80 if gaps else 25

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
            _add(TradeDirection.BUY, 8, "momentum", "Momentum confirms BUY side")
        elif sell > buy:
            _add(TradeDirection.SELL, 8, "momentum", "Momentum confirms SELL side")
        else:
            reasons.append("Momentum present but sides tied")
    factors["momentum"] = mom

    # Session — no directional preference, only quality
    reasons.append("Session scored separately (no BUY preference)")
    buy_c["session"] = 0
    sell_c["session"] = 0

    buy = max(0, min(100, buy))
    sell = max(0, min(100, sell))
    core_buy = max(0, min(100, core_buy))
    core_sell = max(0, min(100, core_sell))
    structure_score = max(
        85 if bos_n else 0,
        80 if choch_n else 0,
        factors.get("m15_structure", 0)
        + factors.get("m5_entry", 0)
        + factors.get("m1_execution", 0),
        int(trend.alignment_score),
    )
    structure_score = max(0, min(100, structure_score))

    edge = max(1, int(getattr(cfg, "direction_edge_margin", 5) or 5))
    ltf_edge = abs(core_buy - core_sell)
    # Direction from M1/M5/liquidity/zone evidence. H1 is excluded from this test
    # so a valid scalp is not vetoed by a neutral or opposite macro bias.
    both_core = buy_core_ev and sell_core_ev
    if buy_core_ev and core_buy > core_sell + edge:
        direction = TradeDirection.BUY
        reasons.append(
            f"LTF edge BUY ({core_buy} vs SELL {core_sell}, margin={edge}; "
            f"H1 context {htf_buy}/{htf_sell} excluded from edge)"
        )
    elif sell_core_ev and core_sell > core_buy + edge:
        direction = TradeDirection.SELL
        reasons.append(
            f"LTF edge SELL ({core_sell} vs BUY {core_buy}, margin={edge}; "
            f"H1 context {htf_buy}/{htf_sell} excluded from edge)"
        )
    elif both_core and ltf_edge <= edge:
        direction = TradeDirection.NONE
        reasons.append(
            f"CONFLICT — BUY LTF {core_buy} ≈ SELL LTF {core_sell} (margin={edge})"
        )
    else:
        direction = TradeDirection.NONE
        reasons.append(
            f"No M1/M5 directional edge — BUY {buy} ≈ SELL {sell} "
            f"(LTF {core_buy}/{core_sell})"
        )

    return DirectionDecision(
        direction=direction,
        buy_score=buy,
        sell_score=sell,
        reasons=tuple(reasons),
        structure_score=structure_score,
        factors=factors,
        buy_components=buy_c,
        sell_components=sell_c,
        directional_edge=ltf_edge,
        edge_margin=edge,
        ltf_buy_score=core_buy,
        ltf_sell_score=core_sell,
        htf_context_buy=htf_buy,
        htf_context_sell=htf_sell,
    )
