"""Edge Ledger service: closed LIVE trades from Supabase -> edge report (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.domain.institutional_trading.performance_lab.edge_ledger import (
    ClosedTrade,
    build_edge_ledger,
)
from core.logging import get_logger

logger = get_logger(__name__)

_TABLE = "live_trade_journal"
_PAGE = 1000
_MAX_ROWS = 20000


def _rest() -> tuple[str, str] | None:
    try:
        from app.application.services.ops_state_persistence import (
            _supabase_rest_config,
        )

        return _supabase_rest_config()
    except Exception:
        return None


def _dec(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
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


def rows_to_trades(
    rows: list[dict[str, Any]], *, symbol_prefix: str
) -> list[ClosedTrade]:
    prefix = symbol_prefix.upper()
    trades: list[ClosedTrade] = []
    for row in rows:
        if str(row.get("status") or "").upper() != "CLOSED":
            continue
        if not str(row.get("symbol") or "").upper().startswith(prefix):
            continue
        pnl = _dec(row.get("pnl"))
        opened = _when(row.get("opened_at"))
        if pnl is None or opened is None:
            continue
        trades.append(
            ClosedTrade(
                side=str(row.get("side") or ""),
                opened_at=opened,
                pnl=pnl,
                r_multiple=_dec(row.get("r_multiple")),
            )
        )
    return trades


def fetch_closed_rows(*, since: datetime | None) -> list[dict[str, Any]] | None:
    """All CLOSED journal rows (paged). None when Supabase is unreachable."""
    cfg = _rest()
    if cfg is None:
        return None
    base, key = cfg
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    params: dict[str, str] = {
        "select": "symbol,side,opened_at,status,pnl,r_multiple",
        "status": "eq.CLOSED",
        "order": "opened_at.asc",
    }
    if since is not None:
        params["opened_at"] = f"gte.{since.isoformat()}"
    rows: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            while len(rows) < _MAX_ROWS:
                page = client.get(
                    f"{base}/{_TABLE}",
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
    except Exception as exc:
        logger.warning("edge_ledger_fetch_failed", error=type(exc).__name__)
        return None
    return rows


def build_edge_ledger_report(
    *, days: int | None = None, symbol_prefix: str = "XAU"
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    rows = fetch_closed_rows(since=since)
    if rows is None:
        return {
            "available": False,
            "reason": "live_trade_journal unreachable (Supabase unset or down)",
        }
    report = build_edge_ledger(rows_to_trades(rows, symbol_prefix=symbol_prefix))
    return {
        "available": True,
        "source": _TABLE,
        "symbol_prefix": symbol_prefix.upper(),
        "window_days": days,
        "generated_at": datetime.now(UTC).isoformat(),
        **report,
    }
