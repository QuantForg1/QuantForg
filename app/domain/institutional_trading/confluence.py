"""Canonical ConfluenceEngine — institutional final judge before risk.

Score Pipeline Integration (ite-v2.2.0):
  - M15 semantics contribute when H1+M15 lock holds (m15 not permanently zero)
  - Structural facts scored in Quality are not re-penalized here (dedup)
  - Liquidity v2 remains the liquidity context source
  - Weights unchanged; thresholds unchanged (min_confluence_score)

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
from app.domain.institutional_trading.liquidity_v2 import evaluate_liquidity_v2
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_structure.enums import StructureBreakKind, TrendDirection
from app.domain.order_block.enums import OrderBlockState

# Classifications that mean M15 agrees with structural bias after semantics.
_M15_ALIGNED_LABELS = {
    "TREND_CONTINUATION",
    "PULLBACK_WITHIN_TREND",
    "CONSOLIDATION",
}


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


def _quality_factor_score(quality: object, code: str) -> int | None:
    for factor in getattr(quality, "factors", ()) or ():
        if getattr(factor, "code", None) == code:
            try:
                return int(getattr(factor, "score", 0) or 0)
            except (TypeError, ValueError):
                return None
    return None


def _dedup_passthrough(
    *,
    quality_score: int | None,
    observed: int,
    present: bool,
    min_quality_bar: int,
) -> tuple[int, bool]:
    """Avoid a second independent penalty for a fact already scored in Quality.

    When Quality already graded the fact at/above ``min_quality_bar``, confidence
    reuses that Quality score (single source — no re-scoring, no inflation to 100).
    Otherwise use the confluence observation score.
    """
    if present and quality_score is not None and quality_score >= min_quality_bar:
        return int(quality_score), True
    if present and quality_score is None:
        return observed, False
    return observed, False


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
        dedup_notes: list[str] = []

        trend = snapshot.trend
        quality = snapshot.trade_quality
        session = snapshot.session
        news = snapshot.news
        structure = snapshot.primary_structure
        sem = getattr(trend, "m15_semantics", None) or {}

        # --- Direction from MTF v2 (regime-aware) ---
        # Trending: H4+H1+M15 lock. Ranging: H4 context; H1+M15 lock.
        # M5 is execution timing only — never redefines H1 direction.
        direction = TradeDirection.NONE
        bias = trend.effective_bias
        if trend.aligned and bias in {TrendDirection.UP, TrendDirection.DOWN}:
            direction = _dir_to_trade(bias)
            factors["mtf"] = trend.alignment_score
            regime = getattr(trend, "market_regime", "unknown")
            reasons.append(
                f"MTF v2 {regime}: aligned bias={bias.value} "
                f"(H4={trend.macro_bias.value}"
                f"{' context' if getattr(trend, 'h4_is_context', False) else ''} "
                f"H1={trend.primary.value} M15={trend.entry.value} "
                f"M5={trend.execution.value} score={trend.alignment_score})"
            )
        elif (
            cfg.is_scalping()
            and bias in {TrendDirection.UP, TrendDirection.DOWN}
            and trend.alignment_score >= 40
        ):
            # Soft structure path — directional bias without full lock.
            direction = _dir_to_trade(bias)
            factors["mtf"] = max(40, trend.alignment_score)
            reasons.append(
                f"MTF v2 soft bias={bias.value} "
                f"(score={trend.alignment_score}; awaiting full lock)"
            )
        else:
            rejected.append("mtf_not_aligned")
            factors["mtf"] = max(0, trend.alignment_score // 2)
            reasons.append(trend.why or "MTF v2 not aligned")

        # --- M15 / entry confirmation (semantics-aware) ---
        # After successful H1+M15 lock, M15 must contribute positively — not stay 0.
        entry_key = cfg.entry_confirmation_tf.value.lower()
        entry_confirms = (
            direction is TradeDirection.BUY and trend.entry is TrendDirection.UP
        ) or (direction is TradeDirection.SELL and trend.entry is TrendDirection.DOWN)
        sem_label = str(sem.get("new_classification") or "")
        sem_effective = str(sem.get("effective_direction") or "").lower()
        sem_supports = (
            sem_label in _M15_ALIGNED_LABELS
            and bias in {TrendDirection.UP, TrendDirection.DOWN}
            and sem_effective == bias.value
        )

        if trend.aligned and entry_confirms:
            factors[entry_key] = 100
            factors["m15"] = 100
            reasons.append(
                f"{cfg.entry_confirmation_tf.value} confirms {bias.value} "
                f"(H1+M15 lock"
                + (f"; M15 semantics={sem_label}" if sem_label else "")
                + ")"
            )
        elif trend.aligned and sem_supports:
            # Lock held via semantics rewrite — credit M15 explicitly
            factors[entry_key] = 100
            factors["m15"] = 100
            reasons.append(
                f"M15 semantics {sem_label} contributes to H1+M15 lock "
                f"(effective={sem_effective})"
            )
        elif entry_confirms and direction is not TradeDirection.NONE:
            factors[entry_key] = 100
            factors["m15"] = 100
            reasons.append(f"{cfg.entry_confirmation_tf.value} confirms {bias.value}")
        elif direction is not TradeDirection.NONE and sem_supports:
            factors[entry_key] = 100
            factors["m15"] = 100
            reasons.append(
                f"M15 semantics {sem_label} soft-path contribution "
                f"(effective={sem_effective})"
            )
        elif direction is not TradeDirection.NONE:
            factors[entry_key] = 40
            factors["m15"] = 40
            rejected.append("entry_tf_not_confirming")
        else:
            factors[entry_key] = 0
            factors["m15"] = 0

        # Execution TF — timing soft score only; never a directional veto.
        exec_key = cfg.execution_management_tf.value.lower()
        if exec_key != entry_key:
            if direction is not TradeDirection.NONE and trend.execution == bias:
                factors[exec_key] = 100
                if exec_key == "m5" or "m5" not in factors:
                    factors["m5"] = 100
                reasons.append(
                    f"{cfg.execution_management_tf.value} timing confirms "
                    f"{bias.value} (execution only)"
                )
            elif direction is not TradeDirection.NONE:
                factors[exec_key] = 50
                if exec_key == "m5" or "m5" not in factors:
                    factors["m5"] = 50
                reasons.append(
                    f"{cfg.execution_management_tf.value} timing soft — "
                    "does not redefine H1+M15 lock"
                )
            else:
                factors.setdefault(exec_key, 0)

        # Structure events — scored in Quality (market_structure); dedup here
        bos = len(structure.breaks_of_structure) if structure else 0
        choch = len(structure.changes_of_character) if structure else 0
        struct_present = bool(structure and (bos or choch))
        struct_observed = 90 if (bos and choch) else (75 if struct_present else 25)
        q_struct = _quality_factor_score(quality, "market_structure")
        factors["structure"], struct_deduped = _dedup_passthrough(
            quality_score=q_struct,
            observed=struct_observed,
            present=struct_present,
            min_quality_bar=70,
        )
        if struct_present:
            reasons.append(
                f"{cfg.primary_structure_tf.value} structure events "
                f"bos={bos} choch={choch}"
            )
            if structure and structure.breaks_of_structure:
                last = structure.breaks_of_structure[-1]
                if last.kind is StructureBreakKind.BOS:
                    reasons.append(f"Latest BOS trend={last.trend_direction.value}")
            if struct_deduped:
                dedup_notes.append("structure")
        else:
            rejected.append("no_structure_event")

        # Liquidity v2 — context reject flag kept; score deduped vs Quality
        liq_v2 = evaluate_liquidity_v2(snapshot)
        q_liq = _quality_factor_score(quality, "liquidity")
        factors["liquidity"], liq_deduped = _dedup_passthrough(
            quality_score=q_liq,
            observed=liq_v2.score,
            present=liq_v2.has_context,
            min_quality_bar=65,
        )
        reasons.extend(liq_v2.reasons)
        if liq_v2.rejected:
            rejected.append("no_liquidity_context")
        elif liq_v2.sources:
            reasons.append("Liquidity v2 sources=" + ",".join(liq_v2.sources))
        if liq_deduped:
            dedup_notes.append("liquidity")

        # Order blocks — zone quality lives in Quality; dedup here
        ob = snapshot.order_blocks
        active_ob = 0
        if ob:
            active_ob = sum(
                1
                for b in ob.order_blocks
                if b.state in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
            )
        ob_observed = 85 if active_ob else 20
        q_ob = _quality_factor_score(quality, "order_block")
        factors["order_block"], ob_deduped = _dedup_passthrough(
            quality_score=q_ob,
            observed=ob_observed,
            present=bool(active_ob),
            min_quality_bar=70,
        )
        if active_ob:
            reasons.append(f"Active order blocks={active_ob}")
            if ob_deduped:
                dedup_notes.append("order_block")
        else:
            rejected.append("no_active_order_block")

        # FVG — zone quality lives in Quality; dedup here
        fvg = snapshot.fair_value_gaps
        open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
        fvg_observed = 80 if open_fvg else 25
        q_fvg = _quality_factor_score(quality, "fair_value_gap")
        factors["fvg"], fvg_deduped = _dedup_passthrough(
            quality_score=q_fvg,
            observed=fvg_observed,
            present=bool(open_fvg),
            min_quality_bar=70,
        )
        if open_fvg:
            reasons.append(f"Open FVGs={open_fvg}")
            if fvg_deduped:
                dedup_notes.append("fvg")
        else:
            rejected.append("no_open_fvg")

        # Quality gate — when passed, do not re-drag confidence with component deficits
        if quality.passed:
            factors["quality"] = 100
            reasons.append(
                f"Trade quality {quality.total} ({quality.band}) — "
                "confidence quality slot passthrough (dedup)"
            )
        else:
            factors["quality"] = quality.total
            rejected.append("quality_below_threshold")
            reasons.append(f"Trade quality {quality.total} below gate")

        if dedup_notes:
            reasons.append(
                "Score dedup (fact counted in Quality once): " + ",".join(dedup_notes)
            )

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

        # Spread — soft score when elevated; hard reject only above ceiling
        spread = snapshot.spread
        if spread is None:
            factors["spread"] = 50
            reasons.append("Spread unavailable — neutral")
        elif spread > cfg.max_spread_reject:
            factors["spread"] = 0
            rejected.append("spread_too_wide")
            reasons.append(f"Spread {spread} exceeds reject {cfg.max_spread_reject}")
        elif spread <= cfg.max_spread_for_full_score:
            factors["spread"] = 100
            reasons.append(f"Spread {spread} tight")
        else:
            span = cfg.max_spread_reject - cfg.max_spread_for_full_score
            factors["spread"] = int(
                max(
                    0.0,
                    float(100 * (1 - (spread - cfg.max_spread_for_full_score) / span)),
                )
            )
            reasons.append(
                f"Spread {spread} elevated — soft score {factors['spread']} "
                f"(reject only above {cfg.max_spread_reject})"
            )

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

        # Weighted confidence — weights preserved (sum 100), no inflation
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
