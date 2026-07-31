"""AI Decision Engine v2 — rejection telemetry + counterfactual.

Observation-grade records for every reject. Never mutates thresholds,
risk, OMS, or MT5. Never fabricates fills.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.mtf_v2 import (
    evaluate_mtf_v1_legacy,
    evaluate_mtf_v2,
)
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
class DecisionTelemetryStore:
    """In-memory + durable JSONL ring of rejection telemetry events."""

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
            self._path = base / "ai_decision_v2_telemetry.jsonl"

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
            logger.exception("decision_v2_telemetry_persist_failed")
        return row

    def recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(list(self._events)[-max(1, limit) :]))


_STORE: DecisionTelemetryStore | None = None
_LOCK = threading.Lock()


def get_decision_telemetry_store() -> DecisionTelemetryStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = DecisionTelemetryStore()
        return _STORE


def build_rejection_telemetry(
    *,
    trend: Any,
    quality_score: int | None,
    confidence_score: int | None,
    liquidity_score: int | None,
    liquidity_sources: list[str] | tuple[str, ...] | None = None,
    rejected_rules: list[str] | tuple[str, ...] | None = None,
    primary_reason: str | None = None,
    min_quality: int = 80,
    min_confidence: int = 80,
    scalping: bool = True,
    trace_id: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Build Phase-3 telemetry payload for one rejected (or evaluated) cycle."""
    h4 = _parse_dir(getattr(trend, "macro_bias", None) or getattr(trend, "h4", None))
    h1 = _parse_dir(getattr(trend, "primary", None) or getattr(trend, "h1", None))
    m15 = _parse_dir(getattr(trend, "entry", None) or getattr(trend, "m15", None))
    m5 = _parse_dir(getattr(trend, "execution", None) or getattr(trend, "m5", None))

    # Prefer live v2 fields when present on TrendSnapshot
    if getattr(trend, "mtf_contributions", None):
        contributions = dict(trend.mtf_contributions)
        regime = str(getattr(trend, "market_regime", "unknown"))
        v2_aligned = bool(getattr(trend, "aligned", False))
        v2_score = int(getattr(trend, "alignment_score", 0) or 0)
        h4_context = bool(getattr(trend, "h4_is_context", False))
    else:
        v2 = evaluate_mtf_v2(h4=h4, h1=h1, m15=m15, m5=m5, scalping=scalping)
        contributions = dict(v2.contributions)
        regime = v2.regime
        v2_aligned = v2.aligned
        v2_score = v2.alignment_score
        h4_context = v2.h4_is_context

    v1 = evaluate_mtf_v1_legacy(h4=h4, h1=h1, m15=m15, m5=m5, scalping=scalping)

    q = int(quality_score) if quality_score is not None else None
    c = int(confidence_score) if confidence_score is not None else None
    liq = int(liquidity_score) if liquidity_score is not None else None

    quality_pass = q is not None and q >= min_quality
    confidence_pass = c is not None and c >= min_confidence
    liquidity_pass_v2 = liq is not None and liq >= 65
    # Legacy liquidity: score 20 meant reject
    liquidity_pass_v1 = liq is not None and liq >= 65 and not (
        # If sources include only v2 expansions, legacy would have failed —
        # callers should pass liquidity_sources for accuracy.
        False
    )

    sources = [str(s) for s in (liquidity_sources or ())]
    legacy_liq_sources = {
        "liquidity_sweep",
        "liquidity_pool",
        "eqh",
        "eql",
        "legacy_liq",
    }
    if sources:
        liquidity_pass_v1 = bool(set(sources) & legacy_liq_sources)
        liquidity_pass_v2 = len(sources) > 0
    elif liq is not None:
        liquidity_pass_v1 = liq >= 65
        liquidity_pass_v2 = liq >= 65

    structural_v1 = bool(v1.aligned) and liquidity_pass_v1
    structural_v2 = bool(v2_aligned) and liquidity_pass_v2
    full_v1 = structural_v1 and quality_pass and confidence_pass
    full_v2 = structural_v2 and quality_pass and confidence_pass

    rules = [str(r) for r in (rejected_rules or ()) if str(r).strip()]
    primary = primary_reason or (rules[0] if rules else "unknown")

    return {
        "trace_id": trace_id,
        "symbol": symbol,
        "market_regime": regime,
        "h4_contribution": contributions.get("h4", contributions.get("macro_bias", 0)),
        "h1_contribution": contributions.get("h1", contributions.get("primary_structure", 0)),
        "m15_contribution": contributions.get(
            "m15", contributions.get("entry_confirmation", 0)
        ),
        "m5_contribution": contributions.get(
            "m5", contributions.get("execution_management", 0)
        ),
        "mtf_contributions": contributions,
        "h4_is_context": h4_context,
        "mtf_score_v2": v2_score,
        "mtf_aligned_v2": v2_aligned,
        "mtf_aligned_v1_legacy": bool(v1.aligned),
        "liquidity_contribution": liq,
        "liquidity_sources": sources,
        "quality_contribution": q,
        "confidence_contribution": c,
        "final_rejection_reason": primary,
        "rejected_rules": rules,
        "thresholds": {
            "min_quality": min_quality,
            "min_confidence": min_confidence,
            "quality_thresholds_reduced": False,
        },
        "counterfactual": {
            "would_pass_structural_v1": structural_v1,
            "would_pass_structural_v2": structural_v2,
            "would_pass_full_v1": full_v1,
            "would_pass_full_v2_redesigned_policy": full_v2,
            "false_negative_removed": (not structural_v1) and structural_v2,
            "note": (
                "Full pass still requires quality/confidence ≥ institutional floors; "
                "floors are not lowered."
            ),
        },
    }


def record_rejection_telemetry(**kwargs: Any) -> dict[str, Any]:
    payload = build_rejection_telemetry(**kwargs)
    return get_decision_telemetry_store().record(payload)
