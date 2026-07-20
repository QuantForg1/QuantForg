"""Canonical ConfluenceEngine — institutional final judge before risk.

Deterministic. No randomness. No OMS. No AI.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    TradeDirection,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_structure.enums import StructureBreakKind, TrendDirection
from app.domain.order_block.enums import OrderBlockState


def _band(score: int, *, min_pass: int, high: int) -> str:
    if score < min_pass:
        return "reject"
    if score >= high:
        return "high_confidence"
    return "tradable"


def _dir_to_trade(d: TrendDirection) -> TradeDirection:
    if d is TrendDirection.UP:
        return TradeDirection.BUY
    if d is TrendDirection.DOWN:
        return TradeDirection.SELL
    return TradeDirection.NONE


@dataclass(frozen=True, slots=True)
class ConfluenceEngine:
    """Combine Phase A snapshot factors into a single confidence + direction."""

    config: ITEConfig

    def evaluate(
        self,
        snapshot: MarketAnalysisSnapshot,
        *,
        atr: Decimal | None = None,
        current_drawdown_pct: Decimal | None = None,
    ) -> ConfluenceResult:
        cfg = self.config
        reasons: list[str] = []
        rejected: list[str] = []
        factors: dict[str, int] = {}

        trend = snapshot.trend
        quality = snapshot.trade_quality
        session = snapshot.session
        news = snapshot.news
        structure = snapshot.primary_structure

        # --- Direction from hierarchy (H4 macro must agree with H1) ---
        direction = TradeDirection.NONE
        if (
            trend.macro_bias in {TrendDirection.UP, TrendDirection.DOWN}
            and trend.macro_bias == trend.primary
        ):
            direction = _dir_to_trade(trend.macro_bias)
            reasons.append(
                f"H4/H1 aligned {trend.macro_bias.value} "
                f"(M15={trend.entry.value} M5={trend.execution.value})"
            )
            factors["mtf"] = trend.alignment_score
        else:
            rejected.append("mtf_not_aligned")
            factors["mtf"] = max(0, trend.alignment_score // 2)
            reasons.append(trend.why or "MTF not aligned")

        # M15 confirmation soft bonus / penalty
        if direction is TradeDirection.BUY and trend.entry is TrendDirection.UP:
            factors["m15"] = 100
            reasons.append("M15 confirms bullish")
        elif direction is TradeDirection.SELL and trend.entry is TrendDirection.DOWN:
            factors["m15"] = 100
            reasons.append("M15 confirms bearish")
        elif direction is not TradeDirection.NONE:
            factors["m15"] = 40
            rejected.append("m15_not_confirming")
        else:
            factors["m15"] = 0

        # Structure events on H1
        bos = len(structure.breaks_of_structure) if structure else 0
        choch = len(structure.changes_of_character) if structure else 0
        if structure and (bos or choch):
            factors["structure"] = 90 if (bos and choch) else 75
            reasons.append(f"H1 structure events bos={bos} choch={choch}")
            # Directional structure bias
            if structure.breaks_of_structure:
                last = structure.breaks_of_structure[-1]
                if last.kind is StructureBreakKind.BOS:
                    reasons.append(f"Latest BOS trend={last.trend_direction.value}")
        else:
            factors["structure"] = 25
            rejected.append("no_structure_event")

        # Liquidity
        liq = snapshot.liquidity
        if liq and (liq.sweeps or liq.pools or liq.equal_highs or liq.equal_lows):
            sweep_n = len(liq.sweeps)
            factors["liquidity"] = 85 if sweep_n else 65
            reasons.append(f"Liquidity present sweeps={sweep_n} pools={len(liq.pools)}")
        else:
            factors["liquidity"] = 20
            rejected.append("no_liquidity_context")

        # Order blocks
        ob = snapshot.order_blocks
        active_ob = 0
        if ob:
            active_ob = sum(
                1
                for b in ob.order_blocks
                if b.state in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
            )
        if active_ob:
            factors["order_block"] = 85
            reasons.append(f"Active order blocks={active_ob}")
        else:
            factors["order_block"] = 20
            rejected.append("no_active_order_block")

        # FVG
        fvg = snapshot.fair_value_gaps
        open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
        if open_fvg:
            factors["fvg"] = 80
            reasons.append(f"Open FVGs={open_fvg}")
        else:
            factors["fvg"] = 25
            rejected.append("no_open_fvg")

        # Trade quality (already composite)
        factors["quality"] = quality.total
        if quality.passed:
            reasons.append(f"Trade quality {quality.total} ({quality.band})")
        else:
            rejected.append("quality_below_threshold")
            reasons.append(f"Trade quality {quality.total} below gate")

        # Session
        if session.allowed:
            factors["session"] = 100
            reasons.append(session.reason)
        else:
            factors["session"] = 0
            rejected.append("session_blocked")
            reasons.append(session.reason)

        # News
        if news.blocked:
            factors["news"] = 0
            rejected.append("news_blackout")
            reasons.append(news.reason)
        else:
            factors["news"] = 100
            reasons.append(news.reason)

        # Spread
        spread = snapshot.spread
        if spread is None:
            factors["spread"] = 50
            reasons.append("Spread unavailable — neutral")
        elif spread <= cfg.max_spread_for_full_score:
            factors["spread"] = 100
            reasons.append(f"Spread {spread} tight")
        elif spread > cfg.max_spread_reject:
            factors["spread"] = 0
            rejected.append("spread_too_wide")
            reasons.append(f"Spread {spread} exceeds reject {cfg.max_spread_reject}")
        else:
            span = cfg.max_spread_reject - cfg.max_spread_for_full_score
            factors["spread"] = int(
                max(
                    0.0,
                    float(100 * (1 - (spread - cfg.max_spread_for_full_score) / span)),
                )
            )
            reasons.append(f"Spread {spread} elevated")

        # ATR volatility (optional)
        if atr is not None and atr > 0:
            mid = None
            if structure and structure.swings:
                mid = structure.swings[-1].price.value
            if mid and mid > 0:
                atr_pct = (atr / mid) * Decimal("100")
                if atr_pct > Decimal("3"):
                    factors["volatility"] = 30
                    rejected.append("atr_elevated")
                    reasons.append(f"ATR {atr_pct:.2f}% of price elevated")
                elif atr_pct < Decimal("0.05"):
                    factors["volatility"] = 40
                    rejected.append("atr_too_low")
                    reasons.append(f"ATR {atr_pct:.2f}% of price too low")
                else:
                    factors["volatility"] = 80
                    reasons.append(f"ATR {atr_pct:.2f}% of price acceptable")
            else:
                factors["volatility"] = 60
        else:
            factors["volatility"] = 60

        # Current drawdown soft penalty
        if current_drawdown_pct is not None and current_drawdown_pct > 0:
            if current_drawdown_pct >= cfg.max_weekly_drawdown_pct:
                factors["drawdown"] = 0
                rejected.append("drawdown_elevated")
                reasons.append(f"Drawdown {current_drawdown_pct}% elevated")
            elif current_drawdown_pct >= cfg.max_daily_loss_pct:
                factors["drawdown"] = 40
                reasons.append(f"Drawdown {current_drawdown_pct}% caution")
            else:
                factors["drawdown"] = 90
        else:
            factors["drawdown"] = 80

        # Hard rejects force NONE
        hard = {
            "session_blocked",
            "news_blackout",
            "spread_too_wide",
            "mtf_not_aligned",
            "quality_below_threshold",
        }
        if hard & set(rejected):
            direction = TradeDirection.NONE

        # Weighted confidence
        weights = {
            "mtf": 22,
            "m15": 8,
            "structure": 12,
            "liquidity": 10,
            "order_block": 12,
            "fvg": 10,
            "quality": 12,
            "session": 6,
            "news": 4,
            "spread": 2,
            "volatility": 1,
            "drawdown": 1,
        }
        weighted = 0
        total_w = 0
        for k, w in weights.items():
            weighted += factors.get(k, 0) * w
            total_w += w
        confidence = round(weighted / total_w) if total_w else 0
        confidence = max(0, min(100, confidence))

        # Require SMC pair: OB or FVG (prefer both)
        if "no_active_order_block" in rejected and "no_open_fvg" in rejected:
            confidence = min(confidence, 55)
            rejected.append("no_smc_zone")
            direction = TradeDirection.NONE

        if confidence < cfg.min_confluence_score:
            direction = TradeDirection.NONE
            rejected.append("confidence_below_threshold")

        passed = (
            confidence >= cfg.min_confluence_score
            and direction is not TradeDirection.NONE
            and "session_blocked" not in rejected
            and "news_blackout" not in rejected
            and "spread_too_wide" not in rejected
            and quality.passed
        )

        payload = (
            f"{snapshot.input_hash}|{confidence}|{direction.value}|"
            f"{','.join(sorted(rejected))}|{atr}|{current_drawdown_pct}"
        )
        input_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

        return ConfluenceResult(
            confidence=confidence,
            direction=direction,
            reasons=tuple(reasons),
            rejected_rules=tuple(dict.fromkeys(rejected)),
            input_hash=input_hash,
            band=_band(
                confidence,
                min_pass=cfg.min_confluence_score,
                high=cfg.high_confidence_score,
            ),
            passed=passed,
            factors=factors,
        )
