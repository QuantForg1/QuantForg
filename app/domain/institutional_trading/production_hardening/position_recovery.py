"""Position recovery after Railway/process restart — no duplicate trades."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    PositionLifecycleState,
)
from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PmeRecoverySnapshot:
    ticket: int
    symbol: str
    side: str
    entry_price: str
    initial_volume: str
    remaining_volume: str
    initial_stop: str
    risk_distance: str
    opened_at: str
    state: str
    current_stop: str
    current_tp: str
    be_moved: bool
    partial_done: bool
    trailing_active: bool
    max_favorable_r: str
    ai_entry_confidence: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_path() -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / DEFAULT_HARDENING_CONFIG.pme_state_filename


def persist_pme_state(engine: Any) -> None:
    """Snapshot PME managed positions for cold restart."""
    path = _state_path()
    rows: list[dict[str, Any]] = []
    try:
        positions = getattr(engine, "_positions", {}) or {}
        for pos in positions.values():
            rows.append(
                PmeRecoverySnapshot(
                    ticket=int(pos.ticket),
                    symbol=str(pos.symbol),
                    side=str(pos.side),
                    entry_price=str(pos.entry_price),
                    initial_volume=str(pos.initial_volume),
                    remaining_volume=str(pos.remaining_volume),
                    initial_stop=str(pos.initial_stop),
                    risk_distance=str(pos.risk_distance),
                    opened_at=pos.opened_at.isoformat()
                    if hasattr(pos.opened_at, "isoformat")
                    else str(pos.opened_at),
                    state=str(getattr(pos.state, "value", pos.state)),
                    current_stop=str(pos.current_stop),
                    current_tp=str(pos.current_tp),
                    be_moved=bool(pos.be_moved),
                    partial_done=bool(pos.partial_done),
                    trailing_active=bool(pos.trailing_active),
                    max_favorable_r=str(pos.max_favorable_r),
                    ai_entry_confidence=getattr(pos, "ai_entry_confidence", None),
                ).to_dict()
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"updated_at": datetime.now(UTC).isoformat(), "positions": rows},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("pme_state_persist_failed")


def recover_positions_from_mt5(
    *,
    mt5_adapter: Any,
    engine: Any,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Reload live MT5 positions into PME; restore trailing/partial state from snapshot.

    Never opens new trades. Skips tickets already registered (no duplicates).
    """
    from app.application.services.mt5_position_truth import force_sync_positions
    from app.domain.trading.gold_only import GOLD_SYMBOL

    sym = (symbol or GOLD_SYMBOL).strip().upper() or GOLD_SYMBOL
    sync = force_sync_positions(mt5_adapter, symbol=sym, position_engine=engine)
    restored = 0
    registered = 0
    snapshot_by_ticket: dict[int, dict[str, Any]] = {}
    path = _state_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for row in raw.get("positions", []):
                if isinstance(row, dict) and row.get("ticket") is not None:
                    snapshot_by_ticket[int(row["ticket"])] = row
        except Exception:
            logger.exception("pme_recovery_snapshot_load_failed")

    live_rows: list[Any] = []
    try:
        if hasattr(mt5_adapter, "list_positions"):
            live_rows = list(mt5_adapter.list_positions() or [])
        else:
            client = getattr(mt5_adapter, "_client", None)
            if client is not None and hasattr(client, "list_positions"):
                live_rows = list(client.list_positions() or [])
    except Exception as exc:
        logger.exception("pme_recovery_list_positions_failed")
        from app.domain.institutional_trading.production_hardening.incidents import (
            get_incident_detector,
        )

        get_incident_detector().on_position_sync_failure(detail=str(exc))
        return {
            "ok": False,
            "error": str(exc),
            "mt5_positions": sync.mt5_positions,
            "restored": 0,
            "registered": 0,
        }

    existing = set(getattr(engine, "_positions", {}) or {})
    for row in live_rows:
        ticket = int(getattr(row, "ticket", 0) or 0)
        if ticket <= 0:
            continue
        if ticket in existing:
            # Restore flags from snapshot if present
            snap = snapshot_by_ticket.get(ticket)
            if snap is not None:
                pos = engine.get(ticket) if hasattr(engine, "get") else None
                if pos is not None:
                    try:
                        pos.be_moved = bool(snap.get("be_moved", pos.be_moved))
                        pos.partial_done = bool(snap.get("partial_done", pos.partial_done))
                        pos.trailing_active = bool(
                            snap.get("trailing_active", pos.trailing_active)
                        )
                        state_raw = str(snap.get("state") or "")
                        if state_raw in {s.value for s in PositionLifecycleState}:
                            pos.state = PositionLifecycleState(state_raw)
                        restored += 1
                    except Exception:
                        logger.exception("pme_flag_restore_failed", ticket=ticket)
            continue

        snap = snapshot_by_ticket.get(ticket, {})
        try:
            side = str(getattr(row, "side", "buy") or "buy").lower()
            entry = Decimal(str(getattr(row, "open_price", 0) or 0))
            volume = Decimal(str(getattr(row, "volume", 0) or 0))
            sl = Decimal(str(snap.get("current_stop") or snap.get("initial_stop") or 0))
            if sl <= 0:
                # Prefer No Trade geometry invention — use 1% distance placeholder for PME only
                sl = entry * Decimal("0.99") if side == "buy" else entry * Decimal("1.01")
            risk = abs(entry - sl) or Decimal("1")
            opened = datetime.now(UTC)
            state = PositionLifecycleState.OPEN
            state_raw = str(snap.get("state") or "")
            if state_raw in {s.value for s in PositionLifecycleState}:
                state = PositionLifecycleState(state_raw)
            managed = ManagedPosition(
                ticket=ticket,
                symbol=str(getattr(row, "symbol", sym) or sym),
                side=side,
                entry_price=entry,
                initial_volume=volume,
                remaining_volume=volume,
                initial_stop=sl,
                risk_distance=risk,
                opened_at=opened,
                state=state,
                current_stop=Decimal(str(snap.get("current_stop") or sl)),
                current_tp=Decimal(str(snap.get("current_tp") or 0)),
                be_moved=bool(snap.get("be_moved", False)),
                partial_done=bool(snap.get("partial_done", False)),
                trailing_active=bool(snap.get("trailing_active", False)),
                max_favorable_r=Decimal(str(snap.get("max_favorable_r") or 0)),
            )
            if hasattr(engine, "register"):
                engine.register(managed)
            else:
                engine._positions[ticket] = managed
            registered += 1
            restored += 1
        except Exception:
            logger.exception("pme_recovery_register_failed", ticket=ticket)

    persist_pme_state(engine)
    logger.warning(
        "position_recovery_complete",
        mt5_positions=sync.mt5_positions,
        registered=registered,
        restored=restored,
    )
    return {
        "ok": True,
        "mt5_positions": sync.mt5_positions,
        "registered": registered,
        "restored": restored,
        "tickets": list(sync.tickets),
    }
