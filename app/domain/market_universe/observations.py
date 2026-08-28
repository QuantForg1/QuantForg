"""Process-local research observations. Not the live forensic ledger.

Observations are not fills, not STRATEGY_MATCHED, and not PnL.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.domain.market_universe.constants import UNKNOWN
from app.domain.market_universe.identity import canonical_desk

_LOCK = threading.Lock()
_OBS: deque[dict[str, Any]] = deque(maxlen=500)

RESEARCH_STAGES: tuple[str, ...] = (
    "DISCOVER",
    "CLASSIFY",
    "VALIDATE_DATA",
    "ANALYZE",
    "RANK",
    "GENERATE_RESEARCH_SIGNAL",
    "SHADOW",
    "COLLECT_EVIDENCE",
    "OOS",
    "WALK_FORWARD",
    "RISK_REVIEW",
    "HUMAN_AUTHORIZATION",
    "LIVE_PROMOTION",
)


def reset_observations_for_tests() -> None:
    with _LOCK:
        _OBS.clear()


def record_observations(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> int:
    as_of = datetime.now(UTC).isoformat()
    added = 0
    with _LOCK:
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            desk = canonical_desk(
                str(row.get("canonical_symbol") or row.get("symbol") or "")
            )
            if not desk:
                continue
            _OBS.append(
                {
                    "kind": "RESEARCH_OBSERVATION",
                    "not_a_fill": True,
                    "not_a_trade": True,
                    "not_strategy_matched": True,
                    "symbol": str(row.get("broker_symbol") or row.get("symbol") or ""),
                    "canonical_symbol": desk,
                    "asset_class": row.get("asset_class") or UNKNOWN,
                    "timestamp": as_of,
                    "market_data_status": row.get("data_state") or UNKNOWN,
                    "Opportunity": row.get("opportunity_score")
                    if isinstance(row.get("opportunity_score"), int)
                    else UNKNOWN,
                    "edge": row.get("directional_edge")
                    if isinstance(row.get("directional_edge"), int)
                    else UNKNOWN,
                    "direction": row.get("direction") or UNKNOWN,
                    "setup": row.get("setup_state") or UNKNOWN,
                    "regime": (row.get("evidence") or {}).get("REGIME") or UNKNOWN,
                    "session": row.get("session") or UNKNOWN,
                    "spread": row.get("spread")
                    if row.get("spread") not in (None, "")
                    else UNKNOWN,
                    "RR": row.get("RR") or row.get("rr") or UNKNOWN,
                    "entry_candidate": row.get("entry_candidate")
                    or row.get("entry")
                    or UNKNOWN,
                    "SL_candidate": row.get("sl_candidate") or row.get("sl") or UNKNOWN,
                    "TP_candidate": row.get("tp_candidate") or row.get("tp") or UNKNOWN,
                    "analysis_metadata": {
                        "board_status": row.get("board_status"),
                        "features_as_of": row.get("features_as_of"),
                    },
                }
            )
            added += 1
    return added


def list_observations(*, limit: int = 50) -> dict[str, Any]:
    with _LOCK:
        rows = list(_OBS)[-max(0, int(limit or 0)) :]
        n = len(_OBS)
    return {
        "advisory_only": True,
        "kind": "RESEARCH_OBSERVATION",
        "n": n,
        "returned": len(rows),
        "observations": rows,
        "counted_as_fills": False,
        "counted_as_strategy_matched": False,
        "hypothetical_pnl": False,
    }


def current_research_stage(
    *,
    catalogue_source: str,
    analyzed_n: int,
    signal_n: int,
    shadow_n: int,
    matched_n: int,
) -> dict[str, Any]:
    """Furthest completed research stage. LIVE_PROMOTION is never current."""
    src = str(catalogue_source or "")
    if src in {"UNAVAILABLE", "ERROR", ""}:
        stage = "DISCOVER"
    elif analyzed_n <= 0:
        stage = "VALIDATE_DATA"
    elif signal_n <= 0:
        stage = "ANALYZE"
    elif shadow_n <= 0:
        stage = "GENERATE_RESEARCH_SIGNAL"
    elif matched_n < 20:
        stage = "SHADOW"
    elif matched_n < 50:
        stage = "COLLECT_EVIDENCE"
    else:
        stage = "OOS"
    return {
        "stage": stage,
        "chain": list(RESEARCH_STAGES),
        "live_promotion_enabled": False,
        "skipped_to_live": False,
        "note": "LIVE_PROMOTION requires a later authorized phase.",
    }
