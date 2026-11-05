"""In-process shadow reversal exit book — observe only, never submits orders."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_trading.management.exit_context import (
    ReversalExitProposal,
    shadow_log_fields,
)

_LOCK = Lock()
_ENTRIES: list[dict[str, Any]] = []
_MAX = 500


@dataclass
class ShadowExitRecord:
    ticket: int
    symbol: str
    side: str
    proposal: ReversalExitProposal
    recorded_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    live_fed: bool = False
    note: str = ""


def record_shadow_exit(
    *,
    ticket: int,
    symbol: str,
    side: str,
    proposal: ReversalExitProposal,
    live_fed: bool = False,
    note: str = "",
) -> dict[str, Any]:
    row = ShadowExitRecord(
        ticket=int(ticket),
        symbol=str(symbol or ""),
        side=str(side or ""),
        proposal=proposal,
        live_fed=bool(live_fed),
        note=str(note or ""),
    )
    payload = {
        "ticket": row.ticket,
        "symbol": row.symbol,
        "side": row.side,
        "recorded_at": row.recorded_at,
        "live_fed": row.live_fed,
        "note": row.note,
        **shadow_log_fields(proposal),
        "proposal": asdict(proposal),
    }
    with _LOCK:
        _ENTRIES.append(payload)
        if len(_ENTRIES) > _MAX:
            del _ENTRIES[: len(_ENTRIES) - _MAX]
    return payload


def list_shadow_exits(*, limit: int = 100) -> list[dict[str, Any]]:
    with _LOCK:
        return list(_ENTRIES[-max(1, int(limit)) :])


def clear_shadow_exits() -> None:
    with _LOCK:
        _ENTRIES.clear()
