"""Research-universe scan — isolated from ITE / OMS / MT5 execution.

Reuses existing score_scalping_setup only when a caller injects a market
context. Default path never hits order_send and never writes ITE handoff.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
)
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.shadow_wall import ResearchExecutionBlocked

RESEARCH_SCAN_TAG = "RESEARCH_SHADOW"


def evaluate_injected_contexts(
    contexts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Score caller-supplied research contexts with the existing scorer.

    ``contexts`` items must already contain a ``score`` dict or precomputed
    fields. This function does not fetch MT5 data and does not submit orders.
    """
    if ALLOW_LIVE_PROMOTION:
        raise ResearchExecutionBlocked("ALLOW_LIVE_PROMOTION must stay false")
    rows: list[dict[str, Any]] = []
    for raw in contexts or ():
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or "")
        score = raw.get("score") if isinstance(raw.get("score"), dict) else raw
        buy = (
            score.get("buy_score")
            or score.get("core_buy")
            or score.get("bullish_score")
        )
        sell = (
            score.get("sell_score")
            or score.get("core_sell")
            or score.get("bearish_score")
        )
        ltf_buy = score.get("ltf_buy_score") or score.get("ltf_buy")
        ltf_sell = score.get("ltf_sell_score") or score.get("ltf_sell")
        direction = str(
            score.get("direction")
            or score.get("signal_action")
            or score.get("selected_side")
            or ""
        ).upper()
        if direction not in {"BUY", "SELL", "WAIT"}:
            direction = "WAIT"
        rows.append(
            {
                "symbol": symbol,
                "canonical_symbol": canonical_desk(symbol),
                "opportunity_score": score.get("opportunity_score"),
                "directional_edge": score.get("directional_edge"),
                "direction": direction,
                "selected_side": direction,
                "direction_reason": score.get("direction_reason")
                or score.get("setup_state")
                or "WAIT",
                "core_buy": buy,
                "core_sell": sell,
                "ltf_buy": ltf_buy,
                "ltf_sell": ltf_sell,
                "never_prefer_buy_only": True,
                "setup_state": score.get("setup_state"),
                "structure_score": score.get("structure_score"),
                "liquidity_score": score.get("liquidity_score"),
                "zone_score": score.get("zone_score"),
                "momentum_score": score.get("momentum_score"),
                "volatility_score": score.get("volatility_score"),
                "regime_score": score.get("regime_score"),
                "price_action_score": score.get("price_action_score"),
                "rr": score.get("rr") or score.get("expected_rr"),
                "spread": score.get("spread"),
                "market_session": score.get("market_session"),
                "market_regime": score.get("market_regime"),
                "first_authoritative_blocker": score.get("first_authoritative_blocker")
                or score.get("reject_reason"),
                "layer": RESEARCH_SCAN_TAG,
                "authorizes_trade": False,
                "forwarded_to_oms": False,
                "frozen_opportunity_threshold": FROZEN_OPPORTUNITY_THRESHOLD,
                "frozen_directional_edge": FROZEN_DIRECTIONAL_EDGE,
            }
        )
    return {
        "advisory_only": True,
        "layer": RESEARCH_SCAN_TAG,
        "authorizes_trade": False,
        "forwarded_to_oms": False,
        "ALLOW_LIVE_PROMOTION": False,
        "would_submit_order": False,
        "never_prefer_buy_only": True,
        "rows": rows,
        "n": len(rows),
    }


def score_injected_snapshots(
    items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Reuse score_scalping_setup as a library. Never ITE handoff / OMS.

    Each item must already contain a MarketAnalysisSnapshot under ``snapshot``.
    This function does not fetch MT5 and does not submit orders. One bad
    snapshot becomes ERROR; others continue.
    """
    if ALLOW_LIVE_PROMOTION:
        raise ResearchExecutionBlocked("ALLOW_LIVE_PROMOTION must stay false")
    from app.domain.institutional_trading.ai_scalping.scoring import (
        score_scalping_setup,
    )
    from app.domain.market_universe.concurrency import map_isolated

    def _one(item: dict[str, Any]) -> dict[str, Any]:
        snapshot = item.get("snapshot")
        if snapshot is None:
            raise ValueError("snapshot_required")
        verdict = score_scalping_setup(
            snapshot,
            atr=item.get("atr"),
            mid=item.get("mid"),
            symbol=str(item.get("symbol") or getattr(snapshot, "symbol", "") or ""),
            bid=item.get("bid"),
            ask=item.get("ask"),
            closes=item.get("closes"),
            opens=item.get("opens"),
            highs=item.get("highs"),
            lows=item.get("lows"),
        )
        payload = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
        payload["symbol"] = str(item.get("symbol") or payload.get("symbol") or "")
        payload["layer"] = RESEARCH_SCAN_TAG
        payload["authorizes_trade"] = False
        payload["forwarded_to_oms"] = False
        payload["would_submit_order"] = False
        return payload

    isolated = map_isolated(
        [i for i in (items or ()) if isinstance(i, dict)],
        _one,
    )
    scored = [
        r["result"]
        for r in isolated
        if r.get("ok") and isinstance(r.get("result"), dict)
    ]
    wrapped = evaluate_injected_contexts(scored)
    wrapped["errors"] = [r for r in isolated if not r.get("ok")]
    wrapped["forwarded_to_oms"] = False
    wrapped["would_submit_order"] = False
    return wrapped
