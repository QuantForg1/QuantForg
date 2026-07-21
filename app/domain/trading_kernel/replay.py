"""Stage replay + deterministic replay mode."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.domain.trading_kernel.event_bus import KernelEvent, KernelEventBus


@dataclass(frozen=True, slots=True)
class ReplayResult:
    status: str
    mode: str
    trace_id: str
    stages: list[dict[str, Any]]
    input_hash: str | None
    deterministic: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "trace_id": self.trace_id,
            "stages": list(self.stages),
            "input_hash": self.input_hash,
            "deterministic": self.deterministic,
            "detail": self.detail,
            "never_order_send": True,
        }


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stage_replay(
    bus: KernelEventBus, *, trace_id: str, stage: str | None = None
) -> ReplayResult:
    events = bus.by_trace(trace_id)
    if not events:
        return ReplayResult(
            status="unavailable",
            mode="stage",
            trace_id=trace_id,
            stages=[],
            input_hash=None,
            deterministic=False,
            detail="No recorded events for trace_id — never invents replay",
        )
    rows = [e.to_dict() for e in events]
    if stage:
        rows = [r for r in rows if r.get("stage") == stage]
        if not rows:
            return ReplayResult(
                status="empty",
                mode="stage",
                trace_id=trace_id,
                stages=[],
                input_hash=None,
                deterministic=False,
                detail=f"No events for stage={stage}",
            )
    return ReplayResult(
        status="available",
        mode="stage",
        trace_id=trace_id,
        stages=rows,
        input_hash=None,
        deterministic=False,
        detail="Read-only stage replay from auditable event bus",
    )


def deterministic_replay(
    recorded_inputs: dict[str, Any],
    recorded_outputs: dict[str, Any],
    *,
    recompute_outputs: dict[str, Any],
) -> ReplayResult:
    in_hash = _hash_payload(recorded_inputs)
    match = _hash_payload(recorded_outputs) == _hash_payload(recompute_outputs)
    return ReplayResult(
        status="available" if match else "mismatch",
        mode="deterministic",
        trace_id=str(recorded_inputs.get("trace_id") or ""),
        stages=[
            {
                "recorded": recorded_outputs,
                "recomputed": recompute_outputs,
                "match": match,
            }
        ],
        input_hash=in_hash,
        deterministic=match,
        detail=(
            "Deterministic match on identical inputs"
            if match
            else "Outputs diverge — check config/input freeze"
        ),
    )


def freeze_cycle_record(
    *,
    trace_id: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    events: list[KernelEvent],
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "inputs": dict(inputs),
        "outputs": dict(outputs),
        "input_hash": _hash_payload(inputs),
        "output_hash": _hash_payload(outputs),
        "events": [e.to_dict() for e in events],
    }
