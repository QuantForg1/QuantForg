"""Trade Decision Engine — decides only; never sends orders / never OMS."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    EligibilityResult,
    PriceZone,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_structure.enums import TrendDirection
from app.domain.order_block.enums import OrderBlockState


def _zone(low: Decimal, high: Decimal) -> PriceZone:
    if low > high:
        low, high = high, low
    mid = (low + high) / Decimal("2")
    return PriceZone(low=low, high=high, mid=mid)


@dataclass(frozen=True, slots=True)
class TradeDecisionEngine:
    """Map confluence + risk + eligibility → NO_TRADE | WATCH | BUY | SELL."""

    config: ITEConfig

    def decide(
        self,
        *,
        snapshot: MarketAnalysisSnapshot,
        confluence: ConfluenceResult,
        eligibility: EligibilityResult,
        account: AccountRiskState,
        risk_score: int,
        risk_reasons: tuple[str, ...] = (),
        approved_lots: Decimal | None = None,
    ) -> TradeDecision:
        cfg = self.config
        quality = snapshot.trade_quality.total
        confidence = confluence.confidence

        entry_zone, stop_zone, target_zone, rr, invalidations = self._geometry(
            snapshot, confluence.direction, account
        )

        reasons: list[str] = list(confluence.reasons)
        if risk_reasons:
            reasons.extend(risk_reasons)
        if not eligibility.eligible:
            reasons.extend(eligibility.rejection_reasons)

        # Decision ladder (institutional — no OMS call here)
        action = DecisionAction.NO_TRADE
        direction = TradeDirection.NONE

        hard_fail = (
            not eligibility.eligible
            or confluence.direction is TradeDirection.NONE
            or confidence < cfg.min_confluence_score
            or quality < cfg.min_trade_quality_score
        )

        if hard_fail:
            action = DecisionAction.NO_TRADE
            if not eligibility.eligible:
                reasons.append("Eligibility failed — NO_TRADE")
            elif confluence.direction is TradeDirection.NONE:
                reasons.append("No directional confluence — NO_TRADE")
            else:
                reasons.append(
                    "Below institutional confidence/quality gates — NO_TRADE"
                )
            # Near-miss watch band (70-79) with direction hint
            if (
                eligibility.checks.get("session_valid", False)
                and not snapshot.news.blocked
                and confluence.direction is not TradeDirection.NONE
                and 70 <= confidence < cfg.min_confluence_score
            ):
                action = DecisionAction.WATCH
                direction = confluence.direction
                reasons.append("WATCH — setup forming below confluence gate")
        else:
            action = (
                DecisionAction.BUY
                if confluence.direction is TradeDirection.BUY
                else DecisionAction.SELL
            )
            direction = confluence.direction
            label = (
                "High-confidence"
                if confidence >= cfg.high_confidence_score
                else "Tradable"
            )
            reasons.append(
                f"{label} {direction.value} "
                f"(confidence={confidence} quality={quality})"
            )

        expected = self._duration(confidence, account.atr)

        digest = hashlib.sha256(
            (
                f"{snapshot.input_hash}|{confluence.input_hash}|"
                f"{action.value}|{confidence}|{quality}|{risk_score}|"
                f"{eligibility.eligible}"
            ).encode()
        ).hexdigest()[:32]

        return TradeDecision(
            action=action,
            direction=direction,
            confidence=confidence,
            quality=quality,
            risk_score=risk_score,
            reasons=tuple(dict.fromkeys(reasons)),
            invalidations=tuple(invalidations),
            entry_zone=entry_zone,
            stop_zone=stop_zone,
            target_zone=target_zone,
            estimated_rr=rr,
            expected_duration=expected,
            confluence=confluence,
            eligibility=eligibility,
            input_hash=digest,
            config_version=cfg.config_version,
            symbol=snapshot.symbol,
            as_of=snapshot.as_of,
            approved_lots=approved_lots,
            risk_reasons=risk_reasons,
        )

    def _geometry(
        self,
        snapshot: MarketAnalysisSnapshot,
        direction: TradeDirection,
        account: AccountRiskState,
    ) -> tuple[
        PriceZone | None,
        PriceZone | None,
        PriceZone | None,
        Decimal | None,
        list[str],
    ]:
        invalidations: list[str] = []
        mid = account.mid_price
        atr = account.atr or Decimal("0")

        # Prefer active OB as entry zone
        entry: PriceZone | None = None
        ob = snapshot.order_blocks
        if ob:
            for block in ob.order_blocks:
                if block.state not in {
                    OrderBlockState.ACTIVE,
                    OrderBlockState.VALIDATED,
                }:
                    continue
                top = block.zone.high_price.value
                bottom = block.zone.low_price.value
                if top > 0 and bottom > 0:
                    entry = _zone(bottom, top)
                    break

        # FVG fallback
        if entry is None and snapshot.fair_value_gaps:
            gaps = list(getattr(snapshot.fair_value_gaps, "active_gaps", ()) or ())
            if gaps:
                g = gaps[0]
                zone = g.zone
                top = zone.high_price.value
                bottom = zone.low_price.value
                if top > 0 and bottom > 0:
                    entry = _zone(bottom, top)

        if entry is None and mid is not None and mid > 0:
            pad = atr if atr > 0 else mid * Decimal("0.0005")
            entry = _zone(mid - pad, mid + pad)

        if entry is None:
            return None, None, None, None, ["Insufficient data for entry geometry"]

        # Stop beyond structure swing / ATR
        stop_dist = atr * Decimal("1.5") if atr > 0 else (entry.high - entry.low)
        if stop_dist <= 0:
            stop_dist = entry.mid or entry.low
            stop_dist = stop_dist * Decimal("0.001") if stop_dist else Decimal("1")

        if direction is TradeDirection.BUY:
            stop = _zone(entry.low - stop_dist, entry.low - stop_dist * Decimal("0.5"))
            target = _zone(
                entry.high + stop_dist * Decimal("2"),
                entry.high + stop_dist * Decimal("2.5"),
            )
            invalidations.append("Close below bullish invalidation / stop zone")
            if snapshot.trend.macro_bias is TrendDirection.DOWN:
                invalidations.append("H4 flips bearish")
        elif direction is TradeDirection.SELL:
            stop = _zone(
                entry.high + stop_dist * Decimal("0.5"), entry.high + stop_dist
            )
            target = _zone(
                entry.low - stop_dist * Decimal("2.5"),
                entry.low - stop_dist * Decimal("2"),
            )
            invalidations.append("Close above bearish invalidation / stop zone")
            if snapshot.trend.macro_bias is TrendDirection.UP:
                invalidations.append("H4 flips bullish")
        else:
            return entry, None, None, None, invalidations

        risk = abs((entry.mid or entry.low) - (stop.mid or stop.low))
        reward = abs((target.mid or target.high) - (entry.mid or entry.high))
        rr = (reward / risk).quantize(Decimal("0.01")) if risk > 0 else None
        return entry, stop, target, rr, invalidations

    @staticmethod
    def _duration(confidence: int, atr: Decimal | None) -> str:
        if confidence >= 90:
            return "M15-H1 (high confidence, faster management)"
        if atr is not None and atr > 0:
            return "H1-H4 (standard swing hold)"
        return "H1-H4"
