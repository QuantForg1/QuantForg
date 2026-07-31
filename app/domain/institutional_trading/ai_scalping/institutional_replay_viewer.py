"""Institutional Replay Viewer — format real completed-trade artefacts for NOC."""

from __future__ import annotations

from typing import Any


def format_institutional_replay(raw: dict[str, Any] | Any) -> dict[str, Any]:
    """Map a stored TradeReplay (dict or object) into the institutional viewer shape.

    Never fabricates pipeline / OMS / MT5 data — only surfaces what was recorded.
    """
    if hasattr(raw, "to_dict"):
        item = raw.to_dict()
    elif isinstance(raw, dict):
        item = dict(raw)
    else:
        item = {}

    frames = item.get("frames") if isinstance(item.get("frames"), list) else []
    market = (
        item.get("market_snapshot")
        if isinstance(item.get("market_snapshot"), dict)
        else {}
    )
    institutional = (
        market.get("institutional")
        if isinstance(market.get("institutional"), dict)
        else {}
    )

    timeline = []
    for f in frames:
        if isinstance(f, dict):
            timeline.append(
                {
                    "label": f.get("label"),
                    "at": f.get("at"),
                    "detail": f.get("detail"),
                    "price": f.get("price"),
                    "stop": f.get("stop"),
                    "tp": f.get("tp"),
                    "trail": f.get("trail"),
                }
            )

    close_reason = None
    for f in reversed(timeline):
        label = str(f.get("label") or "").upper()
        if label in {"EXIT", "CLOSE", "FLATTEN"}:
            close_reason = f.get("detail")
            break

    return {
        "id": item.get("id"),
        "ticket": item.get("ticket"),
        "symbol": item.get("symbol"),
        "direction": item.get("direction"),
        "created_at": item.get("created_at"),
        "ai_decision": item.get("ai_reasoning") or institutional.get("ai_decision"),
        "scanner_ranking": institutional.get("scanner_ranking")
        or market.get("scanner_ranking"),
        "pipeline": institutional.get("pipeline"),
        "execution_trace": institutional.get("execution_trace"),
        "risk_sizing": institutional.get("risk_sizing"),
        "oms": institutional.get("oms"),
        "mt5": institutional.get("mt5"),
        "management_timeline": timeline,
        "close_reason": close_reason or institutional.get("close_reason"),
        "entry": item.get("entry"),
        "exit": item.get("exit"),
        "sl": item.get("sl"),
        "tp": item.get("tp"),
        "structure": item.get("structure"),
        "liquidity": item.get("liquidity"),
        "bos": item.get("bos"),
        "choch": item.get("choch"),
        "fvg": item.get("fvg"),
        "order_blocks": item.get("order_blocks"),
        "fabricated": False,
        "source": "trade_replay_store",
    }


def list_institutional_replays(*, limit: int = 25) -> dict[str, Any]:
    """List formatted replays from the live trade replay store."""
    try:
        from app.domain.institutional_trading.performance_lab.trade_replay import (
            get_trade_replay_store,
        )

        raw_items = get_trade_replay_store().list(limit=limit)
        items = [
            format_institutional_replay(r)
            for r in raw_items
            if isinstance(r, (dict,)) or hasattr(r, "to_dict")
        ]
        return {
            "items": items,
            "count": len(items),
            "fabricated": False,
            "observe_only": True,
        }
    except Exception:
        return {"items": [], "count": 0, "fabricated": False, "observe_only": True}
