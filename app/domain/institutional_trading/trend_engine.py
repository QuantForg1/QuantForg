"""MTF Trend Engine — hierarchical bias from configured timeframes."""

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
        execution = _dir_from_snapshot(structure_by_tf.get(cfg.execution_management_tf))

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

        # Swing: bias from H4. Scalping: bias from H1 (macro remapped) — never require H4.
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

        # Conflict penalty: macro vs primary opposite
        if (
            macro in {TrendDirection.UP, TrendDirection.DOWN}
            and primary in {TrendDirection.UP, TrendDirection.DOWN}
            and macro != primary
        ):
            score = max(0, score - 25)

        if cfg.is_scalping():
            # Scalping: direction filter (H1) may stand without perfect structure lock.
            aligned = (
                bias in {TrendDirection.UP, TrendDirection.DOWN}
                and score >= 55
                and (
                    macro == primary
                    or primary in {TrendDirection.RANGE, TrendDirection.UNKNOWN}
                    or macro == entry
                )
            )
        else:
            aligned = (
                bias in {TrendDirection.UP, TrendDirection.DOWN}
                and macro == primary
                and macro in {TrendDirection.UP, TrendDirection.DOWN}
                and score >= 70
            )

        why = (
            f"MTF {bias.value}: {cfg.macro_bias_tf.value}={macro.value} "
            f"{cfg.primary_structure_tf.value}={primary.value} "
            f"{cfg.entry_confirmation_tf.value}={entry.value} "
            f"{cfg.execution_management_tf.value}={execution.value} "
            f"score={score}"
            + (" aligned" if aligned else " not aligned")
            + (" [scalping]" if cfg.is_scalping() else "")
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
