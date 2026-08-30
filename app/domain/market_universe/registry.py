"""Market Universe Registry — research catalogue, not an execution allowlist.

Answers: how many instruments exist, by class, which are live/stale/
unavailable. Never treats missing data as opportunity=0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    discover_from_broker_rows,
    is_liquid_scalping_candidate,
)
from app.domain.market_universe.asset_profiles import profile_for
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.constants import (
    ADVISORY_ONLY,
    ALLOW_LIVE_PROMOTION,
    ASSET_CLASSES,
    RESEARCH_UNIVERSE_IS_NOT_EXECUTION_UNIVERSE,
    UNKNOWN,
)
from app.domain.market_universe.data_quality import evaluate_data_quality
from app.domain.market_universe.identity import (
    AliasIndex,
    canonical_desk,
    group_catalogue_by_desk,
    identity_from_broker_code,
)
from app.domain.market_universe.instrument import InstrumentRecord
from app.domain.market_universe.sessions import session_for_instrument, weekend_behavior
from app.domain.trading.gold_only import is_gold_symbol


def _row_get(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return default


def _is_unsupported(code: str, row: dict[str, Any]) -> bool:
    mode = row.get("trade_mode_raw", row.get("trade_mode"))
    mode_int: int | None
    try:
        mode_int = int(mode) if mode not in (None, "") else None
    except (TypeError, ValueError):
        mode_int = 4 if str(mode).strip().lower() in {"full", "4"} else None
    try:
        return not is_liquid_scalping_candidate(
            code, trade_mode=mode_int, asset_class=None
        )
    except Exception:
        return False


def _trade_mode_label(row: dict[str, Any]) -> str:
    raw = _row_get(row, "trade_mode", "trade_mode_raw")
    mapping = {0: "disabled", 1: "longonly", 2: "shortonly", 3: "closeonly", 4: "full"}
    if isinstance(raw, int):
        return mapping.get(raw, str(raw))
    text = str(raw or "").strip().lower()
    return text or UNKNOWN


def _infer_currencies(desk: str, row: dict[str, Any]) -> tuple[str, str]:
    base = str(_row_get(row, "currency_base", "base_currency") or "")
    quote = str(
        _row_get(row, "currency_profit", "quote_currency", "currency_margin") or ""
    )
    if not base and len(desk) >= 6 and desk[:6].isalpha():
        base, quote = desk[:3], desk[3:6]
    return (base or UNKNOWN, quote or UNKNOWN)


def build_instrument(
    row: dict[str, Any],
    *,
    catalogue_forms: tuple[str, ...] = (),
    quote: dict[str, Any] | None = None,
    now: datetime | None = None,
    disabled: bool = False,
) -> InstrumentRecord:
    code = str(_row_get(row, "code", "name", "symbol") or "").strip()
    desk = canonical_desk(code)
    desc = str(row.get("description") or "")
    identity = identity_from_broker_code(
        code,
        display_name=desc or desk or code,
        catalogue_forms=catalogue_forms,
        broker=str(_row_get(row, "broker") or UNKNOWN),
        exchange=str(_row_get(row, "exchange") or UNKNOWN),
    )
    classification = classify_instrument(code, description=desc, broker_row=row)
    q = quote if isinstance(quote, dict) else {}
    crypto = classification.asset_class == "CRYPTO"
    trade_mode = _trade_mode_label(row)
    dq = evaluate_data_quality(
        bid=_row_get(q, "bid", default=row.get("bid")),
        ask=_row_get(q, "ask", default=row.get("ask")),
        last_quote_ts=_row_get(
            q, "last_quote_timestamp", "tick_time", "time", default=row.get("time")
        ),
        quote_age_seconds=_row_get(
            q, "quote_age_seconds", default=row.get("quote_age_seconds")
        ),
        last_bar_ts=_row_get(q, "last_bar_ts", "bar_time"),
        bar_age_seconds=_row_get(q, "bar_age_seconds"),
        history_bars=_row_get(
            q, "history_bars", "bars", default=row.get("history_bars")
        ),
        missing_bars=_row_get(q, "missing_bars"),
        spread=_row_get(q, "spread", default=row.get("spread")),
        tick_frequency=_row_get(q, "tick_frequency"),
        volume=_row_get(q, "volume", "tick_volume"),
        trade_mode=trade_mode,
        market_open=_row_get(q, "market_open", default=row.get("market_open")),
        disabled=disabled,
        unsupported=_is_unsupported(code, row),
        fetch_error=bool(row.get("fetch_error") or q.get("error")),
        crypto_24_7=crypto,
        now=now,
    )
    sess = session_for_instrument(
        code,
        asset_class=classification.asset_class,
        now=now,
        broker_session=str(_row_get(row, "session", "trading_sessions") or "") or None,
    )
    base, quote_ccy = _infer_currencies(desk, row)
    tradable = trade_mode == "full" and dq.state not in {"DISABLED", "UNSUPPORTED"}
    research_eligible = dq.state in {
        "LIVE",
        "STALE",
        "INSUFFICIENT_HISTORY",
    }
    return InstrumentRecord(
        identity=identity,
        classification=classification,
        data_quality=dq,
        quote_currency=quote_ccy,
        base_currency=base,
        contract_size=str(
            _row_get(row, "contract_size", "trade_contract_size") or UNKNOWN
        ),
        point=str(_row_get(row, "point") or UNKNOWN),
        digits=row.get("digits") if row.get("digits") not in (None, "") else UNKNOWN,
        tick_size=str(_row_get(row, "tick_size", "trade_tick_size") or UNKNOWN),
        tick_value=str(_row_get(row, "tick_value", "trade_tick_value") or UNKNOWN),
        min_volume=str(_row_get(row, "volume_min", "min_volume") or UNKNOWN),
        max_volume=str(_row_get(row, "volume_max", "max_volume") or UNKNOWN),
        volume_step=str(_row_get(row, "volume_step") or UNKNOWN),
        trading_sessions=str(sess.get("session") or UNKNOWN),
        timezone=str(_row_get(row, "timezone") or "UTC"),
        exchange=str(_row_get(row, "exchange") or UNKNOWN),
        broker=str(_row_get(row, "broker") or UNKNOWN),
        margin_requirements=str(
            _row_get(row, "margin_initial", "margin_requirements", "margin_calc_mode")
            or UNKNOWN
        ),
        leverage_constraints=str(
            _row_get(row, "leverage", "leverage_constraints") or UNKNOWN
        ),
        contract_type=str(
            _row_get(row, "contract_type", "margin_calc_mode", "trade_calc_mode")
            or UNKNOWN
        ),
        market_status=dq.session_status,
        trade_mode=trade_mode,
        data_availability=dq.state,
        last_quote_timestamp=str(
            _row_get(q, "last_quote_timestamp", "tick_time")
            or _row_get(row, "time")
            or UNKNOWN
        ),
        spread=_row_get(q, "spread", default=row.get("spread")) or UNKNOWN,
        liquidity_metadata=str(_row_get(row, "liquidity_metadata") or UNKNOWN),
        tradable=tradable,
        research_eligible=research_eligible,
        extra={
            "weekend_behavior": weekend_behavior(classification.asset_class),
            "filling_mode": _row_get(row, "filling_mode"),
            "execution_mode": _row_get(row, "execution_mode"),
            "swap": _row_get(row, "swap_mode", "swap"),
            "visible": _row_get(row, "visible"),
            "trade_allowed": _row_get(row, "trade_allowed"),
            "timeframe_quality": q.get("timeframe_quality")
            if isinstance(q.get("timeframe_quality"), dict)
            else {},
            "bid": _row_get(q, "bid", default=row.get("bid")),
            "ask": _row_get(q, "ask", default=row.get("ask")),
            "last_error": _row_get(q, "reason", default=row.get("fetch_error")),
            "live_execution_enabled": is_gold_symbol(desk),
        },
    )


def build_registry(
    broker_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    quotes: dict[str, dict[str, Any]] | None = None,
    disabled_symbols: set[str] | frozenset[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a canonical registry from broker catalogue rows.

    One record per economic desk. Multiple broker forms collapse to aliases.
    """
    rows = [r for r in (broker_rows or ()) if isinstance(r, dict)]
    discovered = discover_from_broker_rows(rows)
    codes = [str(d.code) for d in discovered]
    by_desk = group_catalogue_by_desk(codes)
    row_by_code = {
        str(_row_get(r, "code", "name") or "").strip().upper(): r for r in rows
    }
    aliases = AliasIndex()
    instruments: list[dict[str, Any]] = []
    seen_desk: set[str] = set()
    quote_map = quotes or {}
    disabled = {canonical_desk(s) for s in (disabled_symbols or ())}

    for desk, forms in sorted(by_desk.items()):
        if not desk or desk in seen_desk:
            continue
        seen_desk.add(desk)
        preferred = next((f for f in forms if str(f).upper().endswith("_I")), forms[0])
        row = row_by_code.get(preferred.upper()) or row_by_code.get(desk.upper()) or {}
        if not row:
            row = {"code": preferred, "name": preferred}
        for form in forms:
            aliases.add(form, desk)
        rec = build_instrument(
            row,
            catalogue_forms=forms,
            quote=quote_map.get(preferred)
            or quote_map.get(desk)
            or quote_map.get(preferred.upper()),
            now=now,
            disabled=desk in disabled,
        )
        instruments.append(rec.to_dict())

    by_class: dict[str, int] = dict.fromkeys(ASSET_CLASSES, 0)
    by_state: dict[str, int] = {}
    for item in instruments:
        by_class[str(item.get("asset_class") or "UNKNOWN")] = (
            by_class.get(str(item.get("asset_class") or "UNKNOWN"), 0) + 1
        )
        state = str((item.get("data_quality") or {}).get("state") or UNKNOWN)
        by_state[state] = by_state.get(state, 0) + 1

    profiles = {k: profile_for(k) for k in ASSET_CLASSES}
    return {
        "advisory_only": ADVISORY_ONLY,
        "research_universe_is_not_execution_universe": (
            RESEARCH_UNIVERSE_IS_NOT_EXECUTION_UNIVERSE
        ),
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "as_of": (now or datetime.now(UTC)).isoformat(),
        "broker_symbols_found": len(discovered),
        "canonical_instruments": len(instruments),
        "counts": {
            "universe": len(instruments),
            "FOREX": by_class.get("FOREX", 0),
            "CRYPTO": by_class.get("CRYPTO", 0),
            "METALS": by_class.get("METALS", 0),
            "INDICES": by_class.get("INDICES", 0),
            "ENERGY": by_class.get("ENERGY", 0),
            "STOCKS": by_class.get("STOCKS", 0),
            "COMMODITIES": by_class.get("COMMODITIES", 0),
            "OTHER": by_class.get("OTHER", 0),
            "UNKNOWN_CLASS": by_class.get("UNKNOWN", 0),
            "tradable": sum(1 for i in instruments if i.get("tradable")),
            "live": by_state.get("LIVE", 0),
            "stale": by_state.get("STALE", 0),
            "no_data": by_state.get("NO_DATA", 0),
            "market_closed": by_state.get("MARKET_CLOSED", 0),
            "disabled": by_state.get("DISABLED", 0),
            "insufficient_history": by_state.get("INSUFFICIENT_HISTORY", 0),
            "unsupported": by_state.get("UNSUPPORTED", 0),
            "error": by_state.get("ERROR", 0),
            "unknown": by_state.get("UNKNOWN", 0),
            "data_ready": by_state.get("LIVE", 0),
        },
        "by_state": by_state,
        "by_class": by_class,
        "instruments": instruments,
        "alias_index": dict(aliases.by_form),
        "asset_profiles": profiles,
        "xauusd_reference": next(
            (i for i in instruments if i.get("canonical_symbol") == "XAUUSD"),
            None,
        ),
    }
