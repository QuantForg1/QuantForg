"""Application service — Institutional Replay & Evidence Lab (advisory)."""

from __future__ import annotations

from typing import Any

from app.domain.replay_evidence_lab.evidence_store import (
    EvidenceDatabase,
    get_evidence_database,
)
from app.domain.replay_evidence_lab.lab import build_replay_evidence_lab


def run_replay_evidence_lab(
    *,
    bars: list[dict[str, Any]] | None = None,
    opportunities: list[dict[str, Any]] | None = None,
    live_closed_trades: list[dict[str, Any]] | None = None,
    demo_records: list[dict[str, Any]] | None = None,
    research_records: list[dict[str, Any]] | None = None,
    thresholds: dict[str, Any] | None = None,
    use_process_store: bool = False,
) -> dict[str, Any]:
    """Run the lab pack. Never mutates strategy / risk / safety / execution."""
    db: EvidenceDatabase | None = (
        get_evidence_database() if use_process_store else EvidenceDatabase()
    )
    return build_replay_evidence_lab(
        bars=bars,
        opportunities=opportunities,
        live_closed_trades=live_closed_trades,
        demo_records=demo_records,
        research_records=research_records,
        thresholds=thresholds,
        database=db,
    )
