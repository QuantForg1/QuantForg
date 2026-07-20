"""MTF Trend Engine — H4 macro · H1 primary · M15 entry · M5 execution."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import TrendSnapshot
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot

# Approved weights: macro + primary dominate
_WEIGHTS: dict[str, int] = {
    "macro_bias": 40,
    "primary_structure": 30,
    "entry_confirmation": 20,
    "execution_management": 10,
}


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
        execution = _dir_from_snapshot(
            structure_by_tf.get(cfg.execution_management_tf)
        )

        frames = {
            cfg.macro_bias_tf.value: macro.value,
            cfg.primary_structure_tf.value: primary.value,
            cfg.entry_confirmation_tf.value: entry.value,
            cfg.execution_management_tf.value: execution.value,
        }

        role_dirs = {
            "macro_bias": macro,
            "primary_structure": primary,
            "entry_confirmation": entry,
            "execution_management": execution,
        }

        # Choose bias from H4; require H1 agreement for alignment
        bias = macro
        if bias in {TrendDirection.UNKNOWN, TrendDirection.RANGE}:
            bias = primary

        score = 0
        if bias in {TrendDirection.UP, TrendDirection.DOWN}:
            for role, direction in role_dirs.items():
                w = _WEIGHTS[role]
                if direction == bias:
                    score += w
                elif direction in {TrendDirection.RANGE, TrendDirection.UNKNOWN}:
                    score += w // 4
                # opposite direction → 0 for that weight

        # Conflict penalty: H4 vs H1 opposite
        if (
            macro in {TrendDirection.UP, TrendDirection.DOWN}
            and primary in {TrendDirection.UP, TrendDirection.DOWN}
            and macro != primary
        ):
            score = max(0, score - 25)

        aligned = (
            bias in {TrendDirection.UP, TrendDirection.DOWN}
            and macro == primary
            and macro in {TrendDirection.UP, TrendDirection.DOWN}
            and score >= 70
        )

        why = (
            f"MTF {bias.value}: H4={macro.value} H1={primary.value} "
            f"M15={entry.value} M5={execution.value} score={score}"
            + (" aligned" if aligned else " not aligned")
        )

        return TrendSnapshot(
            macro_bias=macro,
            primary=primary,
            entry=entry,
            execution=execution,
            alignment_score=int(score),
            aligned=aligned,
            frames=frames,
            why=why,
        )
