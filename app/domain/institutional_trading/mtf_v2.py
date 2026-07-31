"""AI Decision Engine v2 — regime-aware MTF alignment.

Preserves institutional quality floors. Does not lower confidence/quality
thresholds. Removes structural false negatives where H4 RANGE acted as a
permanent veto despite lower-TF agreement.

Policies
--------
Trending (H4 UP/DOWN):
  Require H4 + H1 + M15 directional agreement. M5 is confirmation bonus.

Ranging (H4 RANGE/UNKNOWN):
  H4 is context only (never a veto). Require H1 structure + M15 agreement
  + M5 entry confirmation (all same direction).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.domain.market_structure.enums import TrendDirection

MarketRegimeMTF = Literal["trending", "ranging"]
MtfPolicyId = Literal["v2_trending", "v2_ranging"]

# Contribution weights for telemetry / score composition (sum = 100).
_TRENDING_WEIGHTS = {
    "h4": 40,
    "h1": 30,
    "m15": 20,
    "m5": 10,
}
_RANGING_WEIGHTS = {
    "h4": 0,  # context only — never blocks
    "h1": 40,
    "m15": 35,
    "m5": 25,
}


def classify_mtf_regime(macro_h4: TrendDirection) -> MarketRegimeMTF:
    """H4 directional → trending; H4 range/unknown → ranging."""
    if macro_h4 in {TrendDirection.UP, TrendDirection.DOWN}:
        return "trending"
    return "ranging"


def _contrib(direction: TrendDirection, bias: TrendDirection, weight: int) -> int:
    if bias not in {TrendDirection.UP, TrendDirection.DOWN}:
        return 0
    if direction == bias:
        return weight
    if direction in {TrendDirection.RANGE, TrendDirection.UNKNOWN}:
        return weight // 4
    return 0


@dataclass(frozen=True, slots=True)
class MtfV2Assessment:
    """Regime-aware MTF result for TrendEngine + telemetry."""

    regime: MarketRegimeMTF
    policy: MtfPolicyId
    bias: TrendDirection
    alignment_score: int
    aligned: bool
    contributions: dict[str, int] = field(default_factory=dict)
    why: str = ""
    h4_is_context: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "policy": self.policy,
            "bias": self.bias.value,
            "alignment_score": self.alignment_score,
            "aligned": self.aligned,
            "contributions": dict(self.contributions),
            "why": self.why,
            "h4_is_context": self.h4_is_context,
        }


def evaluate_mtf_v2(
    *,
    h4: TrendDirection,
    h1: TrendDirection,
    m15: TrendDirection,
    m5: TrendDirection,
    scalping: bool = False,
) -> MtfV2Assessment:
    """Evaluate MTF under AI Decision Engine v2 regime policy.

    Score floors for ``aligned`` match prior institutional bars:
    scalping ≥55, swing ≥70. Quality/confidence gates are untouched.
    """
    regime = classify_mtf_regime(h4)
    min_score = 55 if scalping else 70

    if regime == "trending":
        bias = h4
        weights = _TRENDING_WEIGHTS
        contributions = {
            "h4": _contrib(h4, bias, weights["h4"]),
            "h1": _contrib(h1, bias, weights["h1"]),
            "m15": _contrib(m15, bias, weights["m15"]),
            "m5": _contrib(m5, bias, weights["m5"]),
        }
        score = sum(contributions.values())
        # Conflict: H4 vs H1 opposite still penalised in trending regimes.
        if (
            h4 in {TrendDirection.UP, TrendDirection.DOWN}
            and h1 in {TrendDirection.UP, TrendDirection.DOWN}
            and h4 != h1
        ):
            score = max(0, score - 25)
            contributions = dict(contributions)
            contributions["conflict_penalty"] = -25

        aligned = (
            bias in {TrendDirection.UP, TrendDirection.DOWN}
            and h4 == h1 == m15
            and h4 in {TrendDirection.UP, TrendDirection.DOWN}
            and score >= min_score
        )
        why = (
            f"MTF v2 trending: H4={h4.value} H1={h1.value} M15={m15.value} "
            f"M5={m5.value} score={score}"
            + (" aligned" if aligned else " not aligned")
            + (" [scalping]" if scalping else "")
        )
        return MtfV2Assessment(
            regime="trending",
            policy="v2_trending",
            bias=bias,
            alignment_score=int(score),
            aligned=aligned,
            contributions=contributions,
            why=why,
            h4_is_context=False,
        )

    # --- Ranging: H4 is context only ---
    bias = h1 if h1 in {TrendDirection.UP, TrendDirection.DOWN} else TrendDirection.UNKNOWN
    weights = _RANGING_WEIGHTS
    contributions = {
        "h4": 0,  # context — never contributes to veto/score gate
        "h1": _contrib(h1, bias, weights["h1"]) if bias != TrendDirection.UNKNOWN else 0,
        "m15": _contrib(m15, bias, weights["m15"]) if bias != TrendDirection.UNKNOWN else 0,
        "m5": _contrib(m5, bias, weights["m5"]) if bias != TrendDirection.UNKNOWN else 0,
        "h4_context": h4.value,
    }
    score = int(contributions["h1"]) + int(contributions["m15"]) + int(contributions["m5"])

    # Require H1 structure + M15 agreement + M5 entry confirmation (same direction).
    lower_tf_lock = (
        bias in {TrendDirection.UP, TrendDirection.DOWN}
        and h1 == bias
        and m15 == bias
        and m5 == bias
    )
    aligned = lower_tf_lock and score >= min_score

    why = (
        f"MTF v2 ranging (H4={h4.value} context): H1={h1.value} M15={m15.value} "
        f"M5={m5.value} score={score}"
        + (" aligned" if aligned else " not aligned")
        + (" [scalping]" if scalping else "")
    )
    return MtfV2Assessment(
        regime="ranging",
        policy="v2_ranging",
        bias=bias,
        alignment_score=int(score),
        aligned=aligned,
        contributions={k: v for k, v in contributions.items() if k != "h4_context"},
        why=why,
        h4_is_context=True,
    )


def evaluate_mtf_v1_legacy(
    *,
    h4: TrendDirection,
    h1: TrendDirection,
    m15: TrendDirection,
    m5: TrendDirection,
    scalping: bool = False,
) -> MtfV2Assessment:
    """Reproduce pre-v2 confluence MTF gate for counterfactual replay.

    Critical legacy false-negative: scalping confluence keyed direction on raw
    H4 ``macro_bias``, so H4 RANGE always hard-rejected ``mtf_not_aligned``
    even when H1 provided a remapped bias in TrendEngine.
    """
    role_dirs = {
        "macro_bias": h4,
        "primary_structure": h1,
        "entry_confirmation": m15,
        "execution_management": m5,
    }
    weights = {
        "macro_bias": 40,
        "primary_structure": 30,
        "entry_confirmation": 20,
        "execution_management": 10,
    }
    bias = h4
    if bias in {TrendDirection.UNKNOWN, TrendDirection.RANGE}:
        bias = h1

    score = 0
    contributions: dict[str, int] = {}
    if bias in {TrendDirection.UP, TrendDirection.DOWN}:
        for role, direction in role_dirs.items():
            w = weights[role]
            if direction == bias:
                c = w
            elif direction in {TrendDirection.RANGE, TrendDirection.UNKNOWN}:
                c = w // 4
            else:
                c = 0
            contributions[role] = c
            score += c

    if (
        h4 in {TrendDirection.UP, TrendDirection.DOWN}
        and h1 in {TrendDirection.UP, TrendDirection.DOWN}
        and h4 != h1
    ):
        score = max(0, score - 25)

    if scalping:
        # Confluence MTF gate (pre-v2): pass only when H4 itself is directional.
        confluence_mtf_pass = h4 in {TrendDirection.UP, TrendDirection.DOWN}
    else:
        confluence_mtf_pass = (
            h4 in {TrendDirection.UP, TrendDirection.DOWN} and h4 == h1
        )

    regime = classify_mtf_regime(h4)
    return MtfV2Assessment(
        regime=regime,
        policy="v2_trending" if regime == "trending" else "v2_ranging",
        bias=bias if bias in {TrendDirection.UP, TrendDirection.DOWN} else TrendDirection.UNKNOWN,
        alignment_score=int(score),
        aligned=bool(confluence_mtf_pass),
        contributions=contributions,
        why=(
            f"MTF v1 legacy confluence gate: H4={h4.value} H1={h1.value} "
            f"M15={m15.value} M5={m5.value} score={score}"
            + (" pass" if confluence_mtf_pass else " mtf_not_aligned")
        ),
        h4_is_context=False,
    )
