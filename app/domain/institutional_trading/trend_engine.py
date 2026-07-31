"""MTF Trend Engine — hierarchical bias from configured timeframes.

AI Decision Engine v2 + M15 Trend Semantics v2:
- Regime-aware alignment via ``mtf_v2.evaluate_mtf_v2``
- Entry-TF (M15 role) pullback/consolidation rewrite before lock
- H1+M15 directional lock; M5 execution timing only
- Quality/confidence floors unchanged
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.m15_semantics_v2 import (
    M15SemanticsResult,
    overlay_m15_semantics_on_structure,
)
from app.domain.institutional_trading.models import TrendSnapshot
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot
from app.domain.order_block.models import OrderBlockSnapshot


def _dir_from_snapshot(snap: StructureSnapshot | None) -> TrendDirection:
    if snap is None or snap.trend is None:
        return TrendDirection.UNKNOWN
    return snap.trend.direction


@dataclass(frozen=True, slots=True)
class TrendEngine:
    """Derive hierarchical MTF bias from structure snapshots."""

    config: ITEConfig

    def analyze(
        self,
        structure_by_tf: dict[Timeframe, StructureSnapshot],
        *,
        order_blocks: OrderBlockSnapshot | None = None,
        fair_value_gaps: FairValueGapSnapshot | None = None,
        apply_m15_semantics: bool = True,
    ) -> TrendSnapshot:
        cfg = self.config
        working = dict(structure_by_tf)
        semantics: M15SemanticsResult | None = None
        if apply_m15_semantics:
            working, semantics = overlay_m15_semantics_on_structure(
                working,
                primary_tf=cfg.primary_structure_tf,
                entry_tf=cfg.entry_confirmation_tf,
                order_blocks=order_blocks,
                fair_value_gaps=fair_value_gaps,
            )

        macro = _dir_from_snapshot(working.get(cfg.macro_bias_tf))
        primary = _dir_from_snapshot(working.get(cfg.primary_structure_tf))
        entry = _dir_from_snapshot(working.get(cfg.entry_confirmation_tf))
        execution = _dir_from_snapshot(working.get(cfg.execution_management_tf))

        frames = {
            cfg.macro_bias_tf.value: macro.value,
            cfg.primary_structure_tf.value: primary.value,
            cfg.entry_confirmation_tf.value: entry.value,
            cfg.execution_management_tf.value: execution.value,
        }

        assessment = evaluate_mtf_v2(
            h4=macro,
            h1=primary,
            m15=entry,
            m5=execution,
            scalping=cfg.is_scalping(),
        )

        why = assessment.why
        sem_dict: dict[str, Any] = {}
        if semantics is not None:
            sem_dict = semantics.to_dict()
            why = f"{why} | M15 semantics: {semantics.new_classification.value} — {semantics.reason}"

        return TrendSnapshot(
            macro_bias=macro,
            primary=primary,
            entry=entry,
            execution=execution,
            alignment_score=int(assessment.alignment_score),
            aligned=bool(assessment.aligned),
            frames=frames,
            why=why,
            market_regime=assessment.regime,
            mtf_policy=assessment.policy,
            trade_bias=assessment.bias,
            mtf_contributions=dict(assessment.contributions),
            h4_is_context=bool(assessment.h4_is_context),
            m15_semantics=sem_dict,
        )
