"""Replay engine — historical XAUUSD opportunities from supplied bars/tags only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.session_filter import classify_session_utc


def _f(raw: Any, default: float | None = None) -> float | None:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _boolish(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _session_label(ts: datetime | None, explicit: Any) -> str | None:
    if explicit:
        return str(explicit).strip().lower().replace(" ", "_")
    if ts is None:
        return None
    try:
        return classify_session_utc(ts).value
    except Exception:
        return None


def normalize_bar(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an OHLC bar. Returns None if incomplete — never invents prices."""
    o = _f(raw.get("open"))
    h = _f(raw.get("high"))
    low = _f(raw.get("low"))
    c = _f(raw.get("close"))
    if None in (o, h, low, c):
        return None
    ts = (
        raw.get("timestamp")
        or raw.get("time")
        or raw.get("ts")
        or raw.get("opened_at")
    )
    return {
        "timestamp": ts,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": _f(raw.get("volume"), 0.0),
        "symbol": raw.get("symbol") or "XAUUSD",
    }


def record_opportunity(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one replay opportunity. Never fabricates signal flags or levels."""
    if not isinstance(raw, dict):
        return None
    ts_raw = (
        raw.get("timestamp")
        or raw.get("time")
        or raw.get("as_of")
        or raw.get("opened_at")
    )
    ts = _parse_ts(ts_raw)
    decision = raw.get("decision") or raw.get("action")
    if decision is None and not any(
        k in raw
        for k in (
            "bos",
            "choch",
            "liquidity_sweep",
            "order_block",
            "fair_value_gap",
            "confluence_score",
        )
    ):
        # Require at least a decision or structural tag — never invent opportunities
        return None

    entry = _f(raw.get("entry") or raw.get("entry_price"))
    exit_px = _f(raw.get("exit") or raw.get("exit_price"))
    rr = _f(raw.get("rr") or raw.get("r_multiple") or raw.get("reward_risk"))
    hold = _f(raw.get("hold_time") or raw.get("hold_sec") or raw.get("hold_time_sec"))

    decision_s = str(decision).upper() if decision is not None else None
    no_trade_reason = None
    if decision_s == "NO_TRADE":
        no_trade_reason = (
            raw.get("no_trade_reason")
            or raw.get("reason")
            or raw.get("why")
            or raw.get("rejected")
        )

    return {
        "timestamp": ts.isoformat() if ts else (str(ts_raw) if ts_raw else None),
        "session": _session_label(ts, raw.get("session") or raw.get("market_session")),
        "market_regime": raw.get("market_regime") or raw.get("regime"),
        "trend": raw.get("trend"),
        "bos": _boolish(raw.get("bos")),
        "choch": _boolish(raw.get("choch")),
        "liquidity_sweep": _boolish(
            raw.get("liquidity_sweep") if "liquidity_sweep" in raw else raw.get("sweep")
        ),
        "order_block": _boolish(raw.get("order_block")),
        "fair_value_gap": _boolish(
            raw.get("fair_value_gap") if "fair_value_gap" in raw else raw.get("fvg")
        ),
        "confluence_score": _f(raw.get("confluence_score") or raw.get("confluence")),
        "decision": decision_s,
        "no_trade_reason": no_trade_reason,
        "direction": raw.get("direction") or raw.get("side"),
        "entry": entry,
        "exit": exit_px,
        "stop_loss": _f(raw.get("stop_loss") or raw.get("sl")),
        "take_profit": _f(raw.get("take_profit") or raw.get("tp")),
        "rr": rr,
        "hold_time": hold,
        "bars_after": raw.get("bars_after") or raw.get("subsequent_bars"),
        "symbol": raw.get("symbol") or "XAUUSD",
        "source": "replay",
        "research_only": True,
    }


def run_replay(
    *,
    bars: list[dict[str, Any]] | None = None,
    opportunities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Replay historical market data and record supplied opportunities.

    Bars and opportunity tags must be supplied by the caller. This engine does
    not invent SMC signals, confluence scores, or trade decisions.
    """
    normalized_bars: list[dict[str, Any]] = []
    for raw in bars or []:
        if isinstance(raw, dict):
            bar = normalize_bar(raw)
            if bar is not None:
                normalized_bars.append(bar)

    recorded: list[dict[str, Any]] = []
    for raw in opportunities or []:
        opp = record_opportunity(raw if isinstance(raw, dict) else {})
        if opp is not None:
            # Attach bar index when timestamp matches a bar (optional enrichment)
            if opp.get("timestamp") and normalized_bars:
                for i, bar in enumerate(normalized_bars):
                    if str(bar.get("timestamp")) == str(opp.get("timestamp")):
                        opp["bar_index"] = i
                        break
            recorded.append(opp)

    return {
        "status": "available" if (normalized_bars or recorded) else "unavailable",
        "symbol": "XAUUSD",
        "bars_loaded": len(normalized_bars),
        "opportunities_recorded": len(recorded),
        "opportunities": recorded,
        "research_only": True,
        "never_modifies_strategy": True,
        "note": (
            "Replay records caller-supplied opportunities against historical bars; "
            "signals and decisions are never fabricated"
        ),
    }
