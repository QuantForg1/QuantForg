"""Shadow Signal Evaluator service (HYPOTHETICAL, read-only for trading).

Evaluates each recorded signal once its 30 min window has closed, stores the
outcome in ``shadow_signal_outcomes`` (primary key = signal_history id, so a
repeat evaluation is ignored), and reports aggregates from the stored rows.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.domain.institutional_trading.performance_lab.shadow_evaluator import (
    HORIZON_TOLERANCE_S,
    HORIZONS_MIN,
    Costs,
    Quote,
    ShadowSignal,
    aggregate,
    evaluate_pending,
)
from core.logging import get_logger

logger = get_logger(__name__)

_SIGNALS = "signal_history"
_OUTCOMES = "shadow_signal_outcomes"
_PAGE = 1000
_MAX_ROWS = 60000
_EVAL_LOCK = threading.Lock()
_COLUMNS = (
    "signal_id",
    "observed_at",
    "side",
    "accepted",
    "blocking_gate",
    "gate_family",
    "news_condition",
    "strategy",
    "session",
    "hour_utc",
    "quality",
    "confidence",
    "regime_proxy",
    "factors",
    "entry_price",
    "spread",
    "stop_distance",
    "target_distance",
    "slippage_per_side",
    "commission_usd",
    "crosses_rollover",
    "move_m1",
    "move_m5",
    "move_m15",
    "move_m30",
    "bracket",
    "r_multiple",
    "net_usd_min_lot",
    "status",
    "status_reasons",
)


def _rest() -> tuple[str, str] | None:
    try:
        from app.application.services.ops_state_persistence import (
            _supabase_rest_config,
        )

        return _supabase_rest_config()
    except Exception:
        return None


def _when(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _f(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    number = _f(value)
    return int(number) if number is not None else None


def commission_usd(symbol: str) -> float | None:
    """Verified policy tariff (USD at 0.01 lot); None when unknown."""
    try:
        from app.domain.institutional_trading.owner_live_limits import (
            resolve_entry_commission,
        )

        fee = resolve_entry_commission(symbol, None)
    except Exception:
        return None
    return float(fee) if fee is not None else None


def rows_to_inputs(
    rows: list[dict[str, Any]],
) -> tuple[list[ShadowSignal], list[Quote]]:
    signals: list[ShadowSignal] = []
    quotes: list[Quote] = []
    for row in rows:
        shadow = row.get("shadow")
        if not isinstance(shadow, dict):
            continue
        at = _when(row.get("observed_at"))
        bid, ask = _f(shadow.get("bid")), _f(shadow.get("ask"))
        if at is None or bid is None or ask is None or ask < bid or bid <= 0:
            continue
        quotes.append(Quote(at=at, bid=bid, ask=ask))
        side = str(shadow.get("intended_direction") or "").upper()
        signal_id = str(row.get("id") or "").strip()
        if side not in {"BUY", "SELL"} or not signal_id:
            continue
        factors = row.get("factors")
        signals.append(
            ShadowSignal(
                signal_id=signal_id,
                at=at,
                side=side,
                bid=bid,
                ask=ask,
                stop_atr=_f(shadow.get("stop_atr")),
                accepted=not bool(row.get("reject")),
                blocking_gate=row.get("blocking_gate"),
                quality=_i(row.get("quality")),
                confidence=_i(row.get("confidence")),
                strategy=row.get("strategy_id"),
                session=row.get("session"),
                factors=factors if isinstance(factors, dict) else {},
            )
        )
    return signals, quotes


def _paged(
    client: httpx.Client, url: str, headers: dict[str, str], params: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    while len(rows) < _MAX_ROWS:
        page = client.get(
            url,
            headers=headers,
            params={**params, "limit": str(_PAGE), "offset": str(len(rows))},
        )
        page.raise_for_status()
        chunk = page.json()
        if not isinstance(chunk, list):
            break
        rows.extend(r for r in chunk if isinstance(r, dict))
        if len(chunk) < _PAGE:
            break
    return rows


def _headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def evaluate_and_store(*, days: int, symbol: str, now: datetime | None = None) -> int:
    """Evaluate closed-window signals not yet stored. Returns rows inserted."""
    cfg = _rest()
    if cfg is None:
        return 0
    base, key = cfg
    moment = now or datetime.now(UTC)
    since = moment - timedelta(days=days)
    with _EVAL_LOCK, httpx.Client(timeout=30.0) as client:
        done = _paged(
            client,
            f"{base}/{_OUTCOMES}",
            _headers(key),
            {"select": "signal_id", "observed_at": f"gte.{since.isoformat()}"},
        )
        already = {str(r.get("signal_id")) for r in done}
        rows = _paged(
            client,
            f"{base}/{_SIGNALS}",
            _headers(key),
            {
                "select": (
                    "id,observed_at,reject,blocking_gate,quality,confidence,"
                    "strategy_id,session,factors,shadow:raw_score->shadow"
                ),
                "symbol": f"eq.{symbol.upper()}",
                "observed_at": f"gte.{since.isoformat()}",
                "raw_score->shadow": "not.is.null",
                "order": "observed_at.asc",
            },
        )
        signals, quotes = rows_to_inputs(rows)
        costs = Costs(commission_usd=commission_usd(symbol))
        fresh = evaluate_pending(
            signals, quotes, already=already, now=moment, costs=costs
        )
        if not fresh:
            return 0
        payload = [
            {"symbol": symbol.upper()} | {c: r[c] for c in _COLUMNS} for r in fresh
        ]
        resp = client.post(
            f"{base}/{_OUTCOMES}",
            headers=_headers(key)
            | {"Prefer": "resolution=ignore-duplicates,return=minimal"},
            params={"on_conflict": "signal_id"},
            json=payload,
        )
        resp.raise_for_status()
    logger.warning("shadow_signals_evaluated", inserted=len(payload))
    return len(payload)


def load_outcomes(*, days: int, symbol: str) -> list[dict[str, Any]] | None:
    cfg = _rest()
    if cfg is None:
        return None
    base, key = cfg
    since = datetime.now(UTC) - timedelta(days=days)
    try:
        with httpx.Client(timeout=30.0) as client:
            rows = _paged(
                client,
                f"{base}/{_OUTCOMES}",
                _headers(key),
                {
                    "select": "*",
                    "symbol": f"eq.{symbol.upper()}",
                    "observed_at": f"gte.{since.isoformat()}",
                    "order": "observed_at.asc",
                },
            )
    except Exception as exc:
        logger.warning("shadow_outcomes_load_failed", error=type(exc).__name__)
        return None
    for row in rows:
        for column in ("move_m1", "move_m5", "move_m15", "move_m30", "spread"):
            row[column] = _f(row.get(column))
        row["r_multiple"] = _f(row.get("r_multiple"))
        row["net_usd_min_lot"] = _f(row.get("net_usd_min_lot"))
    return rows


def build_shadow_signal_report(
    *, days: int = 7, symbol: str = "XAUUSD"
) -> dict[str, Any]:
    inserted = 0
    evaluation_error: str | None = None
    try:
        inserted = evaluate_and_store(days=days, symbol=symbol)
    except Exception as exc:
        evaluation_error = type(exc).__name__
        logger.warning("shadow_signals_evaluate_failed", error=evaluation_error)
    rows = load_outcomes(days=days, symbol=symbol)
    if rows is None:
        return {
            "available": False,
            "label": "HYPOTHETICAL",
            "reason": "shadow_signal_outcomes unreachable (Supabase unset or down)",
        }
    return {
        "available": True,
        "mode": "SHADOW",
        "label": "HYPOTHETICAL",
        "warning": (
            "Hypothetical replay of recorded signals. Not LIVE or DEMO P/L. "
            "Never changes LIVE parameters. Consecutive scans of one setup are "
            "correlated, so sample size overstates independent evidence."
        ),
        "symbol": symbol.upper(),
        "window_days": days,
        "horizons_min": list(HORIZONS_MIN),
        "horizon_tolerance_s": HORIZON_TOLERANCE_S,
        "newly_evaluated": inserted,
        "evaluation_error": evaluation_error,
        "generated_at": datetime.now(UTC).isoformat(),
        **aggregate(rows),
    }


SHADOW_EVAL_INTERVAL_S = 900.0
SHADOW_EVAL_WINDOW_DAYS = 3


async def shadow_evaluation_loop(
    *,
    symbol: str = "XAUUSD",
    interval_s: float = SHADOW_EVAL_INTERVAL_S,
    days: int = SHADOW_EVAL_WINDOW_DAYS,
) -> None:
    """Evaluate recorded signals on a schedule (HYPOTHETICAL, never trades).

    Runs off the event loop. Each signal is stored once (signal_id key), so
    a repeat pass only adds signals whose 30-minute window has since closed.
    """
    import asyncio

    await asyncio.sleep(min(180.0, interval_s))
    while True:
        try:
            inserted = await asyncio.to_thread(
                evaluate_and_store, days=days, symbol=symbol
            )
            logger.info("shadow_evaluation_pass", inserted=inserted, symbol=symbol)
        except Exception as exc:
            logger.warning("shadow_evaluation_pass_failed", error=type(exc).__name__)
        await asyncio.sleep(interval_s)
