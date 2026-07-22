"""Institutional Replay & Evidence Lab — advisory only.

Never modifies strategy, risk, safety, execution, or Performance Intelligence.
Never fabricates metrics. Never mixes Live / Demo / Replay / Research lanes.
"""

from __future__ import annotations

from app.domain.replay_evidence_lab.confidence import (
    build_confidence_report,
    confidence_level,
    score_kpi,
)
from app.domain.replay_evidence_lab.counterfactual import (
    analyze_no_trade_counterfactuals,
    evaluate_counterfactual,
)
from app.domain.replay_evidence_lab.evidence_store import (
    EvidenceDatabase,
    get_evidence_database,
)
from app.domain.replay_evidence_lab.gates import (
    evaluate_evidence_gates,
    merge_thresholds,
)
from app.domain.replay_evidence_lab.lab import build_replay_evidence_lab
from app.domain.replay_evidence_lab.models import (
    DEFAULT_EVIDENCE_THRESHOLDS,
    EVIDENCE_LANES,
    HARD_LOCKS,
)
from app.domain.replay_evidence_lab.replay import record_opportunity, run_replay

__all__ = [
    "DEFAULT_EVIDENCE_THRESHOLDS",
    "EVIDENCE_LANES",
    "HARD_LOCKS",
    "EvidenceDatabase",
    "analyze_no_trade_counterfactuals",
    "build_confidence_report",
    "build_replay_evidence_lab",
    "confidence_level",
    "evaluate_counterfactual",
    "evaluate_evidence_gates",
    "get_evidence_database",
    "merge_thresholds",
    "record_opportunity",
    "run_replay",
    "score_kpi",
]
