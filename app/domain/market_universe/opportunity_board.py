"""Global opportunity board — RESEARCH / DISCOVERY ranking only.

A ranked row is never an authorization to trade. Live gold still must
clear CORE → Sniper → Risk → Safety → OMS. Missing scores stay UNKNOWN
rather than 0.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.classification import classify_or_unknown
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_UNAVAILABLE,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
)
from app.domain.market_universe.identity import canonical_desk, same_economic_instrument
from app.domain.market_universe.opportunity_tiers import research_opportunity_tier
from app.domain.market_universe.promotion import (
    capability_state,
    research_board_status,
)
from app.domain.market_universe.ranking import UNRANKABLE_STATES, compute_research_rank
from app.domain.market_universe.regime_research import normalize_research_regime
from app.domain.trading.gold_only import is_gold_symbol


def _as_int(value: Any) -> int | None:
    if value in (None, "", UNKNOWN):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value in (None, "", UNKNOWN):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_or_unknown(value: Any) -> int | str:
    n = _as_int(value)
    return n if n is not None else UNKNOWN


def _direction(row: dict[str, Any]) -> str:
    raw = (
        str(
            row.get("direction")
            or row.get("signal_action")
            or row.get("candidate")
            or row.get("decision_action")
            or ""
        )
        .strip()
        .upper()
    )
    if raw in {"BUY", "SELL", "WAIT"}:
        return raw
    if "BUY" in raw or raw == "LONG":
        return "BUY"
    if "SELL" in raw or raw == "SHORT":
        return "SELL"
    return UNKNOWN


def _quote_number(value: Any) -> float | str:
    n = _as_float(value)
    return n if n is not None else UNKNOWN


def _mid_from_quotes(*values: Any) -> float | str:
    nums = [_as_float(v) for v in values]
    present = [n for n in nums if n is not None and n > 0]
    if len(present) >= 2:
        return (present[0] + present[1]) / 2.0
    if len(present) == 1:
        return present[0]
    return UNKNOWN


def project_opportunity_row(
    row: dict[str, Any],
    *,
    registry_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol = str(row.get("symbol") or row.get("broker_symbol") or "")
    desk = canonical_desk(symbol)
    asset = str(
        (registry_item or {}).get("asset_class")
        or row.get("asset_class")
        or classify_or_unknown(symbol)
    )
    dq = (
        (registry_item or {}).get("data_quality")
        if registry_item
        else row.get("data_quality")
    )
    if not isinstance(dq, dict):
        dq = {}
    state = str(dq.get("state") or row.get("data_state") or UNKNOWN)
    opp = _score_or_unknown(row.get("opportunity_score"))
    if state in {
        "NO_DATA",
        "STALE",
        "MARKET_CLOSED",
        "DISABLED",
        "UNSUPPORTED",
        "INSUFFICIENT_HISTORY",
        "ERROR",
        "UNKNOWN",
    }:
        # Never convert unavailable data into a numeric zero opportunity.
        if opp == 0 and row.get("opportunity_score") in (None, "", UNKNOWN):
            opp = UNKNOWN
        if row.get("opportunity_score") in (None, "", UNKNOWN):
            opp = UNKNOWN
    edge = _score_or_unknown(
        row.get("directional_edge")
        or row.get("edge")
        or row.get("edge_margin_observed")
    )
    why = {
        "WHY_THIS_MARKET": row.get("why_this_market")
        or (f"scored {desk} in {asset}" if desk else UNKNOWN),
        "WHY_THIS_DIRECTION": row.get("why_this_direction")
        or str(row.get("direction_reason") or row.get("setup_state") or UNKNOWN),
        "WHY_NOW": row.get("why_now")
        or str(
            row.get("first_authoritative_blocker") or row.get("setup_state") or UNKNOWN
        ),
        "STRUCTURE_EVIDENCE": _score_or_unknown(row.get("structure_score")),
        "LIQUIDITY_EVIDENCE": _score_or_unknown(row.get("liquidity_score")),
        "ZONE_EVIDENCE": _score_or_unknown(row.get("zone_score")),
        "MOMENTUM": _score_or_unknown(row.get("momentum_score")),
        "VOLATILITY": _score_or_unknown(row.get("volatility_score")),
        "REGIME": normalize_research_regime(
            row.get("market_regime") or row.get("regime")
        ),
        "RR": row.get("rr") or row.get("expected_rr") or UNKNOWN,
        "RISK_CONDITIONS": row.get("risk_conditions")
        or "Risk engine not invoked by this board",
        "BLOCKERS": row.get("first_authoritative_blocker")
        or row.get("blocking_gate")
        or row.get("reject_reason")
        or UNKNOWN,
        "DATA_FRESHNESS": dq.get("quote_freshness") or row.get("freshness") or UNKNOWN,
    }
    reg = registry_item or {}
    bid = _quote_number(
        row.get("bid") if row.get("bid") not in (None, "", UNKNOWN) else reg.get("bid")
    )
    ask = _quote_number(
        row.get("ask") if row.get("ask") not in (None, "", UNKNOWN) else reg.get("ask")
    )
    mid = _quote_number(row.get("mid") or row.get("price"))
    if mid is UNKNOWN:
        mid = _mid_from_quotes(bid, ask)
    entry = row.get("entry_candidate") or row.get("entry") or row.get("entry_price")
    stop = (
        row.get("SL_candidate")
        or row.get("sl_candidate")
        or row.get("stop_loss")
        or row.get("sl")
        or row.get("stop")
    )
    take = (
        row.get("TP_candidate")
        or row.get("tp_candidate")
        or row.get("take_profit")
        or row.get("tp")
        or row.get("target")
    )
    projected = {
        "symbol": symbol or desk,
        "canonical_symbol": desk,
        "broker_symbol": str(row.get("broker_symbol") or symbol),
        "asset_class": asset,
        "direction": _direction(row),
        "selected_side": _direction(row),
        "core_buy": _score_or_unknown(
            row.get("core_buy") or row.get("buy_score")
        ),
        "core_sell": _score_or_unknown(
            row.get("core_sell") or row.get("sell_score")
        ),
        "ltf_buy": _score_or_unknown(row.get("ltf_buy") or row.get("ltf_buy_score")),
        "ltf_sell": _score_or_unknown(
            row.get("ltf_sell") or row.get("ltf_sell_score")
        ),
        "never_prefer_buy_only": True,
        "opportunity_score": opp,
        "directional_edge": edge,
        "setup_state": row.get("setup_state") or row.get("sniper_state") or UNKNOWN,
        "structure_score": _score_or_unknown(row.get("structure_score")),
        "liquidity_score": _score_or_unknown(row.get("liquidity_score")),
        "zone_score": _score_or_unknown(row.get("zone_score")),
        "momentum_score": _score_or_unknown(row.get("momentum_score")),
        "volatility_score": _score_or_unknown(row.get("volatility_score")),
        "regime_score": _score_or_unknown(row.get("regime_score")),
        "price_action_score": _score_or_unknown(row.get("price_action_score")),
        "RR": row.get("rr") or row.get("expected_rr") or UNKNOWN,
        "spread": row.get("spread") if row.get("spread") not in (None, "") else UNKNOWN,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "price": mid if mid is not UNKNOWN else UNKNOWN,
        "entry": entry if entry not in (None, "", UNKNOWN) else UNKNOWN,
        "entry_candidate": entry if entry not in (None, "", UNKNOWN) else UNKNOWN,
        "stop_loss": stop if stop not in (None, "", UNKNOWN) else UNKNOWN,
        "SL_candidate": stop if stop not in (None, "", UNKNOWN) else UNKNOWN,
        "sl_candidate": stop if stop not in (None, "", UNKNOWN) else UNKNOWN,
        "take_profit": take if take not in (None, "", UNKNOWN) else UNKNOWN,
        "TP_candidate": take if take not in (None, "", UNKNOWN) else UNKNOWN,
        "tp_candidate": take if take not in (None, "", UNKNOWN) else UNKNOWN,
        "session": row.get("market_session")
        or row.get("session")
        or (registry_item or {}).get("trading_sessions")
        or UNKNOWN,
        "timestamp": row.get("as_of")
        or row.get("timestamp")
        or row.get("recorded_at")
        or UNKNOWN,
        "data_freshness": dq.get("quote_freshness") or row.get("freshness") or UNKNOWN,
        "data_state": state,
        "blocker": why["BLOCKERS"],
        "confidence_state": row.get("confidence_state")
        or row.get("ai_confidence")
        or UNKNOWN,
        "evidence": why,
        "sort_rank_is_not_authorization": True,
        "authorizes_trade": False,
        "live_execution_eligible": False,
        "must_still_pass": (
            "CORE",
            "Sniper",
            "Risk",
            "Safety",
            "OMS",
        ),
        "frozen_opportunity_threshold": FROZEN_OPPORTUNITY_THRESHOLD,
        "frozen_directional_edge": FROZEN_DIRECTIONAL_EDGE,
        "frozen_min_rr": FROZEN_MIN_RR,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "is_xauusd_reference": is_gold_symbol(symbol or desk),
        "same_as_xauusd": same_economic_instrument(symbol, "XAUUSD"),
        "board_status": None,  # set below
        "qualified_research": False,
        "capability_state": "DISCOVERED",
        "LIVE_ELIGIBLE": False,
        "opportunity_tier": research_opportunity_tier(opp),
        "opportunity_tier_is_display_only": True,
        "features_as_of": row.get("features_as_of")
        or row.get("as_of")
        or row.get("timestamp")
        or UNKNOWN,
        "market_timestamp": row.get("market_timestamp")
        or row.get("bar_time")
        or UNKNOWN,
        "data_timestamp": row.get("data_timestamp")
        or dq.get("last_quote_timestamp")
        or row.get("last_quote_timestamp")
        or UNKNOWN,
        "research_status_label": "RESEARCH / NOT A TRADE AUTHORIZATION",
    }
    status = research_board_status(
        data_state=state,
        opportunity=opp if isinstance(opp, int) else None,
        edge=edge if isinstance(edge, int) else None,
        direction=_direction(row),
        has_score=isinstance(opp, int),
    )
    projected["board_status"] = status
    projected["qualified_research"] = status == "QUALIFIED"
    projected["capability_state"] = capability_state(status)
    projected["LIVE_ELIGIBLE"] = False
    rank = compute_research_rank(projected)
    projected.update(rank)
    return projected


def _sort_key(row: dict[str, Any]) -> tuple[float, int, int, str]:
    rank = row.get("research_rank_score")
    rank_n = rank if isinstance(rank, (int, float)) else -1.0
    opp = row.get("opportunity_score")
    edge = row.get("directional_edge")
    opp_n = opp if isinstance(opp, int) else -1
    edge_n = edge if isinstance(edge, int) else -1
    return (float(rank_n), opp_n, edge_n, str(row.get("canonical_symbol") or ""))


def _group_top(
    rows: list[dict[str, Any]], key: str, *, n: int = 5
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if key == "regime":
            label = str((row.get("evidence") or {}).get("REGIME") or UNKNOWN)
        else:
            label = str(row.get(key) or UNKNOWN)
        buckets.setdefault(label, []).append(row)
    return {k: v[:n] for k, v in sorted(buckets.items())}


def build_opportunity_board(
    scored_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    registry_by_desk: dict[str, dict[str, Any]] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank scored research/live-scan rows for display only."""
    index = registry_by_desk or {}
    projected: list[dict[str, Any]] = []
    for raw in scored_rows or ():
        if not isinstance(raw, dict) or not (
            raw.get("symbol") or raw.get("broker_symbol")
        ):
            continue
        desk = canonical_desk(str(raw.get("symbol") or raw.get("broker_symbol")))
        projected.append(project_opportunity_row(raw, registry_item=index.get(desk)))

    filt = filters or {}
    asset = str(filt.get("asset_class") or "").strip().upper()
    symbol = str(filt.get("symbol") or "").strip()
    direction = str(filt.get("direction") or "").strip().upper()
    session = str(filt.get("session") or "").strip().upper()
    regime = str(filt.get("regime") or "").strip().upper()
    min_opp = _as_int(filt.get("min_opportunity"))
    min_edge = _as_int(filt.get("min_edge"))
    min_rr = _as_float(filt.get("min_rr"))
    freshness = str(filt.get("data_freshness") or "").strip().upper()
    setup = str(filt.get("setup") or "").strip().upper()
    data_status = str(
        filt.get("data_status") or filt.get("data_state") or ""
    ).strip()
    data_status = data_status.upper()

    def _keep(row: dict[str, Any]) -> bool:
        if asset and str(row.get("asset_class") or "").upper() != asset:
            return False
        if symbol and canonical_desk(symbol) != row.get("canonical_symbol"):
            return False
        if (
            direction
            and direction not in {"ALL", "*"}
            and str(row.get("direction")) != direction
        ):
            return False
        if session and session not in str(row.get("session") or "").upper():
            return False
        if (
            regime
            and regime
            not in str((row.get("evidence") or {}).get("REGIME") or "").upper()
        ):
            return False
        if min_opp is not None:
            opp = row.get("opportunity_score")
            if not isinstance(opp, int) or opp < min_opp:
                return False
        if min_edge is not None:
            edge = row.get("directional_edge")
            if not isinstance(edge, int) or edge < min_edge:
                return False
        if min_rr is not None:
            rr = _as_float(row.get("RR"))
            if rr is None or rr < min_rr:
                return False
        if freshness and freshness not in str(row.get("data_freshness") or "").upper():
            return False
        if (
            data_status
            and data_status not in {"ALL", "*"}
            and str(row.get("data_state") or "").upper() != data_status
        ):
            return False
        return not (setup and setup not in str(row.get("setup_state") or "").upper())

    filtered = [r for r in projected if _keep(r)]
    for row in filtered:
        status = str(row.get("board_status") or "DISCOVERED")
        row["qualified_research"] = status == "QUALIFIED"
        row["authorizes_trade"] = False
        row["live_execution_eligible"] = False
    ranked_all = sorted(filtered, key=_sort_key, reverse=True)
    live_ranked = [
        r
        for r in ranked_all
        if str(r.get("data_state") or "") not in UNRANKABLE_STATES
        and isinstance(r.get("opportunity_score"), int)
        and r.get("rankable") is True
    ]
    ranked = live_ranked
    buys = [r for r in ranked if r.get("direction") == "BUY"]
    sells = [r for r in ranked if r.get("direction") == "SELL"]
    waits = [r for r in ranked if r.get("direction") == "WAIT"]
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "ranking_is_research_only": True,
        "ranks_live_data_only": True,
        "ALLOW_LIVE_PROMOTION": False,
        "frozen_opportunity_threshold": FROZEN_OPPORTUNITY_THRESHOLD,
        "frozen_directional_edge": FROZEN_DIRECTIONAL_EDGE,
        "rows": ranked_all,
        "live_ranked": ranked,
        "discovered_not_ranked": [
            r
            for r in ranked_all
            if str(r.get("data_state") or "") in UNRANKABLE_STATES
        ],
        "top_opportunities": ranked[:20],
        "top_buy": buys[:20],
        "top_sell": sells[:20],
        "top_wait": waits[:20],
        "top_by_asset_class": _group_top(ranked, "asset_class"),
        "top_by_session": _group_top(ranked, "session"),
        "top_by_regime": _group_top(ranked, "regime"),
        "top_directional_edges": sorted(
            [r for r in ranked if isinstance(r.get("directional_edge"), int)],
            key=lambda r: int(r.get("directional_edge") or -1),
            reverse=True,
        )[:20],
        "never_prefer_buy_only": True,
        "n": len(ranked_all),
        "n_live_ranked": len(ranked),
        "n_buy": len(buys),
        "n_sell": len(sells),
        "n_wait": len(waits),
        "n_unknown_direction": sum(
            1 for r in ranked_all if r.get("direction") == UNKNOWN
        ),
        "n_unknown_opportunity": sum(
            1 for r in ranked_all if r.get("opportunity_score") == UNKNOWN
        ),
        "research_status_label": "RESEARCH / NOT A TRADE AUTHORIZATION",
    }


def global_opportunity_now(
    *,
    catalogue_source: str,
    live_ranked: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Best current RESEARCH signal. Never a trade authorization.

    Unavailable catalogues are UNAVAILABLE, not a numeric zero board.
    """
    source = str(catalogue_source or "")
    base = {
        "label": "GLOBAL OPPORTUNITY",
        "not": "GUARANTEED_BEST_TRADE",
        "authorizes_trade": False,
        "live_eligible": False,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "fabricated": False,
        "opportunity_is_not_profitability": True,
    }
    if source != CATALOGUE_LIVE_BROKER:
        status = CATALOGUE_UNAVAILABLE
        return {
            **base,
            "status": status,
            "value": status,
            "row": None,
            "catalogue_source": source,
        }
    ranked = [r for r in (live_ranked or ()) if isinstance(r, dict)]
    if not ranked:
        return {
            **base,
            "status": INSUFFICIENT_SAMPLE,
            "value": INSUFFICIENT_SAMPLE,
            "row": None,
            "catalogue_source": source,
        }
    top = ranked[0]
    return {
        **base,
        "status": "BEST_CURRENT_RESEARCH_SIGNAL",
        "value": top.get("opportunity_score")
        if isinstance(top.get("opportunity_score"), int)
        else UNKNOWN,
        "symbol": top.get("broker_symbol") or top.get("symbol"),
        "canonical_symbol": top.get("canonical_symbol"),
        "asset_class": top.get("asset_class"),
        "direction": top.get("direction"),
        "edge": top.get("directional_edge"),
        "row": top,
        "catalogue_source": source,
    }
