"""SOE live intelligence helpers — regime fit, MTF/LTF, session quality.

Used by the Strategy Orchestration Engine to diversify selection across the
five LIVE profiles without hardcoding a preferred strategy, weakening owner
Risk floors, or manufacturing signals.

Evidence basis (Phase 2 broker sample n=13):
  * trend_continuation monoculture under mixed LTF
  * NY session net -$10.25 vs London +$1.77
  * ultra-short losing BUYs (chase / weak LTF)
"""

from __future__ import annotations

from typing import Any

# Sessions with measured adverse expectancy in Phase 2 (soft uplift only).
NY_QUALITY_SESSIONS: frozenset[str] = frozenset(
    {
        "new_york",
        "london_ny_overlap",
        "ny",
        "newyork",
        "overlap",
    }
)

# NY solo selectivity — above global solo bars, still respects owner Q70 floor.
NY_SOLO_MIN_QUALITY = 86
NY_SOLO_MIN_CONFIDENCE = 84
# Trend / momentum continuation in NY needs stronger HTF alignment.
NY_TREND_MIN_MTF = 70

# Strategies that require LTF directional confirmation with HTF.
_TRENDISH_IDS: frozenset[str] = frozenset(
    {
        "trend_continuation",
        "momentum_scalping",
    }
)

# Soft rank additives by market_regime → strategy_id (never a hard preference).
# Positive = more suitable; large negative demotes misfit without deleting
# candidates that already cleared hard filters (except LTF gate below).
_REGIME_SUITABILITY: dict[str, dict[str, float]] = {
    "strong_trend": {
        "trend_continuation": 3.5,
        "momentum_scalping": 3.0,
        "smc_scalping": 2.0,
        "breakout_scalping": 1.0,
        "range_mean_reversion": -6.0,
    },
    "weak_trend": {
        "smc_scalping": 3.5,
        "momentum_scalping": 2.0,
        "trend_continuation": 1.0,
        "breakout_scalping": 0.5,
        "range_mean_reversion": -2.0,
    },
    "range": {
        "range_mean_reversion": 6.0,
        "smc_scalping": 2.0,
        "breakout_scalping": -4.0,
        "momentum_scalping": -6.0,
        "trend_continuation": -8.0,
    },
    "compression": {
        "range_mean_reversion": 6.0,
        "smc_scalping": 1.5,
        "breakout_scalping": -6.0,
        "momentum_scalping": -8.0,
        "trend_continuation": -8.0,
    },
    "breakout": {
        "breakout_scalping": 6.0,
        "momentum_scalping": 3.0,
        "smc_scalping": 2.0,
        "trend_continuation": 1.0,
        "range_mean_reversion": -6.0,
    },
    "expansion": {
        "breakout_scalping": 4.0,
        "momentum_scalping": 3.5,
        "smc_scalping": 2.0,
        "trend_continuation": 1.5,
        "range_mean_reversion": -5.0,
    },
}


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_session(score: dict[str, Any] | None) -> str:
    if not isinstance(score, dict):
        return ""
    raw = score.get("market_session") or score.get("session")
    if not raw:
        assessment = score.get("session_assessment")
        if isinstance(assessment, dict):
            raw = assessment.get("session")
    return str(raw or "").strip().lower()


def _score_regime(score: dict[str, Any] | None) -> str:
    if not isinstance(score, dict):
        return ""
    return str(score.get("market_regime") or score.get("regime") or "").strip().lower()


def _factors(score: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(score, dict):
        return {}
    raw = score.get("factors")
    return raw if isinstance(raw, dict) else {}


def regime_suitability_boost(strategy_id: str, score: dict[str, Any] | None) -> float:
    """Soft rank additive from regime x strategy fit. Not a hard preference."""
    regime = _score_regime(score)
    table = _REGIME_SUITABILITY.get(regime) or {}
    return float(table.get(str(strategy_id), 0.0))


def is_ny_quality_session(score: dict[str, Any] | None) -> bool:
    return _score_session(score) in NY_QUALITY_SESSIONS


def sniper_chase_or_stale_reason(score: dict[str, Any] | None) -> str | None:
    """Prefer no trade when sniper marks chase/stale/conflict (late entry risk)."""
    if not isinstance(score, dict):
        return None
    sniper = score.get("sniper_entry")
    if not isinstance(sniper, dict):
        sniper = {}
    state = str(
        sniper.get("setup_state") or score.get("setup_state") or ""
    ).strip().upper()
    if state in {"CHASING", "STALE", "CONFLICT"}:
        return (
            f"Entry timing rejected: sniper setup_state={state} "
            "(late / stale / conflict) — prefer no trade"
        )
    factors = _factors(score)
    # Soft chase markers from scoring when setup_state not forwarded.
    try:
        displacement = float(factors.get("displacement") or 0)
        timing = float(factors.get("timing_retest") or 0)
    except (TypeError, ValueError):
        return None
    if (
        state
        and displacement <= 20
        and timing <= 20
        and state not in {"TAKE", "SETUP_READY"}
    ):
        return (
            f"Entry timing weak (displacement={displacement:.0f} "
            f"timing_retest={timing:.0f} state={state}) — prefer no trade"
        )
    return None


def ltf_htf_disagreement_reason(
    strategy_id: str,
    score: dict[str, Any] | None,
) -> str | None:
    """Block trendish strategies when lower-TF structure disagrees with HTF.

    Does not block SMC / breakout / range specialists — they have their own
    regime filters. Avoids trend_continuation entries into M5 range tape.
    """
    sid = str(strategy_id or "")
    if sid not in _TRENDISH_IDS:
        return None
    if not isinstance(score, dict):
        return None

    factors = _factors(score)
    direction = str(score.get("direction") or "").strip().upper()
    regime = _score_regime(score)
    mtf = _i(score.get("mtf_alignment"), _i(factors.get("mtf")))
    # Only enforce LTF structure gates when live scoring attached LTF artefacts.
    # Absent keys (unit fixtures / partial scores) must not invent disagreement.
    has_ltf = any(
        k in factors for k in ("m5_entry", "m5_bos", "m15_structure", "ltf_buy_score")
    ) or any(k in score for k in ("ltf_buy_score", "ltf_sell_score"))

    # Explicit range / compression already forbidden on TC registry — belt+suspenders.
    if regime in {"range", "compression"}:
        return (
            f"{sid} incompatible with LTF/regime={regime} "
            "— prefer alternate specialist or no trade"
        )

    if not has_ltf:
        return None

    m5_entry = _i(factors.get("m5_entry"))
    m5_bos = _i(factors.get("m5_bos"))
    m15_structure = _i(factors.get("m15_structure"))
    ltf_buy = _i(score.get("ltf_buy_score"), _i(factors.get("ltf_buy_score")))
    ltf_sell = _i(score.get("ltf_sell_score"), _i(factors.get("ltf_sell_score")))

    # No M5 lean and soft HTF → continuation into mixed tape (Phase 2 losers).
    if "m5_entry" in factors and m5_entry <= 0 and mtf < 75:
        return (
            f"{sid} lacks M5 entry lean with MTF={mtf} "
            "(HTF/LTF disagreement) — prefer no trade for this strategy"
        )

    # Directional LTF scores oppose the trade direction.
    if direction == "BUY" and ltf_sell > 0 and ltf_buy > 0 and ltf_sell >= ltf_buy + 8:
        return (
            f"{sid} BUY opposed by LTF sell lean "
            f"(buy={ltf_buy} sell={ltf_sell}) — prefer no trade for this strategy"
        )
    if direction == "SELL" and ltf_buy > 0 and ltf_sell > 0 and ltf_buy >= ltf_sell + 8:
        return (
            f"{sid} SELL opposed by LTF buy lean "
            f"(buy={ltf_buy} sell={ltf_sell}) — prefer no trade for this strategy"
        )

    # Continuation without M5/M15 structure confirmation (when those keys exist).
    if (
        ("m5_bos" in factors or "m15_structure" in factors)
        and m5_bos < 50
        and m15_structure < 50
        and mtf < 80
    ):
        return (
            f"{sid} missing M5/M15 structure confirmation "
            f"(m5_bos={m5_bos} m15={m15_structure} mtf={mtf}) "
            "— prefer no trade for this strategy"
        )

    return None


def ny_session_trend_mtf_reason(
    strategy_id: str,
    score: dict[str, Any] | None,
) -> str | None:
    """NY: trendish strategies need stronger MTF (session quality, not ban)."""
    if not is_ny_quality_session(score):
        return None
    if str(strategy_id) not in _TRENDISH_IDS:
        return None
    factors = _factors(score)
    mtf = _i(
        score.get("mtf_alignment") if isinstance(score, dict) else 0,
        _i(factors.get("mtf")),
    )
    if mtf < NY_TREND_MIN_MTF:
        return (
            f"NY session: {strategy_id} needs MTF>={NY_TREND_MIN_MTF} "
            f"(got {mtf}) — prefer no trade for this strategy"
        )
    return None


def momentum_exhaustion_buy_reason(score: dict[str, Any] | None) -> str | None:
    """Ultra-short losing BUY pattern: high momentum, weak structure / no pullback."""
    if not isinstance(score, dict):
        return None
    direction = str(score.get("direction") or "").strip().upper()
    if direction != "BUY":
        return None
    factors = _factors(score)
    try:
        momentum = float(score.get("momentum") or factors.get("momentum") or 0)
        structure = float(
            score.get("structure_score")
            or factors.get("bos")
            or factors.get("structure")
            or 0
        )
        timing = float(factors.get("timing_retest") or 0)
    except (TypeError, ValueError):
        return None
    if momentum >= 78 and structure < 55 and timing <= 25:
        return (
            f"BUY exhaustion risk: momentum={momentum:.0f} structure={structure:.0f} "
            f"timing_retest={timing:.0f} — prefer no trade"
        )
    return None


def evidence_intelligence_reason(score: dict[str, Any] | None) -> str | None:
    """Global evidence vetoes from Phase 3 intelligence (before strategy pick)."""
    return sniper_chase_or_stale_reason(score) or momentum_exhaustion_buy_reason(score)


def filter_candidates_by_ltf_session(
    candidates: list[Any],
    score: dict[str, Any] | None,
) -> tuple[list[Any], list[tuple[Any, str]]]:
    """Drop trendish candidates that fail LTF/NY gates; return (kept, demoted)."""
    kept: list[Any] = []
    demoted: list[tuple[Any, str]] = []
    for ev in candidates:
        sid = str(getattr(ev, "strategy_id", "") or "")
        reason = ltf_htf_disagreement_reason(sid, score) or ny_session_trend_mtf_reason(
            sid, score
        )
        if reason:
            demoted.append((ev, reason))
        else:
            kept.append(ev)
    return kept, demoted


def ny_solo_bars(score: dict[str, Any] | None) -> tuple[int, int] | None:
    """Return raised (quality, confidence) solo bars for NY sessions, else None."""
    if not is_ny_quality_session(score):
        return None
    return NY_SOLO_MIN_QUALITY, NY_SOLO_MIN_CONFIDENCE
