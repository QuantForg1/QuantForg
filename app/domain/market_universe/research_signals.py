"""Research signals — observational. Never LIVE_ORDER, never OMS."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    UNKNOWN,
)
from app.domain.market_universe.identity import canonical_desk


def _u(value: Any) -> Any:
    if value in (None, ""):
        return UNKNOWN
    return value


def build_research_signals(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Emit RESEARCH_SIGNAL rows from analyzed instruments only.

    Missing Opportunity stays UNKNOWN — no signal is invented as 0.
    """
    signals: list[dict[str, Any]] = []
    as_of = datetime.now(UTC).isoformat()
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        opp = row.get("opportunity_score")
        if not isinstance(opp, int):
            continue
        direction = str(row.get("direction") or "WAIT").upper()
        if direction not in {"BUY", "SELL", "WAIT"}:
            direction = "WAIT"
        reason = row.get("blocker") or row.get("direction_reason") or UNKNOWN
        if direction == "WAIT" and reason in (None, "", UNKNOWN):
            reason = "WAIT"
        canonical = canonical_desk(
            str(row.get("canonical_symbol") or row.get("symbol") or "")
        )
        features_as_of = _u(row.get("features_as_of") or as_of)
        identity = {
            "canonical_symbol": canonical,
            "direction": direction,
            "opportunity": opp,
            "edge": row.get("directional_edge"),
            "setup": row.get("setup_state"),
            "features_as_of": features_as_of,
        }
        decision_hash = hashlib.sha256(
            json.dumps(identity, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        evidence = (
            row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        )
        signals.append(
            {
                "kind": "RESEARCH_SIGNAL",
                "not": "LIVE_ORDER",
                "signal_id": f"RS-{decision_hash}",
                "decision_hash": decision_hash,
                "symbol": str(row.get("broker_symbol") or row.get("symbol") or ""),
                "canonical_symbol": canonical,
                "asset_class": _u(row.get("asset_class")),
                "direction": direction,
                "status": _u(row.get("board_status") or row.get("setup_state")),
                "board_status": _u(row.get("board_status")),
                "opportunity": opp,
                "opportunity_score": opp,
                "edge": _u(row.get("directional_edge")),
                "directional_edge": _u(row.get("directional_edge")),
                "research_rank_score": _u(row.get("research_rank_score")),
                "setup": _u(row.get("setup_state")),
                "setup_state": _u(row.get("setup_state")),
                "regime": _u(evidence.get("REGIME") or row.get("regime")),
                "market_regime": _u(evidence.get("REGIME") or row.get("regime")),
                "trend": _u(
                    evidence.get("STRUCTURE_EVIDENCE")
                    or row.get("structure_score")
                    or row.get("trend")
                ),
                "session": _u(row.get("session")),
                "entry_candidate": _u(
                    row.get("entry_candidate")
                    or row.get("entry")
                    or row.get("entry_price")
                ),
                "entry": _u(
                    row.get("entry_candidate")
                    or row.get("entry")
                    or row.get("entry_price")
                ),
                "stop_loss": _u(
                    row.get("SL_candidate")
                    or row.get("sl_candidate")
                    or row.get("stop_loss")
                    or row.get("sl")
                    or row.get("stop")
                ),
                "SL_candidate": _u(
                    row.get("SL_candidate")
                    or row.get("sl_candidate")
                    or row.get("stop_loss")
                    or row.get("sl")
                    or row.get("stop")
                ),
                "take_profit": _u(
                    row.get("TP_candidate")
                    or row.get("tp_candidate")
                    or row.get("take_profit")
                    or row.get("tp")
                    or row.get("target")
                ),
                "TP_candidate": _u(
                    row.get("TP_candidate")
                    or row.get("tp_candidate")
                    or row.get("take_profit")
                    or row.get("tp")
                    or row.get("target")
                ),
                "bid": _u(row.get("bid")),
                "ask": _u(row.get("ask")),
                "mid": _u(row.get("mid") or row.get("price")),
                "price": _u(
                    row.get("price")
                    or row.get("mid")
                    or row.get("last")
                    or row.get("last_price")
                ),
                "RR": _u(row.get("RR") or row.get("rr")),
                "risk_reward": _u(row.get("RR") or row.get("rr")),
                "spread": _u(row.get("spread")),
                "reason": reason,
                "evidence": evidence,
                "data_timestamp": _u(row.get("data_timestamp")),
                "analysis_timestamp": features_as_of,
                "features_as_of": features_as_of,
                "as_of": features_as_of,
                "freshness": _u(row.get("data_freshness") or row.get("freshness")),
                "reason_codes": (reason,),
                "timestamp": features_as_of,
                "quality": _u(row.get("quality") or row.get("market_quality")),
                "confidence": _u(row.get("confidence") or row.get("directional_edge")),
                "volatility": _u(
                    row.get("volatility")
                    or row.get("volatility_score")
                    or evidence.get("VOLATILITY")
                ),
                "timeframe": _u(row.get("timeframe") or row.get("primary_timeframe")),
                "data_quality": _u(
                    row.get("data_quality")
                    or row.get("data_state")
                    or row.get("data_freshness")
                ),
                "data_state": _u(row.get("data_state") or row.get("data_quality")),
                "strategy_version": _u(row.get("strategy_version")),
                "research_only": True,
                "live_eligible": False,
                "structure": _u(row.get("structure_score")),
                "structure_score": _u(row.get("structure_score")),
                "liquidity": _u(row.get("liquidity_score")),
                "liquidity_score": _u(row.get("liquidity_score")),
                "momentum": _u(
                    row.get("momentum_score") or evidence.get("MOMENTUM")
                ),
                "momentum_score": _u(row.get("momentum_score")),
                "volatility_score": _u(row.get("volatility_score")),
                "invalidation": _u(
                    row.get("invalidation") or evidence.get("INVALIDATION")
                ),
                "authorizes_trade": False,
                "would_submit_order": False,
                "forwarded_to_oms": False,
                "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
                "opportunity_is_not_profitability": True,
            }
        )
    return {
        "advisory_only": True,
        "kind": "RESEARCH_SIGNAL",
        "not": "LIVE_ORDER",
        "n": len(signals),
        "signals": signals,
        "would_submit_order": False,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": False,
        "forwarded_to_oms": False,
    }
