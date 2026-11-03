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

ORCHESTRATION_VERSION = "soe-v1.0.0"

# Solo passer must clear a higher quality bar (prefer no trade).
MIN_SOLO_QUALITY = 82
MIN_SOLO_CONFIDENCE = 80
# With multi-strategy agreement, allow slightly lower quality (still not below
# typical SCALPING_V1 soft evidence).
MIN_CONFLUENT_QUALITY = 74
MIN_CONFLUENCE_COUNT = 2
# Absolute floor even with confluence — never select junk.
MIN_ABSOLUTE_QUALITY = 70

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
            "authorizes_trade": False,
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


def orchestrate_strategies(
    evaluations: tuple[StrategyEvaluation, ...] | list[StrategyEvaluation],
    *,
    live_boosts: dict[str, float] | None = None,
    stats_snapshot: dict[str, Any] | None = None,
) -> OrchestrationVerdict:
    """Select at most one strategy opportunity or prefer NO_TRADE.

    All strategies are evaluated for intelligence; only one may win per symbol.
    Deteriorating strategies keep analysis visibility but lose selection power.
    """
    evals = tuple(evaluations)
    health = strategy_health_snapshot(stats_snapshot)
    snap = {"health": health, **(stats_snapshot or {})}
    weights = _influence_map(evals, live_boosts=live_boosts, stats_snapshot=snap)

    rejected: list[RejectedCandidate] = []
    reasons: list[str] = []

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
        return OrchestrationVerdict(
            decision="NO_TRADE",
            selected=None,
            confluence_count=0,
            confluence_score=0,
            influence_weights=weights,
            rejected=tuple(rejected),
            reasons=tuple(
                reasons
                or (
                    "No selectable strategy after filters, influence, and conflict "
                    "resolution — prefer no trade",
                )
            ),
            prefer_no_trade=True,
            conflicting=bool(conflict_rejects),
            health=health,
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
        return OrchestrationVerdict(
            decision="NO_TRADE",
            selected=None,
            confluence_count=0,
            confluence_score=0,
            influence_weights=weights,
            rejected=tuple(rejected),
            reasons=(
                "Conflicting strategy directions — prefer no trade: "
                + ", ".join(f"{e.strategy_id}={e.direction}" for e in selectable),
            ),
            prefer_no_trade=True,
            conflicting=True,
            health=health,
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
    if best.quality < MIN_ABSOLUTE_QUALITY:
        return OrchestrationVerdict(
            decision="NO_TRADE",
            selected=None,
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            influence_weights=weights,
            rejected=tuple(rejected),
            reasons=(
                f"Best quality {best.quality} < absolute floor "
                f"{MIN_ABSOLUTE_QUALITY} — prefer no trade",
            ),
            prefer_no_trade=True,
            conflicting=False,
            health=health,
        )

    if solo:
        solo_ok = (
            best.quality >= MIN_SOLO_QUALITY
            or best.confidence >= MIN_SOLO_CONFIDENCE
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
            return OrchestrationVerdict(
                decision="NO_TRADE",
                selected=None,
                confluence_count=confluence_count,
                confluence_score=confluence_score,
                influence_weights=weights,
                rejected=tuple(rejected),
                reasons=(
                    "Insufficient confluence and solo quality — prefer no trade "
                    f"(confluence={confluence_count}, best_q={best.quality}, "
                    f"best_c={best.confidence})",
                ),
                prefer_no_trade=True,
                conflicting=False,
                health=health,
            )
    elif best.quality < MIN_CONFLUENT_QUALITY:
        return OrchestrationVerdict(
            decision="NO_TRADE",
            selected=None,
            confluence_count=confluence_count,
            confluence_score=confluence_score,
            influence_weights=weights,
            rejected=tuple(rejected),
            reasons=(
                f"Confluent strategies still below quality "
                f"{MIN_CONFLUENT_QUALITY} — prefer no trade",
            ),
            prefer_no_trade=True,
            conflicting=False,
            health=health,
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

    select_reasons = (
        f"SOE selected {best.strategy_id} direction={best.direction} "
        f"quality={best.quality} confidence={best.confidence} "
        f"confluence={confluence_count}/{len(evals)} "
        f"influence={weights.get(best.strategy_id, 1.0):.2f}",
        f"orchestration={ORCHESTRATION_VERSION}",
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
    )


def catalog_participation_policy() -> dict[str, Any]:
    """Document which strategy surfaces may participate in SOE analysis."""
    return {
        "live_executable_profiles": [
            "smc_scalping",
            "trend_continuation",
            "breakout_scalping",
            "range_mean_reversion",
            "momentum_scalping",
        ],
        "analysis_only": [
            "institutional_alpha_v5 (ops enable required)",
            "m1_micro setups (unified_decision arbitration)",
            "ite_swing_confluence (mode=swing)",
            "strategy_engine_plugins (intentions only)",
            "alpha_factory / research_lab / scalping_ai_v2 / ASI",
        ],
        "never_live_from_catalog": [
            "session_breakout",
            "ma_cross",
            "rsi",
            "macd",
            "bollinger_bands",
            "grid",
            "martingale",
        ],
        "rule": (
            "All valid live profiles participate in evaluation; only one may "
            "select; catalog/research never order_send; prefer no trade."
        ),
        "orchestration_version": ORCHESTRATION_VERSION,
    }
