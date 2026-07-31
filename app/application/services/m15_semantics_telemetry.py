"""M15 Trend Semantics v2 — observe-only telemetry.

Records previous vs new classification, reason, and MTF counterfactual.
Never mutates thresholds, risk, OMS, or MT5.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.m15_semantics_v2 import (
    classify_m15_semantics_from_cycle_evidence,
)
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2
from app.domain.market_structure.enums import TrendDirection
from core.logging import get_logger

logger = get_logger(__name__)

_DIR = {
    "up": TrendDirection.UP,
    "down": TrendDirection.DOWN,
    "range": TrendDirection.RANGE,
    "unknown": TrendDirection.UNKNOWN,
}


def _parse_dir(value: Any) -> TrendDirection:
    if isinstance(value, TrendDirection):
        return value
    return _DIR.get(str(value or "unknown").lower(), TrendDirection.UNKNOWN)


@dataclass
class M15SemanticsTelemetryStore:
    maxlen: int = 2000
    _events: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._events = deque(maxlen=self.maxlen)
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "m15_semantics_v2_telemetry.jsonl"

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        row = dict(event)
        row.setdefault("recorded_at", datetime.now(UTC).isoformat())
        row["advisory_only"] = True
        row["thresholds_changed"] = False
        with self._lock:
            self._events.append(row)
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
        except Exception:
            logger.exception("m15_semantics_telemetry_persist_failed")
        return row

    def recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(list(self._events)[-max(1, limit) :]))


_STORE: M15SemanticsTelemetryStore | None = None
_LOCK = threading.Lock()


def get_m15_semantics_telemetry_store() -> M15SemanticsTelemetryStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = M15SemanticsTelemetryStore()
        return _STORE


def build_m15_semantics_telemetry(
    *,
    h4: Any,
    h1: Any,
    m15: Any,
    m5: Any,
    latest_bos: Any = None,
    has_ob: bool = False,
    has_fvg: bool = False,
    has_bos: bool = False,
    choch_opposes_bias: bool = False,
    quality_score: int | None = None,
    confidence_score: int | None = None,
    min_quality: int = 80,
    min_confidence: int = 80,
    scalping: bool = True,
    trace_id: str | None = None,
    symbol: str | None = None,
    live_semantics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build telemetry + counterfactual for one cycle."""
    h4_d, h1_d, m15_d, m5_d = (
        _parse_dir(h4),
        _parse_dir(h1),
        _parse_dir(m15),
        _parse_dir(m5),
    )
    bos_d = _parse_dir(latest_bos) if latest_bos not in (None, "", "—") else None
    if bos_d is TrendDirection.UNKNOWN:
        bos_d = None

    if live_semantics:
        semantics = live_semantics
        effective_m15 = _parse_dir(semantics.get("effective_direction"))
    else:
        sem = classify_m15_semantics_from_cycle_evidence(
            h1_direction=h1_d,
            m15_direction=m15_d,
            latest_bos_direction=bos_d,
            has_ob=has_ob,
            has_fvg=has_fvg,
            has_bos=has_bos or bos_d is not None,
            choch_opposes_bias=choch_opposes_bias,
        )
        semantics = sem.to_dict()
        effective_m15 = sem.effective_direction

    before = evaluate_mtf_v2(h4=h4_d, h1=h1_d, m15=m15_d, m5=m5_d, scalping=scalping)
    # Counterfactual: semantics effective M15; M5 still present but not required
    after = evaluate_mtf_v2(
        h4=h4_d, h1=h1_d, m15=effective_m15, m5=m5_d, scalping=scalping
    )

    q_ok = quality_score is not None and int(quality_score) >= min_quality
    c_ok = confidence_score is not None and int(confidence_score) >= min_confidence

    return {
        "advisory_only": True,
        "thresholds_changed": False,
        "trace_id": trace_id,
        "symbol": symbol,
        "previous_m15_classification": semantics.get("previous_classification"),
        "new_classification": semantics.get("new_classification"),
        "reason": semantics.get("reason"),
        "m15_semantics": semantics,
        "frames": {
            "h4": h4_d.value,
            "h1": h1_d.value,
            "m15_raw": m15_d.value,
            "m15_effective": effective_m15.value,
            "m5": m5_d.value,
        },
        "counterfactual": {
            "mtf_aligned_before": bool(before.aligned),
            "mtf_score_before": int(before.alignment_score),
            "mtf_aligned_after": bool(after.aligned),
            "mtf_score_after": int(after.alignment_score),
            "mtf_policy_after": after.policy,
            "alignment_gained": bool(after.aligned and not before.aligned),
            "full_gate_opportunity_after": bool(after.aligned and q_ok and c_ok),
            "quality_pass": q_ok,
            "confidence_pass": c_ok,
            "min_quality": min_quality,
            "min_confidence": min_confidence,
        },
        "m5_execution_only": True,
    }
