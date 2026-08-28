"""Live broker catalogue discovery for research.

Never invents symbols. Never treats a test fixture as LIVE_BROKER.
Does not fan out quotes (no N+1). One catalogue read only.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    CATALOGUE_CACHE,
    CATALOGUE_ERROR,
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_MOCK,
    CATALOGUE_UNAVAILABLE,
    UNKNOWN,
)
from core.logging import get_logger

logger = get_logger(__name__)

_MOCK_CLIENT_NAMES = frozenset({"MockMT5Client", "MockMT5Adapter"})


def _is_mock_adapter(mt5_adapter: Any | None) -> bool:
    if mt5_adapter is None:
        return False
    names = {type(mt5_adapter).__name__}
    client = getattr(mt5_adapter, "client", None) or getattr(
        mt5_adapter, "_client", None
    )
    if client is not None:
        names.add(type(client).__name__)
    return bool(names & _MOCK_CLIENT_NAMES)


def connection_trace(mt5_adapter: Any | None) -> dict[str, Any]:
    """Observability only. Never connects a second gateway process."""
    if mt5_adapter is None:
        return {
            "mt5_adapter_found": False,
            "gateway_found": False,
            "broker_connection_available": False,
            "symbol_discovery_function": UNKNOWN,
            "catalogue_source": CATALOGUE_UNAVAILABLE,
            "is_mock": False,
            "execution_enabled": False,
        }
    client = getattr(mt5_adapter, "client", None) or getattr(
        mt5_adapter, "_client", None
    )
    client_name = type(client).__name__ if client is not None else UNKNOWN
    gateway = client_name == "GatewayMT5Client"
    mock = _is_mock_adapter(mt5_adapter)
    discovery = UNKNOWN
    if hasattr(mt5_adapter, "symbols"):
        discovery = f"{type(mt5_adapter).__name__}.symbols"
    elif hasattr(mt5_adapter, "list_symbols"):
        discovery = f"{type(mt5_adapter).__name__}.list_symbols"
    exec_on = bool(getattr(mt5_adapter, "execution_enabled", False))
    return {
        "mt5_adapter_found": True,
        "gateway_found": gateway,
        "broker_connection_available": (not mock) and gateway,
        "symbol_discovery_function": discovery,
        "catalogue_source": CATALOGUE_UNAVAILABLE if mock else UNKNOWN,
        "is_mock": mock,
        "client_type": client_name,
        "execution_enabled": exec_on,
    }


def _flatten_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        row = dict(item)
        raw = row.get("raw")
        if isinstance(raw, dict):
            for key, value in raw.items():
                if row.get(key) in (None, ""):
                    row[key] = value
        code = str(
            row.get("code") or row.get("name") or row.get("symbol") or ""
        ).strip()
        if not code:
            return None
        row["code"] = code
        return row
    code = str(getattr(item, "code", None) or getattr(item, "name", "") or "").strip()
    if not code:
        return None
    row: dict[str, Any] = {"code": code}
    for attr in (
        "description",
        "digits",
        "point",
        "contract_size",
        "trade_mode",
        "volume_min",
        "volume_max",
        "volume_step",
        "currency_base",
        "currency_profit",
        "filling_mode",
        "execution_mode",
        "margin_calc_mode",
        "visible",
        "selected",
        "market_open",
        "trade_allowed",
        "stops_level",
        "freeze_level",
        "bid",
        "ask",
        "path",
        "category",
        "group",
    ):
        if hasattr(item, attr):
            value = getattr(item, attr)
            if value not in (None, ""):
                row[attr] = value
    raw = getattr(item, "raw", None)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if row.get(key) in (None, ""):
                row[key] = value
    return row


def discover_live_catalogue(mt5_adapter: Any | None) -> dict[str, Any]:
    """Read the connected broker catalogue. Empty if disconnected.

    ``catalogue_source`` is LIVE_BROKER only when the adapter returned rows.
    Fixtures must be passed separately as INJECTED and never labeled live.
    """
    if mt5_adapter is None:
        return {
            "catalogue_source": CATALOGUE_UNAVAILABLE,
            "rows": (),
            "count": 0,
            "error": "no_mt5_adapter",
            "invented": False,
            "quotes_fetched": False,
        }
    if _is_mock_adapter(mt5_adapter):
        return {
            "catalogue_source": CATALOGUE_UNAVAILABLE,
            "rows": (),
            "count": 0,
            "error": "mock_mt5_client_not_live_broker",
            "invented": False,
            "quotes_fetched": False,
            "populates_production_universe": False,
            "adapter_kind": CATALOGUE_MOCK,
        }
    listing = None
    source = CATALOGUE_LIVE_BROKER
    try:
        if hasattr(mt5_adapter, "symbols"):
            listing = mt5_adapter.symbols()
        elif hasattr(mt5_adapter, "list_symbols"):
            listing = mt5_adapter.list_symbols(include_quotes=False)
        else:
            return {
                "catalogue_source": CATALOGUE_UNAVAILABLE,
                "rows": (),
                "count": 0,
                "error": "adapter_has_no_symbols_api",
                "invented": False,
                "quotes_fetched": False,
            }
    except Exception as exc:
        logger.exception("live_broker_catalogue_fetch_failed")
        msg = str(exc)
        disconnected = any(
            needle in msg.lower()
            for needle in (
                "not connected",
                "unreachable",
                "credentials",
                "no_mt5",
            )
        )
        return {
            "catalogue_source": (
                CATALOGUE_UNAVAILABLE if disconnected else CATALOGUE_ERROR
            ),
            "rows": (),
            "count": 0,
            "error": msg[:200],
            "invented": False,
            "quotes_fetched": False,
        }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in listing or ():
        row = _flatten_item(item)
        if not row:
            continue
        code = str(row["code"]).upper()
        if code in seen:
            continue
        seen.add(code)
        rows.append(row)
    if not rows:
        return {
            "catalogue_source": CATALOGUE_UNAVAILABLE,
            "rows": (),
            "count": 0,
            "error": "empty_catalogue",
            "invented": False,
            "quotes_fetched": False,
        }
    return {
        "catalogue_source": source,
        "rows": tuple(rows),
        "count": len(rows),
        "error": None,
        "invented": False,
        "quotes_fetched": False,
        "sample": [r.get("code") for r in rows[:12]],
        "cache_hint": CATALOGUE_CACHE,
        "broker": UNKNOWN,
    }


def probe_timeframe_history(
    mt5_adapter: Any | None,
    symbols: list[str],
    *,
    max_symbols: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Bounded history probe. One bad symbol does not abort the rest."""
    from app.domain.market_universe.constants import (
        CONTEXT_TIMEFRAMES,
        HISTORY_CONTEXT_BARS,
        HISTORY_PROBE_BARS,
        MAX_HISTORY_PROBE_SYMBOLS,
        RESEARCH_TIMEFRAMES,
    )

    cap = max_symbols or MAX_HISTORY_PROBE_SYMBOLS
    out: dict[str, dict[str, Any]] = {}
    if mt5_adapter is None or _is_mock_adapter(mt5_adapter):
        return out
    if not hasattr(mt5_adapter, "copy_rates_from_pos"):
        return out
    try:
        from app.domain.market_data.timeframe import Timeframe
    except Exception:
        return out
    tf_map = {
        "M1": getattr(Timeframe, "M1", None),
        "M5": getattr(Timeframe, "M5", None),
        "M15": getattr(Timeframe, "M15", None),
        "H1": getattr(Timeframe, "H1", None),
        "H4": getattr(Timeframe, "H4", None),
        "D1": getattr(Timeframe, "D1", None),
    }
    probe_frames = tuple(RESEARCH_TIMEFRAMES) + tuple(CONTEXT_TIMEFRAMES)
    for symbol in list(symbols)[: max(0, cap)]:
        frames: dict[str, Any] = {}
        for name in probe_frames:
            tf = tf_map.get(name)
            bar_cap = (
                HISTORY_CONTEXT_BARS
                if name in CONTEXT_TIMEFRAMES
                else HISTORY_PROBE_BARS
            )
            if tf is None:
                frames[name] = {"error": True, "continuity": UNKNOWN}
                continue
            try:
                bars = mt5_adapter.copy_rates_from_pos(symbol, tf, 0, bar_cap)
                n = len(bars or [])
                latest = None
                if n:
                    last = bars[-1]
                    latest = getattr(last, "open_time", None) or getattr(
                        last, "time", None
                    )
                frames[name] = {
                    "bar_count": n,
                    "latest_bar_timestamp": latest,
                    "missing_bars": max(0, bar_cap - n) if n else UNKNOWN,
                    "continuity": "OK" if n >= bar_cap else "SHORT",
                    "error": False,
                    "role": "CONTEXT"
                    if name in CONTEXT_TIMEFRAMES
                    else "RESEARCH",
                }
            except Exception as exc:
                frames[name] = {
                    "error": True,
                    "continuity": "ERROR",
                    "reason": str(exc)[:160],
                }
        out[symbol] = frames
    return out


def probe_quotes(
    mt5_adapter: Any | None,
    symbols: list[str],
    *,
    max_symbols: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Bounded tick probe. One bad symbol does not abort the rest."""
    from app.domain.market_universe.constants import MAX_HISTORY_PROBE_SYMBOLS

    out: dict[str, dict[str, Any]] = {}
    if mt5_adapter is None or _is_mock_adapter(mt5_adapter):
        return out
    if not hasattr(mt5_adapter, "latest_tick"):
        return out
    cap = max_symbols or MAX_HISTORY_PROBE_SYMBOLS
    for symbol in list(symbols)[: max(0, cap)]:
        try:
            tick = mt5_adapter.latest_tick(symbol)
            bid = getattr(tick, "bid", None)
            ask = getattr(tick, "ask", None)
            ts = getattr(tick, "time", None) or getattr(tick, "time_msc", None)
            spread = None
            try:
                if bid is not None and ask is not None:
                    spread = float(ask) - float(bid)
            except (TypeError, ValueError):
                spread = None
            out[symbol] = {
                "bid": bid,
                "ask": ask,
                "last_quote_timestamp": ts,
                "spread": spread,
                "error": False,
            }
        except Exception as exc:
            out[symbol] = {
                "error": True,
                "fetch_error": True,
                "reason": str(exc)[:160],
            }
    return out
