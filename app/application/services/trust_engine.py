"""Load the signed-in user's broker history into the Trust Engine.

This service only reads. It does not place, modify, or close trades.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.exceptions.base import NotFoundError, ServiceUnavailableError
from app.domain.trust_engine import TrustBuildInput, build_trust_report
from core.logging import get_logger

logger = get_logger(__name__)


async def load_trust_performance(
    *,
    user_id: UUID,
    history: Any,
    account: Any | None = None,
    read_at: datetime | None = None,
) -> dict[str, Any]:
    """Read one user's history and optional account snapshot.

    ``user_id`` is passed only to the existing portfolio use cases. It is not
    copied into the report.
    """
    observed = read_at or datetime.now(UTC)
    try:
        history_dto = await history.execute(user_id=user_id)
    except (NotFoundError, ServiceUnavailableError) as exc:
        logger.info("trust_history_unavailable", error_type=type(exc).__name__)
        status_deals: tuple[dict[str, Any], ...] | None = (
            None if isinstance(exc, NotFoundError) else ()
        )
        return build_trust_report(
            TrustBuildInput(
                deals=status_deals,
                history_available=False,
                read_at=observed,
                account_scope="unknown",
            )
        )

    records = tuple(
        _deal_record(deal) for deal in (getattr(history_dto, "deals", ()) or ())
    )
    floating, login, server = await _account_facts(account, user_id=user_id)
    return build_trust_report(
        TrustBuildInput(
            deals=records,
            history_available=True,
            account_scope="unknown",
            account_login=login,
            broker_server=server,
            floating_pnl=floating,
            read_at=observed,
        )
    )


async def _account_facts(
    account: Any | None, *, user_id: UUID
) -> tuple[str | None, int | str | None, str | None]:
    if account is None:
        return None, None, None
    try:
        snapshot = await account.execute(user_id=user_id)
    except (NotFoundError, ServiceUnavailableError) as exc:
        logger.info("trust_account_unavailable", error_type=type(exc).__name__)
        return None, None, None
    server = str(getattr(snapshot, "server", "") or "").strip() or None
    profit = getattr(snapshot, "profit", None)
    return (
        None if profit is None else str(profit),
        getattr(snapshot, "login", None),
        server,
    )


def _deal_record(deal: Any) -> dict[str, Any]:
    if isinstance(deal, dict):
        return dict(deal)
    return {
        "ticket": deal.ticket,
        "position_id": deal.position_id,
        "symbol": deal.symbol,
        "side": deal.side,
        "volume": deal.volume,
        "price": deal.price,
        "profit": deal.profit,
        "commission": deal.commission,
        "swap": deal.swap,
        "deal_type": deal.deal_type,
        "time": deal.time,
    }
