"""Trade Quality Score (0-100) — reject below configured threshold."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import (
    SessionFilterResult,
    TradeQualityFactor,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot
from app.domain.order_block.enums import OrderBlockState
from app.domain.order_block.models import OrderBlockSnapshot

# Equal weights sum to 100
_WEIGHTS = {
    "trend": 20,
    "liquidity": 15,
    "order_block": 15,
    "fair_value_gap": 15,
    "market_structure": 15,
    "session": 10,
    "spread": 10,
}


def _band(total: int, *, min_pass: int, high: int) -> str:
    if total < min_pass:
        return "reject"
    if total >= high:
        return "high_confidence"
    return "tradable"


@dataclass(frozen=True, slots=True)
class TradeQualityEvaluator:
    """Deterministic quality score from analysis factors."""

    config: ITEConfig

    def evaluate(
        self,
        *,
        trend: TrendSnapshot,
        structure: StructureSnapshot | None,
        liquidity: LiquiditySnapshot | None,
        order_blocks: OrderBlockSnapshot | None,
        fvgs: FairValueGapSnapshot | None,
        session: SessionFilterResult,
        spread: Decimal | None,
    ) -> TradeQualityScore:
        factors = (
            self._trend(trend),
            self._liquidity(liquidity),
            self._order_blocks(order_blocks),
            self._fvgs(fvgs),
            self._structure(structure),
            self._session(session),
            self._spread(spread),
        )
        # Weighted average of component scores
        weighted = 0
        total_w = 0
        for f in factors:
            weighted += f.score * f.weight
            total_w += f.weight
        total = round(weighted / total_w) if total_w else 0
        total = max(0, min(100, total))
        passed = total >= self.config.min_trade_quality_score
        return TradeQualityScore(
            total=total,
            passed=passed,
            band=_band(
                total,
                min_pass=self.config.min_trade_quality_score,
                high=self.config.high_confidence_score,
            ),
            factors=factors,
        )

    def _trend(self, trend: TrendSnapshot) -> TradeQualityFactor:
        score = trend.alignment_score
        if trend.aligned:
            score = max(score, 75)
        detail = trend.why
        return TradeQualityFactor(
            code="trend", weight=_WEIGHTS["trend"], score=score, detail=detail
        )

    def _liquidity(self, snap: LiquiditySnapshot | None) -> TradeQualityFactor:
        if snap is None:
            return TradeQualityFactor(
                code="liquidity",
                weight=_WEIGHTS["liquidity"],
                score=0,
                detail="No liquidity snapshot",
            )
        sweeps = len(getattr(snap, "sweeps", ()) or ())
        pools = len(getattr(snap, "pools", ()) or ())
        eqh = len(getattr(snap, "equal_highs", ()) or ())
        eql = len(getattr(snap, "equal_lows", ()) or ())
        score = 40
        if sweeps:
            score += 30
        if pools or eqh or eql:
            score += 20
        if sweeps and (pools or eqh or eql):
            score = min(100, score + 10)
        return TradeQualityFactor(
            code="liquidity",
            weight=_WEIGHTS["liquidity"],
            score=min(100, score),
            detail=f"sweeps={sweeps} pools={pools} eqh={eqh} eql={eql}",
        )

    def _order_blocks(self, snap: OrderBlockSnapshot | None) -> TradeQualityFactor:
        if snap is None:
            return TradeQualityFactor(
                code="order_block",
                weight=_WEIGHTS["order_block"],
                score=0,
                detail="No order-block snapshot",
            )
        blocks = list(getattr(snap, "order_blocks", ()) or ())
        active = [
            b
            for b in blocks
            if getattr(b, "state", None)
            in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
            or str(getattr(b, "state", "")).lower() in {"active", "validated"}
        ]
        breakers = list(getattr(snap, "breakers", ()) or ())
        score = 20
        if active:
            score = 75
        if breakers:
            score = max(score, 55)
        if active and breakers:
            score = 85
        return TradeQualityFactor(
            code="order_block",
            weight=_WEIGHTS["order_block"],
            score=min(100, score),
            detail=f"active={len(active)} total={len(blocks)} breakers={len(breakers)}",
        )

    def _fvgs(self, snap: FairValueGapSnapshot | None) -> TradeQualityFactor:
        if snap is None:
            return TradeQualityFactor(
                code="fair_value_gap",
                weight=_WEIGHTS["fair_value_gap"],
                score=0,
                detail="No FVG snapshot",
            )
        gaps = list(getattr(snap, "gaps", ()) or ())
        open_gaps = list(getattr(snap, "active_gaps", None) or ())
        if not open_gaps and gaps:
            open_gaps = [
                g
                for g in gaps
                if str(
                    getattr(getattr(g, "state", None), "value", getattr(g, "state", ""))
                ).lower()
                not in {"mitigated", "invalidated", "expired", "filled"}
            ]
        score = 25 if gaps else 0
        if open_gaps:
            score = 70
        if len(open_gaps) >= 2:
            score = 85
        return TradeQualityFactor(
            code="fair_value_gap",
            weight=_WEIGHTS["fair_value_gap"],
            score=min(100, score),
            detail=f"open={len(open_gaps)} total={len(gaps)}",
        )

    def _structure(self, snap: StructureSnapshot | None) -> TradeQualityFactor:
        if snap is None:
            return TradeQualityFactor(
                code="market_structure",
                weight=_WEIGHTS["market_structure"],
                score=0,
                detail="No primary structure",
            )
        bos = len(snap.breaks_of_structure or ())
        choch = len(snap.changes_of_character or ())
        swings = len(snap.swings or ())
        direction = snap.trend.direction if snap.trend else TrendDirection.UNKNOWN
        score = 30
        if swings >= 4:
            score += 15
        if bos:
            score += 25
        if choch:
            score += 20
        if direction in {TrendDirection.UP, TrendDirection.DOWN}:
            score += 10
        return TradeQualityFactor(
            code="market_structure",
            weight=_WEIGHTS["market_structure"],
            score=min(100, score),
            detail=f"bos={bos} choch={choch} swings={swings} trend={direction.value}",
        )

    def _session(self, session: SessionFilterResult) -> TradeQualityFactor:
        score = 100 if session.allowed else 15
        return TradeQualityFactor(
            code="session",
            weight=_WEIGHTS["session"],
            score=score,
            detail=session.reason,
        )

    def _spread(self, spread: Decimal | None) -> TradeQualityFactor:
        if spread is None:
            return TradeQualityFactor(
                code="spread",
                weight=_WEIGHTS["spread"],
                score=50,
                detail="Spread unavailable — neutral score",
            )
        tight = self.config.max_spread_for_full_score
        reject = self.config.max_spread_reject
        if spread <= tight:
            score = 100
        elif spread >= reject:
            score = 0
        else:
            # Linear decay between tight and reject
            span = reject - tight
            score = int(max(0.0, float(100 * (1 - (spread - tight) / span))))
        return TradeQualityFactor(
            code="spread",
            weight=_WEIGHTS["spread"],
            score=score,
            detail=f"spread={spread}",
        )
