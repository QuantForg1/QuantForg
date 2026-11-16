"""Account snapshot the worker sends with every execution authorization.

The backend runs the final owner guard on it (risk %, daily budget, RR,
spread, session, positions). Values come straight from the worker's own
MT5 session; nothing is estimated. Fields that cannot be read are left out,
and the backend then rejects the entry. Never contains credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

_TRADE_MODES = {0: "demo", 1: "contest", 2: "real"}


def _deal_row(deal: Any) -> dict[str, Any]:
    return {
        "ticket": int(getattr(deal, "ticket", 0) or 0),
        "time": int(getattr(deal, "time", 0) or 0),
        "type": int(getattr(deal, "type", -1)),
        "entry": int(getattr(deal, "entry", -1)),
        "volume": str(getattr(deal, "volume", 0) or 0),
        "profit": str(getattr(deal, "profit", 0) or 0),
        "commission": str(getattr(deal, "commission", 0) or 0),
        "swap": str(getattr(deal, "swap", 0) or 0),
        "fee": str(getattr(deal, "fee", 0) or 0),
    }


def build_account_snapshot(
    mt5: Any,
    symbol: str,
    *,
    now: datetime | None = None,
    verified_commission_usd: str | None = None,
) -> dict[str, Any]:
    """Read account, quote, positions and today's deals from the session."""
    moment = now or datetime.now(UTC)
    snap: dict[str, Any] = {"captured_at": moment.isoformat()}
    info = mt5.account_info()
    if info is not None:
        mode = _TRADE_MODES.get(int(getattr(info, "trade_mode", -1)))
        if mode:
            snap["trade_mode"] = mode
        snap["balance"] = str(info.balance)
        snap["equity"] = str(info.equity)
    tick = mt5.symbol_info_tick(symbol) if symbol else None
    if tick is not None and tick.bid and tick.ask:
        snap["bid"] = str(tick.bid)
        snap["ask"] = str(tick.ask)
    sym = mt5.symbol_info(symbol) if symbol else None
    if sym is not None and getattr(sym, "trade_contract_size", 0):
        snap["contract_size"] = str(sym.trade_contract_size)
    positions = mt5.positions_get()
    if positions is not None:
        snap["open_positions"] = len(positions)
    start = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
    deals = mt5.history_deals_get(start - timedelta(days=1), moment + timedelta(days=1))
    if deals is not None:
        snap["deals_today"] = [_deal_row(d) for d in deals]
    if verified_commission_usd is not None:
        snap["commission_source"] = "verified_account_tariff"
        snap["commission_usd"] = str(verified_commission_usd)
    return snap
