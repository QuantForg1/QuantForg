"""Durable broker-confirmed trade outcomes for post-PR #182 monitoring.

Observability only — never authorizes or blocks LIVE orders. Idempotent on
``(position_id, exit_deal_id)``. Unknown strategy_id stays NULL. Missing
commission/swap are flagged via ``costs_complete=False`` rather than inventing
zeros for profitability claims.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

PR182_UTC = datetime(2026, 11, 6, 11, 11, tzinfo=UTC)
PR180_UTC = datetime(2026, 11, 6, 9, 51, tzinfo=UTC)

_LOCK = RLock()
_MEMORY: dict[tuple[int, int], dict[str, Any]] = {}
_FORCED_DOWN = False

_CREATE = """
CREATE TABLE IF NOT EXISTS public.strategy_trade_outcome (
    position_id BIGINT NOT NULL,
    exit_deal_id BIGINT NOT NULL,
    broker_login BIGINT,
    strategy_id TEXT,
    engine TEXT,
    contributors JSONB NOT NULL DEFAULT '[]'::jsonb,
    symbol TEXT,
    side TEXT,
    volume NUMERIC,
    net_pnl NUMERIC NOT NULL,
    profit NUMERIC,
    commission NUMERIC,
    swap NUMERIC,
    costs_complete BOOLEAN NOT NULL DEFAULT FALSE,
    close_reason TEXT,
    attribution_confidence TEXT NOT NULL DEFAULT 'unknown',
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (position_id, exit_deal_id)
)
"""

_LOCKDOWN = """
DO $lock$
BEGIN
  EXECUTE 'ALTER TABLE public.strategy_trade_outcome ENABLE ROW LEVEL SECURITY';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.strategy_trade_outcome FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.strategy_trade_outcome FROM authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT ALL ON TABLE public.strategy_trade_outcome TO service_role';
  END IF;
END
$lock$;
"""

_INSERT = """
INSERT INTO public.strategy_trade_outcome (
    position_id, exit_deal_id, broker_login, strategy_id, engine, contributors,
    symbol, side, volume, net_pnl, profit, commission, swap, costs_complete,
    close_reason, attribution_confidence, closed_at
) VALUES (
    $1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17
)
ON CONFLICT (position_id, exit_deal_id) DO NOTHING
"""

_SELECT_LOGIN = """
SELECT *
FROM public.strategy_trade_outcome
WHERE ($1::bigint IS NULL OR broker_login = $1)
ORDER BY closed_at NULLS LAST, created_at
"""


@dataclass(frozen=True, slots=True)
class TradeOutcomeRow:
    position_id: int
    exit_deal_id: int
    broker_login: int | None
    strategy_id: str | None
    engine: str | None
    contributors: tuple[str, ...]
    symbol: str | None
    side: str | None
    volume: float | None
    net_pnl: float
    profit: float | None
    commission: float | None
    swap: float | None
    costs_complete: bool
    close_reason: str | None
    attribution_confidence: str
    closed_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "exit_deal_id": self.exit_deal_id,
            "broker_login": self.broker_login,
            "strategy_id": self.strategy_id,
            "engine": self.engine,
            "contributors": list(self.contributors),
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "net_pnl": self.net_pnl,
            "profit": self.profit,
            "commission": self.commission,
            "swap": self.swap,
            "costs_complete": self.costs_complete,
            "close_reason": self.close_reason,
            "attribution_confidence": self.attribution_confidence,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "period": period_label(self.closed_at),
        }


def period_label(closed_at: datetime | None) -> str:
    if closed_at is None:
        return "unknown_time"
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=UTC)
    if closed_at >= PR182_UTC:
        return "post_pr182"
    if closed_at >= PR180_UTC:
        return "post_pr180_pre_pr182"
    return "pre_pr180"


def reset_trade_outcome_store_for_tests() -> None:
    global _FORCED_DOWN
    with _LOCK:
        _MEMORY.clear()
        _FORCED_DOWN = False


def force_trade_outcome_store_unavailable_for_tests(down: bool) -> None:
    global _FORCED_DOWN
    with _LOCK:
        _FORCED_DOWN = down


def _testing() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _use_postgres() -> bool:
    if _testing() or _FORCED_DOWN:
        return False
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
    )

    return direct_postgres_available()


def _ensure_schema() -> None:
    from app.infrastructure.persistence.direct_postgres import execute

    execute(_CREATE)
    execute(_LOCKDOWN)


def _parse_closed_at(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def record_trade_outcome(
    *,
    position_id: int,
    exit_deal_id: int,
    net_pnl: float | Decimal | str,
    strategy_id: str | None = None,
    engine: str | None = None,
    contributors: list[str] | None = None,
    symbol: str | None = None,
    side: str | None = None,
    volume: float | None = None,
    profit: float | None = None,
    commission: float | None = None,
    swap: float | None = None,
    costs_complete: bool = False,
    close_reason: str | None = None,
    attribution_confidence: str = "unknown",
    closed_at: datetime | str | None = None,
    broker_login: int | None = None,
) -> str:
    """Idempotent insert. Returns created | duplicate | untrusted."""
    try:
        pid = int(position_id)
        xid = int(exit_deal_id)
        pnl = float(Decimal(str(net_pnl)))
    except Exception:
        return "ignored_unconfirmed"
    if pid <= 0 or xid <= 0:
        return "ignored_unconfirmed"
    sid = str(strategy_id or "").strip() or None
    if sid in {"ite_primary", "unknown", "none"}:
        sid = None
        if attribution_confidence == "bound_other":
            attribution_confidence = "unknown"
    contrib = [
        str(c).strip()
        for c in (contributors or [])
        if str(c).strip() and str(c).strip() != sid
    ]
    when = closed_at if isinstance(closed_at, datetime) else _parse_closed_at(closed_at)
    payload = {
        "position_id": pid,
        "exit_deal_id": xid,
        "broker_login": int(broker_login) if broker_login else None,
        "strategy_id": sid,
        "engine": str(engine or "").strip() or None,
        "contributors": contrib,
        "symbol": symbol,
        "side": str(side or "").strip().upper() or None,
        "volume": volume,
        "net_pnl": pnl,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "costs_complete": bool(costs_complete),
        "close_reason": close_reason,
        "attribution_confidence": attribution_confidence or "unknown",
        "closed_at": when,
    }
    key = (pid, xid)
    with _LOCK:
        if key in _MEMORY:
            return "duplicate"
        _MEMORY[key] = dict(payload)
    if not _use_postgres():
        if _FORCED_DOWN:
            with _LOCK:
                _MEMORY.pop(key, None)
            return "untrusted"
        return "created"
    try:
        _ensure_schema()
        from app.infrastructure.persistence.direct_postgres import execute

        execute(
            _INSERT,
            pid,
            xid,
            payload["broker_login"],
            sid,
            payload["engine"],
            json.dumps(contrib),
            symbol,
            payload["side"],
            volume,
            pnl,
            profit,
            commission,
            swap,
            bool(costs_complete),
            close_reason,
            payload["attribution_confidence"],
            when,
        )
    except Exception as exc:
        with _LOCK:
            _MEMORY.pop(key, None)
        logger.warning(
            "strategy_trade_outcome_record_failed",
            error_type=type(exc).__name__,
            position_id=pid,
        )
        return "untrusted"
    logger.warning(
        "strategy_trade_outcome_recorded",
        position_id=pid,
        exit_deal_id=xid,
        strategy_id=sid,
        net_pnl=pnl,
        attribution_confidence=payload["attribution_confidence"],
        costs_complete=bool(costs_complete),
    )
    return "created"


def list_trade_outcomes(
    *,
    broker_login: int | None = None,
    period: str | None = None,
) -> list[TradeOutcomeRow]:
    rows: list[dict[str, Any]] = []
    if _use_postgres():
        try:
            _ensure_schema()
            from app.infrastructure.persistence.direct_postgres import fetch

            fetched = fetch(_SELECT_LOGIN, broker_login)
            rows = [dict(r) for r in fetched]
        except Exception as exc:
            logger.warning(
                "strategy_trade_outcome_list_failed",
                error_type=type(exc).__name__,
            )
            rows = []
    if not rows:
        with _LOCK:
            rows = [
                dict(v)
                for v in _MEMORY.values()
                if broker_login is None or v.get("broker_login") == broker_login
            ]
    out: list[TradeOutcomeRow] = []
    for row in rows:
        closed = row.get("closed_at")
        if not isinstance(closed, datetime):
            closed = _parse_closed_at(closed)
        contrib_raw = row.get("contributors") or []
        if isinstance(contrib_raw, str):
            try:
                contrib_raw = json.loads(contrib_raw)
            except Exception:
                contrib_raw = []
        item = TradeOutcomeRow(
            position_id=int(row["position_id"]),
            exit_deal_id=int(row["exit_deal_id"]),
            broker_login=(
                int(row["broker_login"])
                if row.get("broker_login") not in (None, "")
                else None
            ),
            strategy_id=(str(row["strategy_id"]) if row.get("strategy_id") else None),
            engine=(str(row["engine"]) if row.get("engine") else None),
            contributors=tuple(str(c) for c in contrib_raw if str(c).strip()),
            symbol=row.get("symbol"),
            side=row.get("side"),
            volume=(float(row["volume"]) if row.get("volume") is not None else None),
            net_pnl=float(row["net_pnl"]),
            profit=(float(row["profit"]) if row.get("profit") is not None else None),
            commission=(
                float(row["commission"]) if row.get("commission") is not None else None
            ),
            swap=float(row["swap"]) if row.get("swap") is not None else None,
            costs_complete=bool(row.get("costs_complete")),
            close_reason=row.get("close_reason"),
            attribution_confidence=str(row.get("attribution_confidence") or "unknown"),
            closed_at=closed,
        )
        if period and period_label(item.closed_at) != period:
            continue
        out.append(item)
    out.sort(key=lambda r: r.closed_at or datetime.min.replace(tzinfo=UTC))
    return out
