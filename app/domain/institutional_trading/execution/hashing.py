"""Deterministic decision hashing for duplicate protection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.domain.institutional_trading.decision_models import TradeDecision


def compute_decision_hash(decision: TradeDecision) -> str:
    """Stable hash of decision content (excludes UUID id)."""

    payload: dict[str, Any] = {
        "input_hash": decision.input_hash,
        "action": decision.action.value,
        "direction": decision.direction.value,
        "confidence": decision.confidence,
        "quality": decision.quality,
        "risk_score": decision.risk_score,
        "approved_lots": (
            str(decision.approved_lots) if decision.approved_lots is not None else None
        ),
        "entry_zone": decision.entry_zone.to_dict() if decision.entry_zone else None,
        "stop_zone": decision.stop_zone.to_dict() if decision.stop_zone else None,
        "target_zone": decision.target_zone.to_dict() if decision.target_zone else None,
        "estimated_rr": (
            str(decision.estimated_rr) if decision.estimated_rr is not None else None
        ),
        "config_version": decision.config_version,
        "symbol": decision.symbol,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
