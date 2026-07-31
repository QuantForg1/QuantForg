"""M15 Trend Semantics v2 — pullback vs reversal taxonomy.

Institutional naming (role vocabulary used by MTF / cycle evidence):
  H1  = primary structure bias
  M15 = entry-confirmation TF (clock M15 in swing; entry role in all modes)
  M5  = execution timing only — never redefines direction

When the higher TF remains structurally directional, M15 raw RANGE/DOWN is
reclassified as pullback / consolidation / continuation instead of a hard
DOWN that invalidates the H1+M15 directional lock.

DOWN is reserved for confirmed structural regime reversal (CHOCH + opposing BOS).
Quality / confidence thresholds are never lowered here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.order_block.enums import OrderBlockState
from app.domain.order_block.models import OrderBlockSnapshot

SEMANTICS_VERSION = "m15-semantics-v2.0.0"


class M15SemanticLabel(str, Enum):
    TREND_CONTINUATION = "TREND_CONTINUATION"
    PULLBACK_WITHIN_TREND = "PULLBACK_WITHIN_TREND"
    CONSOLIDATION = "CONSOLIDATION"
    TRUE_REGIME_REVERSAL = "TRUE_REGIME_REVERSAL"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class M15SemanticsResult:
    """Classification of entry-TF (M15 role) relative to structural H1 bias."""

    previous_classification: str
    new_classification: M15SemanticLabel
    previous_direction: TrendDirection
    effective_direction: TrendDirection
    structural_bias: TrendDirection
    reason: str
    has_valid_bos: bool = False
    has_valid_ob: bool = False
    has_valid_fvg: bool = False
    bos_agrees_bias: bool = False
    choch_opposes_bias: bool = False
    confirmed_reversal: bool = False
    m5_ignored_for_direction: bool = True
    version: str = SEMANTICS_VERSION

    @property
    def rewritten(self) -> bool:
        return (
            self.new_classification is not M15SemanticLabel.UNCHANGED
            and self.effective_direction != self.previous_direction
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_classification": self.previous_classification,
            "new_classification": self.new_classification.value,
            "previous_direction": self.previous_direction.value,
            "effective_direction": self.effective_direction.value,
            "structural_bias": self.structural_bias.value,
            "reason": self.reason,
            "has_valid_bos": self.has_valid_bos,
            "has_valid_ob": self.has_valid_ob,
            "has_valid_fvg": self.has_valid_fvg,
            "bos_agrees_bias": self.bos_agrees_bias,
            "choch_opposes_bias": self.choch_opposes_bias,
            "confirmed_reversal": self.confirmed_reversal,
            "m5_ignored_for_direction": self.m5_ignored_for_direction,
            "rewritten": self.rewritten,
            "version": self.version,
        }


def _dir_label(d: TrendDirection) -> str:
    return d.value.upper() if d is not TrendDirection.UNKNOWN else "UNKNOWN"


def _raw_classification(direction: TrendDirection) -> str:
    """Legacy single-label used before semantics v2."""
    if direction is TrendDirection.UP:
        return "UP"
    if direction is TrendDirection.DOWN:
        return "DOWN"
    if direction is TrendDirection.RANGE:
        return "RANGE"
    return "UNKNOWN"


def _latest_bos_direction(snap: StructureSnapshot | None) -> TrendDirection | None:
    if snap is None or not snap.breaks_of_structure:
        return None
    return snap.breaks_of_structure[-1].trend_direction


def _latest_choch_opposes(snap: StructureSnapshot | None, bias: TrendDirection) -> bool:
    if snap is None or not snap.changes_of_character:
        return False
    if bias not in {TrendDirection.UP, TrendDirection.DOWN}:
        return False
    choch = snap.changes_of_character[-1]
    # CHOCH breaks prior trend; previous_trend matching bias ⇒ character change against bias
    return choch.previous_trend == bias


def _has_active_ob(ob: OrderBlockSnapshot | None) -> bool:
    if ob is None:
        return False
    return any(
        b.state in {OrderBlockState.ACTIVE, OrderBlockState.VALIDATED}
        for b in (ob.order_blocks or ())
    )


def _has_open_fvg(fvg: FairValueGapSnapshot | None) -> bool:
    if fvg is None:
        return False
    return len(getattr(fvg, "active_gaps", ()) or ()) > 0


def resolve_structural_bias(
    structure_by_tf: dict[Timeframe, StructureSnapshot],
    *,
    primary_tf: Timeframe,
) -> TrendDirection:
    """Prefer clock H1 when directional; else primary structure TF."""
    h1 = structure_by_tf.get(Timeframe.H1)
    if h1 is not None and h1.trend.direction in {
        TrendDirection.UP,
        TrendDirection.DOWN,
    }:
        return h1.trend.direction
    primary = structure_by_tf.get(primary_tf)
    if primary is not None and primary.trend.direction in {
        TrendDirection.UP,
        TrendDirection.DOWN,
    }:
        return primary.trend.direction
    return TrendDirection.UNKNOWN


def classify_m15_semantics(
    *,
    structural_bias: TrendDirection,
    m15_raw: TrendDirection,
    bos_direction: TrendDirection | None = None,
    choch_opposes_bias: bool = False,
    has_valid_ob: bool = False,
    has_valid_fvg: bool = False,
    has_valid_bos: bool = False,
) -> M15SemanticsResult:
    """Classify M15-role direction relative to structural (H1) bias.

    M5 is intentionally absent — execution timing must not redefine direction.
    """
    previous = _raw_classification(m15_raw)
    bos_agrees = bool(
        bos_direction is not None
        and structural_bias in {TrendDirection.UP, TrendDirection.DOWN}
        and bos_direction == structural_bias
    )
    bos_opposes = bool(
        bos_direction is not None
        and structural_bias in {TrendDirection.UP, TrendDirection.DOWN}
        and bos_direction in {TrendDirection.UP, TrendDirection.DOWN}
        and bos_direction != structural_bias
    )

    # No usable higher-TF bias → leave M15 alone
    if structural_bias not in {TrendDirection.UP, TrendDirection.DOWN}:
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=M15SemanticLabel.UNCHANGED,
            previous_direction=m15_raw,
            effective_direction=m15_raw,
            structural_bias=structural_bias,
            reason="No directional structural bias — M15 left unchanged",
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=False,
        )

    # Already aligned with bias
    if m15_raw == structural_bias:
        continuation_structure = (
            has_valid_bos and bos_agrees and has_valid_ob and has_valid_fvg
        )
        label = (
            M15SemanticLabel.TREND_CONTINUATION
            if continuation_structure
            else M15SemanticLabel.TREND_CONTINUATION
        )
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=label,
            previous_direction=m15_raw,
            effective_direction=structural_bias,
            structural_bias=structural_bias,
            reason=(
                f"M15 already {_dir_label(m15_raw)}; aligned with structural "
                f"{_dir_label(structural_bias)}"
                + (" (BOS+OB+FVG continuation)" if continuation_structure else "")
            ),
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=False,
        )

    # Confirmed structural reversal only
    confirmed_reversal = bool(
        m15_raw
        == (
            TrendDirection.DOWN
            if structural_bias is TrendDirection.UP
            else TrendDirection.UP
        )
        and choch_opposes_bias
        and bos_opposes
    )
    # Also treat RANGE→opposing after CHOCH+opposing BOS as reversal attempt
    if not confirmed_reversal and choch_opposes_bias and bos_opposes:
        confirmed_reversal = True

    if confirmed_reversal:
        rev_dir = (
            TrendDirection.DOWN
            if structural_bias is TrendDirection.UP
            else TrendDirection.UP
        )
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=M15SemanticLabel.TRUE_REGIME_REVERSAL,
            previous_direction=m15_raw,
            effective_direction=rev_dir,
            structural_bias=structural_bias,
            reason=(
                f"Confirmed regime reversal vs structural {_dir_label(structural_bias)}: "
                f"CHOCH against bias + opposing BOS "
                f"(bos={bos_direction.value if bos_direction else 'none'})"
            ),
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=True,
        )

    # Continuation: BOS + OB + FVG with bias despite RANGE raw
    if (
        m15_raw is TrendDirection.RANGE
        and has_valid_bos
        and bos_agrees
        and has_valid_ob
        and has_valid_fvg
    ):
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=M15SemanticLabel.TREND_CONTINUATION,
            previous_direction=m15_raw,
            effective_direction=structural_bias,
            structural_bias=structural_bias,
            reason=(
                f"RANGE with valid BOS+OB+FVG continuation — align M15 with "
                f"structural {_dir_label(structural_bias)}"
            ),
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=False,
        )

    # Pullback within trend: raw DOWN (or soft conflict) without confirmed reversal
    opposite = (
        TrendDirection.DOWN
        if structural_bias is TrendDirection.UP
        else TrendDirection.UP
    )
    if m15_raw == opposite:
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=M15SemanticLabel.PULLBACK_WITHIN_TREND,
            previous_direction=m15_raw,
            effective_direction=structural_bias,
            structural_bias=structural_bias,
            reason=(
                f"M15 {_dir_label(m15_raw)} is pullback within structural "
                f"{_dir_label(structural_bias)} — not a confirmed reversal"
                + ("; latest BOS still agrees" if bos_agrees else "")
            ),
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=False,
        )

    # Consolidation / pause inside trend
    if m15_raw is TrendDirection.RANGE:
        return M15SemanticsResult(
            previous_classification=previous,
            new_classification=M15SemanticLabel.CONSOLIDATION,
            previous_direction=m15_raw,
            effective_direction=structural_bias,
            structural_bias=structural_bias,
            reason=(
                f"M15 RANGE consolidation within structural "
                f"{_dir_label(structural_bias)} — does not invalidate H1+M15 lock"
            ),
            has_valid_bos=has_valid_bos,
            has_valid_ob=has_valid_ob,
            has_valid_fvg=has_valid_fvg,
            bos_agrees_bias=bos_agrees,
            choch_opposes_bias=choch_opposes_bias,
            confirmed_reversal=False,
        )

    return M15SemanticsResult(
        previous_classification=previous,
        new_classification=M15SemanticLabel.UNCHANGED,
        previous_direction=m15_raw,
        effective_direction=m15_raw,
        structural_bias=structural_bias,
        reason=f"No semantic rewrite for M15={_dir_label(m15_raw)}",
        has_valid_bos=has_valid_bos,
        has_valid_ob=has_valid_ob,
        has_valid_fvg=has_valid_fvg,
        bos_agrees_bias=bos_agrees,
        choch_opposes_bias=choch_opposes_bias,
        confirmed_reversal=False,
    )


def classify_m15_semantics_from_snapshots(
    *,
    structure_by_tf: dict[Timeframe, StructureSnapshot],
    primary_tf: Timeframe,
    entry_tf: Timeframe,
    order_blocks: OrderBlockSnapshot | None = None,
    fair_value_gaps: FairValueGapSnapshot | None = None,
) -> M15SemanticsResult:
    """Derive semantics from live structure / OB / FVG snapshots."""
    bias = resolve_structural_bias(structure_by_tf, primary_tf=primary_tf)
    entry_snap = structure_by_tf.get(entry_tf)
    primary_snap = structure_by_tf.get(primary_tf)
    m15_raw = (
        entry_snap.trend.direction if entry_snap is not None else TrendDirection.UNKNOWN
    )
    # Prefer primary structure events (institutional BOS/CHOCH surface)
    event_snap = primary_snap or entry_snap
    bos_dir = _latest_bos_direction(event_snap)
    has_bos = bool(event_snap and event_snap.breaks_of_structure)
    choch_opp = _latest_choch_opposes(event_snap, bias)
    return classify_m15_semantics(
        structural_bias=bias,
        m15_raw=m15_raw,
        bos_direction=bos_dir,
        choch_opposes_bias=choch_opp,
        has_valid_ob=_has_active_ob(order_blocks),
        has_valid_fvg=_has_open_fvg(fair_value_gaps),
        has_valid_bos=has_bos,
    )


def _rewrite_trend_direction(
    trend: TrendState, direction: TrendDirection
) -> TrendState:
    return replace(trend, direction=direction, id=uuid4())


def overlay_m15_semantics_on_structure(
    structure_by_tf: dict[Timeframe, StructureSnapshot],
    *,
    primary_tf: Timeframe,
    entry_tf: Timeframe,
    order_blocks: OrderBlockSnapshot | None = None,
    fair_value_gaps: FairValueGapSnapshot | None = None,
) -> tuple[dict[Timeframe, StructureSnapshot], M15SemanticsResult]:
    """Rewrite entry-TF trend direction in-place map for TrendEngine / MTF.

    Does not touch execution TF (M5 role). Structural bias TF is never
    rewritten by M5.
    """
    result = classify_m15_semantics_from_snapshots(
        structure_by_tf=structure_by_tf,
        primary_tf=primary_tf,
        entry_tf=entry_tf,
        order_blocks=order_blocks,
        fair_value_gaps=fair_value_gaps,
    )
    out = dict(structure_by_tf)
    entry_snap = out.get(entry_tf)
    if (
        entry_snap is not None
        and result.effective_direction != entry_snap.trend.direction
    ):
        out[entry_tf] = replace(
            entry_snap,
            trend=_rewrite_trend_direction(
                entry_snap.trend, result.effective_direction
            ),
            id=uuid4(),
        )
    return out, result


def classify_m15_semantics_from_cycle_evidence(
    *,
    h1_direction: TrendDirection,
    m15_direction: TrendDirection,
    latest_bos_direction: TrendDirection | None = None,
    has_ob: bool = False,
    has_fvg: bool = False,
    has_bos: bool = False,
    choch_opposes_bias: bool = False,
) -> M15SemanticsResult:
    """Replay helper: classify from cycle evidence role labels (H1/M15)."""
    return classify_m15_semantics(
        structural_bias=h1_direction,
        m15_raw=m15_direction,
        bos_direction=latest_bos_direction,
        choch_opposes_bias=choch_opposes_bias,
        has_valid_ob=has_ob,
        has_valid_fvg=has_fvg,
        has_valid_bos=has_bos,
    )
