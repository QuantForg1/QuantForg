"""MTF Trend Engine — hierarchical bias from configured timeframes.

AI Decision Engine v2: regime-aware alignment via ``mtf_v2.evaluate_mtf_v2``.
H4 ranging is context (never a permanent veto). Quality/confidence floors
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import TrendSnapshot
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot


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
    ) -> TrendSnapshot:
        cfg = self.config
        macro = _dir_from_snapshot(structure_by_tf.get(cfg.macro_bias_tf))
        primary = _dir_from_snapshot(structure_by_tf.get(cfg.primary_structure_tf))
        entry = _dir_from_snapshot(structure_by_tf.get(cfg.entry_confirmation_tf))
        execution = _dir_from_snapshot(structure_by_tf.get(cfg.execution_management_tf))

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

        return TrendSnapshot(
            macro_bias=macro,
            primary=primary,
            entry=entry,
            execution=execution,
            alignment_score=int(assessment.alignment_score),
            aligned=bool(assessment.aligned),
            frames=frames,
            why=assessment.why,
            market_regime=assessment.regime,
            mtf_policy=assessment.policy,
            trade_bias=assessment.bias,
            mtf_contributions=dict(assessment.contributions),
            h4_is_context=bool(assessment.h4_is_context),
        )
