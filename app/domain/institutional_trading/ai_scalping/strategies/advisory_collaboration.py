"""Advisory collaboration votes from research/plugin/factor intelligence.

These votes PARTICIPATE in SOE analysis (agreement / disagreement).
They NEVER become the OMS-selected strategy by themselves.
They NEVER call order_send.

When OHLC bars are unavailable, votes are derived from existing AI-scalping
score factors (honest ``score_factor_advisory`` source) — never fabricated
market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AdvisorySource = Literal[
    "score_factor_advisory",
    "strategy_engine_plugin",
    "institutional_alpha",
    "m1_micro",
]


@dataclass(frozen=True, slots=True)
class AdvisoryVote:
    strategy_id: str
    name: str
    direction: str  # BUY | SELL | HOLD | NONE
    confidence: int  # 0..100
    reason: str
    source: AdvisorySource
    may_select_for_oms: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "direction": self.direction,
            "confidence": self.confidence,
            "reason": self.reason,
            "source": self.source,
            "may_select_for_oms": False,
            "authorizes_trade": False,
        }


def _i(value: Any, default: int = 0) -> int:
    try:
        return round(float(value))
    except Exception:
        return default


def _factors(score: dict[str, Any]) -> dict[str, Any]:
    raw = score.get("factors")
    return raw if isinstance(raw, dict) else {}


def collect_score_factor_advisory_votes(
    score: dict[str, Any],
) -> tuple[AdvisoryVote, ...]:
    """Map present score evidence onto research-plugin *roles* for collaboration.

    Does not claim the Strategy Engine plugins executed; labels source clearly.
    """
    factors = _factors(score)
    direction = str(score.get("direction") or "NONE").upper()
    regime = str(score.get("market_regime") or score.get("regime") or "").lower()
    momentum = _i(score.get("momentum") or factors.get("momentum"))
    structure = _i(score.get("structure_score") or factors.get("bos"))
    mtf = _i(score.get("mtf_alignment") or factors.get("mtf"))
    liquidity = _i(score.get("liquidity") or factors.get("liquidity_sweep"))
    pa = _i(factors.get("pa_confluence") or factors.get("rsi"))
    vol = _i(factors.get("volatility") or factors.get("atr_expansion") or 50)
    trend_strength = _i(factors.get("trend_strength") or momentum)
    votes: list[AdvisoryVote] = []

    # Trend-following advisory
    if mtf >= 70 and trend_strength >= 65 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="trend_following",
                name="Trend Following (factor advisory)",
                direction=direction,
                confidence=min(100, round(0.5 * mtf + 0.5 * trend_strength)),
                reason=f"MTF {mtf} + trend_strength {trend_strength} align {direction}",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="trend_following",
                name="Trend Following (factor advisory)",
                direction="HOLD",
                confidence=max(0, min(100, mtf)),
                reason="Insufficient MTF/trend alignment for advisory BUY/SELL",
                source="score_factor_advisory",
            )
        )

    # Momentum advisory — withhold when high momentum lacks structure (exhaustion).
    if momentum >= 75 and structure < 45:
        votes.append(
            AdvisoryVote(
                strategy_id="momentum",
                name="Momentum (factor advisory)",
                direction="HOLD",
                confidence=max(0, min(100, momentum)),
                reason=(
                    f"Momentum exhaustion risk: momentum {momentum} with weak "
                    f"structure {structure}"
                ),
                source="score_factor_advisory",
            )
        )
    elif momentum >= 65 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="momentum",
                name="Momentum (factor advisory)",
                direction=direction,
                confidence=min(100, momentum),
                reason=f"Momentum {momentum} supports {direction}",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="momentum",
                name="Momentum (factor advisory)",
                direction="HOLD",
                confidence=momentum,
                reason=f"Momentum {momentum} below advisory threshold",
                source="score_factor_advisory",
            )
        )

    # Breakout advisory — withhold when BOS lacks volatility (false breakout).
    bos = _i(factors.get("bos"))
    if bos >= 70 and vol < 45:
        votes.append(
            AdvisoryVote(
                strategy_id="breakout",
                name="Breakout (factor advisory)",
                direction="HOLD",
                confidence=max(0, bos),
                reason=(
                    f"False-breakout risk: BOS {bos} without volatility "
                    f"confirmation ({vol})"
                ),
                source="score_factor_advisory",
            )
        )
    elif bos >= 70 and vol >= 60 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="breakout",
                name="Breakout (factor advisory)",
                direction=direction,
                confidence=min(100, round(0.55 * bos + 0.45 * vol)),
                reason=f"BOS {bos} with volatility {vol}",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="breakout",
                name="Breakout (factor advisory)",
                direction="HOLD",
                confidence=max(0, bos),
                reason="No clear BOS+volatility expansion advisory",
                source="score_factor_advisory",
            )
        )

    # Mean-reversion / RSI-style advisory (range regimes)
    if regime in {"range", "compression", "ranging"} and liquidity >= 65:
        # Fade: advisory opposite of sweep exhaustion is encoded as HOLD unless
        # choch/reversal family is present — never invent reverse direction.
        setup = str(score.get("setup_family") or "")
        if "reversal" in setup and direction in {"BUY", "SELL"}:
            votes.append(
                AdvisoryVote(
                    strategy_id="mean_reversion",
                    name="Mean Reversion (factor advisory)",
                    direction=direction,
                    confidence=min(100, liquidity),
                    reason=f"Range regime + reversal family {setup}",
                    source="score_factor_advisory",
                )
            )
        else:
            votes.append(
                AdvisoryVote(
                    strategy_id="mean_reversion",
                    name="Mean Reversion (factor advisory)",
                    direction="HOLD",
                    confidence=liquidity,
                    reason="Range regime without confirmed reversal family",
                    source="score_factor_advisory",
                )
            )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="mean_reversion",
                name="Mean Reversion (factor advisory)",
                direction="HOLD",
                confidence=40,
                reason="Not a range/compression advisory context",
                source="score_factor_advisory",
            )
        )

    # RSI / PA advisory (uses pa_confluence / rsi factor when present)
    if pa >= 70 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="rsi",
                name="RSI/PA (factor advisory)",
                direction=direction,
                confidence=min(100, pa),
                reason=f"PA/RSI factor {pa} concurs with {direction}",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="rsi",
                name="RSI/PA (factor advisory)",
                direction="HOLD",
                confidence=pa,
                reason="PA/RSI factor not strong enough for directional vote",
                source="score_factor_advisory",
            )
        )

    # MACD-style advisory from momentum + structure agreement
    if momentum >= 60 and structure >= 60 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="macd",
                name="MACD-style (factor advisory)",
                direction=direction,
                confidence=min(100, round((momentum + structure) / 2)),
                reason="Momentum+structure agreement proxy for MACD role",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="macd",
                name="MACD-style (factor advisory)",
                direction="HOLD",
                confidence=max(0, min(momentum, structure)),
                reason="Momentum/structure not jointly confirmed",
                source="score_factor_advisory",
            )
        )

    # Bollinger / volatility compression-expansion
    if vol >= 70 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="bollinger",
                name="Bollinger/Vol (factor advisory)",
                direction=direction,
                confidence=min(100, vol),
                reason=f"Volatility expansion band evidence {vol}",
                source="score_factor_advisory",
            )
        )
    elif vol <= 35:
        votes.append(
            AdvisoryVote(
                strategy_id="bollinger",
                name="Bollinger/Vol (factor advisory)",
                direction="HOLD",
                confidence=30,
                reason="Compressed volatility — prefer no expansion trade",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="bollinger",
                name="Bollinger/Vol (factor advisory)",
                direction="HOLD",
                confidence=vol,
                reason="Neutral volatility advisory",
                source="score_factor_advisory",
            )
        )

    # MA cross advisory from EMA factor
    ema = _i(factors.get("ema"))
    if ema >= 70 and mtf >= 65 and direction in {"BUY", "SELL"}:
        votes.append(
            AdvisoryVote(
                strategy_id="ma_cross",
                name="MA Cross (factor advisory)",
                direction=direction,
                confidence=min(100, round(0.5 * ema + 0.5 * mtf)),
                reason=f"EMA factor {ema} with MTF {mtf}",
                source="score_factor_advisory",
            )
        )
    else:
        votes.append(
            AdvisoryVote(
                strategy_id="ma_cross",
                name="MA Cross (factor advisory)",
                direction="HOLD",
                confidence=ema,
                reason="EMA/MTF not jointly strong",
                source="score_factor_advisory",
            )
        )

    return tuple(votes)


def summarize_advisory_agreement(
    *,
    live_direction: str,
    votes: tuple[AdvisoryVote, ...] | list[AdvisoryVote],
) -> dict[str, Any]:
    """Summarize how advisory engines relate to the live pack direction."""
    side = str(live_direction or "NONE").upper()
    agree = [
        v
        for v in votes
        if v.direction in {"BUY", "SELL"}
        and v.direction == side
        and side in {"BUY", "SELL"}
    ]
    disagree = [
        v
        for v in votes
        if v.direction in {"BUY", "SELL"}
        and side in {"BUY", "SELL"}
        and v.direction != side
    ]
    hold = [v for v in votes if v.direction not in {"BUY", "SELL"}]
    agree_conf = round(sum(v.confidence for v in agree) / len(agree)) if agree else 0
    return {
        "live_direction": side,
        "advisory_total": len(votes),
        "agree_count": len(agree),
        "disagree_count": len(disagree),
        "hold_count": len(hold),
        "agree_avg_confidence": agree_conf,
        "agree_ids": [v.strategy_id for v in agree],
        "disagree_ids": [v.strategy_id for v in disagree],
        "hold_ids": [v.strategy_id for v in hold],
        "strong_disagreement": len(disagree) >= 2 and len(agree) == 0,
        "supportive": len(agree) >= 2 and len(disagree) == 0,
    }
