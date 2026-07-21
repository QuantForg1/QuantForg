"""Parameter Experiment Manager — sandbox only; never mutates production."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.strategy_research_lab.config import StrategyLabConfig


@dataclass(frozen=True, slots=True)
class ExperimentVariant:
    variant_id: str
    parameters: dict[str, Any]
    label: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "parameters": dict(self.parameters),
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    variant_id: str
    score: Decimal | None
    metrics: dict[str, object]
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "score": str(self.score) if self.score is not None else None,
            "metrics": dict(self.metrics),
            "notes": self.notes,
        }


@dataclass
class ParameterExperimentBatch:
    batch_id: str
    strategy_key: str
    created_at: datetime
    variants: list[ExperimentVariant] = field(default_factory=list)
    results: list[ExperimentResult] = field(default_factory=list)
    production_defaults_untouched: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "strategy_key": self.strategy_key,
            "created_at": self.created_at.isoformat(),
            "variants": [v.to_dict() for v in self.variants],
            "results": [r.to_dict() for r in self.results],
            "production_defaults_untouched": True,
            "lab_only": True,
        }


class ParameterExperimentManager:
    def __init__(self, config: StrategyLabConfig) -> None:
        self.config = config
        self._batches: dict[str, ParameterExperimentBatch] = {}

    def create_batch(
        self,
        *,
        strategy_key: str,
        variants: list[dict[str, Any]],
    ) -> dict[str, object]:
        batch_id = str(uuid4())
        capped = variants[: self.config.max_experiments_per_batch]
        parsed: list[ExperimentVariant] = []
        for i, row in enumerate(capped):
            params = row.get("parameters") if isinstance(row, dict) else None
            if not isinstance(params, dict):
                continue
            parsed.append(
                ExperimentVariant(
                    variant_id=str(row.get("variant_id") or f"v{i+1}"),
                    parameters=dict(params),
                    label=str(row.get("label") or f"variant-{i+1}"),
                )
            )
        batch = ParameterExperimentBatch(
            batch_id=batch_id,
            strategy_key=strategy_key,
            created_at=datetime.now(UTC),
            variants=parsed,
        )
        self._batches[batch_id] = batch
        return batch.to_dict()

    def record_results(
        self,
        *,
        batch_id: str,
        results: list[dict[str, Any]],
    ) -> dict[str, object] | None:
        batch = self._batches.get(batch_id)
        if not batch:
            return None
        parsed: list[ExperimentResult] = []
        for row in results:
            if not isinstance(row, dict):
                continue
            score_raw = row.get("score")
            score = None
            if score_raw is not None:
                try:
                    score = Decimal(str(score_raw))
                except Exception:
                    score = None
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
            parsed.append(
                ExperimentResult(
                    variant_id=str(row.get("variant_id") or ""),
                    score=score,
                    metrics=dict(metrics),
                    notes=str(row.get("notes") or ""),
                )
            )
        batch.results = parsed
        return batch.to_dict()

    def get_batch(self, batch_id: str) -> dict[str, object] | None:
        batch = self._batches.get(batch_id)
        return batch.to_dict() if batch else None

    def list_batches(
        self, *, strategy_key: str | None = None
    ) -> list[dict[str, object]]:
        rows = list(self._batches.values())
        if strategy_key:
            rows = [b for b in rows if b.strategy_key == strategy_key]
        rows.sort(key=lambda b: b.created_at, reverse=True)
        return [b.to_dict() for b in rows]
