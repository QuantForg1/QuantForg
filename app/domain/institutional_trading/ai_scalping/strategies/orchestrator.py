"""Strategy Orchestration Engine (SOE).

Evaluates all live-eligible strategy profiles together, applies independently
verified performance influence, detects conflict / weak solo setups, and
prefers NO_TRADE over a poor trade.

Insertion point: AFTER per-strategy evaluate_all_strategies, BEFORE Risk /
Eligibility / OMS. Never authorizes order_send, never weakens SCALPING_V1
floors, never enables catalog-only or research plugins for live execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyEvaluation,
)
from app.domain.institutional_trading.ai_scalping.strategies.validation_status import (
    influence_weight_for_strategy,
    strategy_health_snapshot,
)

ORCHESTRATION_VERSION = "soe-v1.2.0"

# Solo passer must clear a higher quality bar (prefer no trade).
MIN_SOLO_QUALITY = 82
MIN_SOLO_CONFIDENCE = 80
# With multi-strategy agreement, allow slightly lower quality (still at/above
# owner minimum trade quality 75).
MIN_CONFLUENT_QUALITY = 76
MIN_CONFLUENCE_COUNT = 2
# Absolute floor even with confluence — never select junk (owner Q75).
MIN_ABSOLUTE_QUALITY = 75
# When advisory engines strongly disagree with the live pack — raise the bar.
ADVISORY_DISAGREE_MIN_QUALITY = 88
ADVISORY_DISAGREE_MIN_CONFIDENCE = 85
# Small-account / cost gate: wide spread vs weak RR → prefer no trade.
MAX_SPREAD_FOR_WEAK_RR = 0.80
MIN_RR_WHEN_SPREAD_ELEVATED = 1.50
# Absolute net reward:risk floor aligned with owner policy (prefer NO_TRADE).
MIN_NET_REWARD_RISK = 1.50
# Setup freshness: stale quotes / expired setups → NO_TRADE.
MAX_QUOTE_AGE_SECONDS = 8.0
MAX_SETUP_AGE_SECONDS = 120.0

# Regime-incompatible pairs: if both somehow pass, keep only the regime-fit
# specialist and demote the other (recorded as conflict resolution).
_REGIME_CONFLICT_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"trend_continuation", "range_mean_reversion"}),
        frozenset({"breakout_scalping", "range_mean_reversion"}),
        frozenset({"momentum_scalping", "range_mean_reversion"}),
    }
)


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    strategy_id: str
    name: str
    reason: str
    quality: int
    confidence: int
    influence_weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "reason": self.reason,
            "quality": self.quality,
            "confidence": self.confidence,
            "influence_weight": self.influence_weight,
        }


@dataclass(frozen=True, slots=True)
class OrchestrationVerdict:
    """Unified multi-strategy selection result — advisory for Risk/OMS."""

    decision: str  # BUY | SELL | NO_TRADE
    selected: StrategyEvaluation | None
    confluence_count: int
    confluence_score: int
    influence_weights: dict[str, float]
    rejected: tuple[RejectedCandidate, ...]
    reasons: tuple[str, ...]
    prefer_no_trade: bool
    conflicting: bool
    orchestration_version: str = ORCHESTRATION_VERSION
    health: dict[str, Any] = field(default_factory=dict)
    advisory_votes: tuple[dict[str, Any], ...] = ()
    advisory_agreement: dict[str, Any] = field(default_factory=dict)
    collaboration: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "selected_strategy_id": (
                self.selected.strategy_id if self.selected else None
            ),
            "selected_strategy_name": self.selected.name if self.selected else None,
            "selected_quality": self.selected.quality if self.selected else None,
            "selected_confidence": (
                self.selected.confidence if self.selected else None
            ),
            "confluence_count": self.confluence_count,
            "confluence_score": self.confluence_score,
            "influence_weights": dict(self.influence_weights),
            "rejected": [r.to_dict() for r in self.rejected],
            "reasons": list(self.reasons),
            "prefer_no_trade": self.prefer_no_trade,
            "conflicting": self.conflicting,
            "orchestration_version": self.orchestration_version,
            "health": dict(self.health),
            "advisory_votes": list(self.advisory_votes),
            "advisory_agreement": dict(self.advisory_agreement),
            "collaboration": dict(self.collaboration),
            "authorizes_trade": False,
            "live_auto_authorize": False,
        }


def _influence_map(
    evaluations: tuple[StrategyEvaluation, ...] | list[StrategyEvaluation],
    *,
    live_boosts: dict[str, float] | None,
    stats_snapshot: dict[str, Any] | None,
) -> dict[str, float]:
    boosts = live_boosts or {}
    health = (stats_snapshot or {}).get("health") or {}
    out: dict[str, float] = {}
    for ev in evaluations:
        sid = str(ev.strategy_id)
        row_health = health.get(sid) if isinstance(health, dict) else None
        out[sid] = influence_weight_for_strategy(
            strategy_id=sid,
            live_rank_boost=float(boosts.get(sid, ev.live_rank_boost)),
            health_row=row_health if isinstance(row_health, dict) else None,
        )
    return out


def _resolve_regime_conflicts(
    candidates: list[StrategyEvaluation],
) -> tuple[list[StrategyEvaluation], list[RejectedCandidate]]:
    """Drop weaker member of known incompatible regime pairs."""
    ids = {c.strategy_id for c in candidates}
    demoted: list[RejectedCandidate] = []
    drop: set[str] = set()
    for pair in _REGIME_CONFLICT_PAIRS:
        if not pair.issubset(ids):
            continue
        members = [c for c in candidates if c.strategy_id in pair]
        members.sort(key=lambda e: e.rank_key, reverse=True)
        for loser in members[1:]:
            drop.add(loser.strategy_id)
            demoted.append(
                RejectedCandidate(
                    strategy_id=loser.strategy_id,
                    name=loser.name,
                    reason=(
                        "Regime conflict with "
                        f"{members[0].strategy_id} — kept higher-ranked specialist"
                    ),
                    quality=loser.quality,
                    confidence=loser.confidence,
                    influence_weight=0.0,
                )
            )
    kept = [c for c in candidates if c.strategy_id not in drop]
    return kept, demoted


def _adjusted_rank(
    ev: StrategyEvaluation, *, influence: float, confluence_bonus: float
) -> tuple[float, int, int]:
    base = float(ev.quality) + float(ev.live_rank_boost)
    return (base * influence + confluence_bonus, ev.confidence, ev.quality)


def _score_rr(score: dict[str, Any]) -> float | None:
    rr_raw = (
        score.get("net_reward_risk")
        or score.get("expected_rr")
        or score.get("risk_reward")
    )
    try:
        return float(rr_raw) if rr_raw is not None else None
    except (TypeError, ValueError):
        return None


def _evidence_gate_prefer_no_trade(score: dict[str, Any] | None) -> str | None:
    """Prefer no trade on weak geometry, stale setups, or false-breakout risk."""
    if not isinstance(score, dict):
        return None
    rr = _score_rr(score)
    if rr is not None and rr < MIN_NET_REWARD_RISK:
        return (
            f"Net reward:risk {rr:.2f} below owner floor "
            f"{MIN_NET_REWARD_RISK:.2f} — prefer no trade"
        )

    spread_raw = score.get("spread")
    if spread_raw is None:
        spread_raw = score.get("spread_points")
    try:
        spread = float(spread_raw) if spread_raw is not None else None
    except (TypeError, ValueError):
        spread = None
    if (
        spread is not None
        and rr is not None
        and spread >= MAX_SPREAD_FOR_WEAK_RR
        and rr < MIN_RR_WHEN_SPREAD_ELEVATED
    ):
        return (
            f"Elevated spread {spread:.2f} with weak RR {rr:.2f} "
            f"(need RR>={MIN_RR_WHEN_SPREAD_ELEVATED}) — prefer no trade"
        )

    for key, limit, label in (
        ("quote_age_seconds", MAX_QUOTE_AGE_SECONDS, "quote"),
        ("setup_age_seconds", MAX_SETUP_AGE_SECONDS, "setup"),
        ("signal_age_seconds", MAX_SETUP_AGE_SECONDS, "signal"),
    ):
        raw = score.get(key)
        if raw is None:
            continue
        try:
            age = float(raw)
        except (TypeError, ValueError):
            continue
        if age > limit:
            return (
                f"Stale {label} age {age:.1f}s exceeds {limit:.0f}s "
                "— prefer no trade (setup freshness)"
            )

    raw_factors = score.get("factors")
    factors: dict[str, Any] = raw_factors if isinstance(raw_factors, dict) else {}
    try:
        bos = float(factors.get("bos") or score.get("structure_score") or 0)
        vol = float(
            factors.get("volatility")
            or factors.get("atr_expansion")
            or factors.get("volume")
            or 50
        )
        momentum = float(score.get("momentum") or factors.get("momentum") or 0)
        structure = float(score.get("structure_score") or factors.get("bos") or 0)
    except (TypeError, ValueError):
        return None

    if bos >= 70 and vol < 45:
        return (
            f"False-breakout risk: BOS {bos:.0f} without volatility "
            f"confirmation ({vol:.0f}) — prefer no trade"
        )
    if momentum >= 75 and structure < 45:
        return (
            f"Momentum exhaustion risk: momentum {momentum:.0f} with weak "
            f"structure {structure:.0f} — prefer no trade"
        )
    return None


def orchestrate_strategies(
    evaluations: tuple[StrategyEvaluation, ...] | list[StrategyEvaluation],
    *,
    live_boosts: dict[str, float] | None = None,
    stats_snapshot: dict[str, Any] | None = None,
    advisory_votes: tuple[Any, ...] | list[Any] | None = None,
    score: dict[str, Any] | None = None,
) -> OrchestrationVerdict:
    """Select at most one LIVE-eligible strategy opportunity or prefer NO_TRADE.

    Live pack + advisory engines collaborate on agreement analysis. Only the
    five SCALPING_V1 profiles may be selected for OMS. Advisory votes never
    authorize order_send. Deteriorating strategies lose selection power.
    """
    from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
        AdvisoryVote,
        collect_score_factor_advisory_votes,
        summarize_advisory_agreement,
    )

    evals = tuple(evaluations)
    health = strategy_health_snapshot(stats_snapshot)
    snap = {"health": health, **(stats_snapshot or {})}
    weights = _influence_map(evals, live_boosts=live_boosts, stats_snapshot=snap)

    votes: list[AdvisoryVote] = []
    if advisory_votes:
        for v in advisory_votes:
            if isinstance(v, AdvisoryVote):
                votes.append(v)
            elif isinstance(v, dict):
                src = str(v.get("source") or "score_factor_advisory")
                if src not in {
                    "score_factor_advisory",
                    "strategy_engine_plugin",
                    "institutional_alpha",
                    "m1_micro",
                }:
                    src = "score_factor_advisory"
                votes.append(
                    AdvisoryVote(
                        strategy_id=str(v.get("strategy_id") or "unknown"),
                        name=str(v.get("name") or v.get("strategy_id") or "unknown"),
                        direction=str(v.get("direction") or "HOLD").upper(),
                        confidence=int(v.get("confidence") or 0),
                        reason=str(v.get("reason") or ""),
                        source=src,  # type: ignore[arg-type]
                    )
                )
    elif isinstance(score, dict):
        votes.extend(collect_score_factor_advisory_votes(score))

    advisory_dicts = tuple(v.to_dict() for v in votes)

    def _collab(agreement: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "live_pack_evaluated": len(evals),
            "advisory_engines": len(votes),
            "oms_winner_allowed_from_advisory": False,
            "advisory_agreement": dict(agreement or {}),
        }

    def _no_trade(
        *,
        reasons_t: tuple[str, ...],
        rejected_t: tuple[RejectedCandidate, ...] = (),
        confluence_count: int = 0,
        confluence_score: int = 0,
        conflicting: bool = False,
        live_direction: str = "NONE",
    ) -> OrchestrationVerdict:
        agreement = summarize_advisory_agreement(
            live_direction=live_direction, votes=votes
        )
        return OrchestrationVerdict(
            decision="NO_TRADE",
            selected=None,
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            influence_weights=weights,
            rejected=rejected_t,
            reasons=reasons_t,
            prefer_no_trade=True,
            conflicting=conflicting,
            health=health,
            advisory_votes=advisory_dicts,
            advisory_agreement=agreement,
            collaboration=_collab(agreement),
        )

    rejected: list[RejectedCandidate] = []
    reasons: list[str] = []

    evidence_reason = _evidence_gate_prefer_no_trade(score)
    if evidence_reason:
        return _no_trade(reasons_t=(evidence_reason,))

    for ev in evals:
        if not ev.passed:
            rejected.append(
                RejectedCandidate(
                    strategy_id=ev.strategy_id,
                    name=ev.name,
                    reason=ev.reject_reason or "strategy_filters_failed",
                    quality=ev.quality,
                    confidence=ev.confidence,
                    influence_weight=weights.get(ev.strategy_id, 1.0),
                )
            )

    # Influence veto: passed on filters but deteriorating → not selectable.
    selectable: list[StrategyEvaluation] = []
    for ev in evals:
        if not ev.passed:
            continue
        w = weights.get(ev.strategy_id, 1.0)
        if w <= 0.0:
            rejected.append(
                RejectedCandidate(
                    strategy_id=ev.strategy_id,
                    name=ev.name,
                    reason=(
                        "Deteriorating live performance — influence veto "
                        "(prefer no trade until recovery evidence)"
                    ),
                    quality=ev.quality,
                    confidence=ev.confidence,
                    influence_weight=w,
                )
            )
            reasons.append(f"veto:{ev.strategy_id}:deteriorating")
            continue
        selectable.append(ev)

    selectable, conflict_rejects = _resolve_regime_conflicts(selectable)
    rejected.extend(conflict_rejects)

    if not selectable:
        return _no_trade(
            reasons_t=tuple(
                reasons
                or (
                    "No selectable strategy after filters, influence, and conflict "
                    "resolution — prefer no trade",
                )
            ),
            rejected_t=tuple(rejected),
            conflicting=bool(conflict_rejects),
        )

    directions = {e.direction for e in selectable if e.direction in {"BUY", "SELL"}}
    if len(directions) > 1:
        for ev in selectable:
            rejected.append(
                RejectedCandidate(
                    strategy_id=ev.strategy_id,
                    name=ev.name,
                    reason=f"Direction conflict ({ev.direction}) across passers",
                    quality=ev.quality,
                    confidence=ev.confidence,
                    influence_weight=weights.get(ev.strategy_id, 1.0),
                )
            )
        return _no_trade(
            reasons_t=(
                "Conflicting strategy directions — prefer no trade: "
                + ", ".join(f"{e.strategy_id}={e.direction}" for e in selectable),
            ),
            rejected_t=tuple(rejected),
            conflicting=True,
        )

    confluence_count = len(selectable)
    # Agreement quality: share of live pack that passed and remained selectable.
    confluence_score = max(
        0, min(100, round(100.0 * confluence_count / max(1, len(evals))))
    )
    confluence_bonus = 4.0 if confluence_count >= MIN_CONFLUENCE_COUNT else 0.0

    ranked = sorted(
        selectable,
        key=lambda e: _adjusted_rank(
            e,
            influence=weights.get(e.strategy_id, 1.0),
            confluence_bonus=confluence_bonus,
        ),
        reverse=True,
    )
    best = ranked[0]

    # Selectivity: solo passers need stronger evidence; confluent packs use
    # MIN_CONFLUENT_QUALITY. Never select below MIN_ABSOLUTE_QUALITY.
    solo = confluence_count < MIN_CONFLUENCE_COUNT
    agreement = summarize_advisory_agreement(live_direction=best.direction, votes=votes)
    # Advisory disagreement raises the evidence bar (never manufactures consensus).
    if agreement.get("strong_disagreement") and (
        best.quality < ADVISORY_DISAGREE_MIN_QUALITY
        and best.confidence < ADVISORY_DISAGREE_MIN_CONFIDENCE
    ):
        return _no_trade(
            reasons_t=(
                "Advisory engines disagree with live pack and evidence is "
                f"below raised bar (need q>={ADVISORY_DISAGREE_MIN_QUALITY} or "
                f"c>={ADVISORY_DISAGREE_MIN_CONFIDENCE}; got q={best.quality} "
                f"c={best.confidence}) — prefer no trade",
            ),
            rejected_t=tuple(rejected),
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            live_direction=best.direction,
        )

    if best.quality < MIN_ABSOLUTE_QUALITY:
        return _no_trade(
            reasons_t=(
                f"Best quality {best.quality} < absolute floor "
                f"{MIN_ABSOLUTE_QUALITY} — prefer no trade",
            ),
            rejected_t=tuple(rejected),
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            live_direction=best.direction,
        )

    if solo:
        solo_ok = (
            best.quality >= MIN_SOLO_QUALITY or best.confidence >= MIN_SOLO_CONFIDENCE
        )
        # Supportive advisory can count as soft confluence for solo selectivity.
        if agreement.get("supportive") and best.quality >= MIN_CONFLUENT_QUALITY:
            solo_ok = True
            reasons.append(
                f"advisory_supportive:{agreement.get('agree_count')} engines"
            )
        if not solo_ok:
            for ev in selectable:
                rejected.append(
                    RejectedCandidate(
                        strategy_id=ev.strategy_id,
                        name=ev.name,
                        reason=(
                            f"Solo strategy below selectivity bar "
                            f"(need quality>={MIN_SOLO_QUALITY} or "
                            f"confidence>={MIN_SOLO_CONFIDENCE}; "
                            f"got q={ev.quality} c={ev.confidence})"
                        ),
                        quality=ev.quality,
                        confidence=ev.confidence,
                        influence_weight=weights.get(ev.strategy_id, 1.0),
                    )
                )
            return _no_trade(
                reasons_t=(
                    "Insufficient confluence and solo quality — prefer no trade "
                    f"(confluence={confluence_count}, best_q={best.quality}, "
                    f"best_c={best.confidence})",
                ),
                rejected_t=tuple(rejected),
                confluence_count=confluence_count,
                confluence_score=confluence_score,
                live_direction=best.direction,
            )
    elif best.quality < MIN_CONFLUENT_QUALITY:
        return _no_trade(
            reasons_t=(
                f"Confluent strategies still below quality "
                f"{MIN_CONFLUENT_QUALITY} — prefer no trade",
            ),
            rejected_t=tuple(rejected),
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            live_direction=best.direction,
        )

    # Record superseded passers as rejected-for-selection (not filter rejects).
    for ev in ranked[1:]:
        rejected.append(
            RejectedCandidate(
                strategy_id=ev.strategy_id,
                name=ev.name,
                reason=(
                    f"Superseded by {best.strategy_id} "
                    f"(q={best.quality} vs {ev.quality}, "
                    f"influence={weights.get(best.strategy_id, 1.0):.2f})"
                ),
                quality=ev.quality,
                confidence=ev.confidence,
                influence_weight=weights.get(ev.strategy_id, 1.0),
            )
        )

    if agreement.get("supportive"):
        confluence_bonus_note = (
            f"advisory_agree={agreement.get('agree_count')} "
            f"disagree={agreement.get('disagree_count')}"
        )
    else:
        confluence_bonus_note = (
            f"advisory_agree={agreement.get('agree_count')} "
            f"disagree={agreement.get('disagree_count')} "
            f"hold={agreement.get('hold_count')}"
        )

    select_reasons = (
        f"SOE selected {best.strategy_id} direction={best.direction} "
        f"quality={best.quality} confidence={best.confidence} "
        f"confluence={confluence_count}/{len(evals)} "
        f"influence={weights.get(best.strategy_id, 1.0):.2f}",
        confluence_bonus_note,
        f"orchestration={ORCHESTRATION_VERSION}",
        *reasons,
        best.explanation,
    )
    return OrchestrationVerdict(
        decision=best.direction if best.direction in {"BUY", "SELL"} else "NO_TRADE",
        selected=best,
        confluence_count=confluence_count,
        confluence_score=confluence_score,
        influence_weights=weights,
        rejected=tuple(rejected),
        reasons=select_reasons,
        prefer_no_trade=False,
        conflicting=False,
        health=health,
        advisory_votes=advisory_dicts,
        advisory_agreement=agreement,
        collaboration=_collab(agreement),
    )


def catalog_participation_policy() -> dict[str, Any]:
    """Document which strategy surfaces may participate in SOE analysis."""
    from app.domain.institutional_trading.ai_scalping.strategies.live_eligibility import (  # noqa: E501
        eligibility_snapshot,
    )

    snap = eligibility_snapshot()
    forbidden_ids = [
        r["strategy_id"] for r in snap["strategies"] if r.get("tier") == "forbidden"
    ]
    catalog_ids = [
        r["strategy_id"] for r in snap["strategies"] if r.get("tier") == "catalog_only"
    ]
    return {
        "live_executable_profiles": [
            r["strategy_id"] for r in snap["strategies"] if r.get("may_select_for_oms")
        ],
        "analysis_participants": [
            r["strategy_id"]
            for r in snap["strategies"]
            if r.get("participates_in_analysis")
        ],
        "ops_gated": [
            r["strategy_id"] for r in snap["strategies"] if r.get("tier") == "ops_gated"
        ],
        "catalog_only": catalog_ids,
        "never_live_from_catalog": sorted(
            set(catalog_ids + forbidden_ids + ["rsi", "macd", "bollinger_bands"])
        ),
        "forbidden": forbidden_ids,
        "rule": (
            "All analysis participants may vote; only live_executable profiles "
            "may win OMS selection; prefer no trade; never auto-authorize LIVE."
        ),
        "orchestration_version": ORCHESTRATION_VERSION,
        "eligibility": snap,
    }
