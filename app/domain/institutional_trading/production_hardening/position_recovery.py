"""Position recovery after Railway/process restart — no duplicate trades."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.management.class_policy import (
    TRADE_CLASS_UNKNOWN,
    merge_position_metadata,
    proven_trade_class,
    resolve_class_management,
)
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
    magic: int = 260720
    comment: str = ""
    cycle_id: str = ""
    snapshot_id: str = ""
    position_plan_id: str = ""
    trade_class: str = TRADE_CLASS_UNKNOWN
    opportunity_score: int | None = None
    management_profile: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_path() -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / DEFAULT_HARDENING_CONFIG.pme_state_filename


def _snapshot_from_position(pos: Any) -> PmeRecoverySnapshot:
    profile = resolve_class_management(getattr(pos, "trade_class", ""))
    score = getattr(pos, "opportunity_score", None)
    try:
        score_i = int(score) if score is not None and score != "" else None
    except (TypeError, ValueError):
        score_i = None
    return PmeRecoverySnapshot(
        ticket=int(pos.ticket),
        symbol=str(pos.symbol),
        side=str(pos.side),
        entry_price=str(pos.entry_price),
        initial_volume=str(pos.initial_volume),
        remaining_volume=str(pos.remaining_volume),
        initial_stop=str(pos.initial_stop),
        risk_distance=str(pos.risk_distance),
        opened_at=(
            pos.opened_at.isoformat()
            if hasattr(pos.opened_at, "isoformat")
            else str(pos.opened_at)
        ),
        state=str(getattr(pos.state, "value", pos.state)),
        current_stop=str(pos.current_stop),
        current_tp=str(pos.current_tp),
        be_moved=bool(pos.be_moved),
        partial_done=bool(pos.partial_done),
        trailing_active=bool(pos.trailing_active),
        max_favorable_r=str(pos.max_favorable_r),
        ai_entry_confidence=getattr(pos, "ai_entry_confidence", None),
        magic=int(getattr(pos, "magic", 0) or 0),
        comment=str(getattr(pos, "comment", "") or "")[:64],
        cycle_id=str(getattr(pos, "cycle_id", "") or ""),
        snapshot_id=str(getattr(pos, "snapshot_id", "") or ""),
        position_plan_id=str(getattr(pos, "position_plan_id", "") or ""),
        trade_class=proven_trade_class(getattr(pos, "trade_class", "")),
        opportunity_score=score_i,
        management_profile=str(
            getattr(pos, "management_profile", "") or profile.profile_name
        ),
    )


def persist_pme_state(engine: Any) -> None:
    """Snapshot PME managed positions for cold restart.

    Only currently registered engine tickets are written. Closed / missing
    MT5 tickets must already have been dropped by force_sync before this
    call so stale disk tickets cannot remain authoritative.
    """
    path = _state_path()
    rows: list[dict[str, Any]] = []
    try:
        from app.domain.institutional_trading.operations.quantforg_position_cap import (
            is_quantforg_owned_position,
        )

        positions = getattr(engine, "_positions", {}) or {}
        for pos in positions.values():
            if not is_quantforg_owned_position(pos):
                continue
            rows.append(_snapshot_from_position(pos).to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"updated_at": datetime.now(UTC).isoformat(), "positions": rows},
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.warning(
            "pme_state_persisted",
            tickets=[row.get("ticket") for row in rows],
            count=len(rows),
        )
    except Exception:
        logger.exception("pme_state_persist_failed")


def _overlay_metadata(pos: Any, meta: dict[str, Any]) -> None:
    cls = proven_trade_class(meta.get("trade_class"))
    current = proven_trade_class(getattr(pos, "trade_class", ""))
    if current == TRADE_CLASS_UNKNOWN and cls in {"SCALP", "HOLD"}:
        pos.trade_class = cls
    elif not str(getattr(pos, "trade_class", "") or "").strip():
        pos.trade_class = cls
    for field_name in ("cycle_id", "snapshot_id", "position_plan_id", "comment"):
        current_val = str(getattr(pos, field_name, "") or "")
        incoming = str(meta.get(field_name) or "")
        if not current_val and incoming:
            setattr(pos, field_name, incoming)
    if getattr(pos, "opportunity_score", None) is None and meta.get(
        "opportunity_score"
    ) not in {None, ""}:
        try:
            pos.opportunity_score = int(meta["opportunity_score"])
        except (TypeError, ValueError):
            pass
    if not str(getattr(pos, "management_profile", "") or ""):
        pos.management_profile = str(
            meta.get("management_profile")
            or resolve_class_management(getattr(pos, "trade_class", "")).profile_name
        )


def recover_positions_from_mt5(
    *,
    mt5_adapter: Any,
    engine: Any,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Reload live MT5 positions into PME; restore trailing/partial state from snapshot.

    Never opens new trades. Skips tickets already registered (no duplicates).
    Stale disk tickets that are absent from MT5 are not re-activated.
    """
    from app.application.services.mt5_position_truth import force_sync_positions
    from app.domain.institutional_trading.operations.quantforg_position_cap import (
        is_quantforg_owned_position,
        ownership_observability,
        position_magic,
        purge_non_quantforg_from_engine,
    )
    from app.domain.trading.gold_only import GOLD_SYMBOL

    sym = (symbol or GOLD_SYMBOL).strip().upper() or GOLD_SYMBOL
    sync = force_sync_positions(mt5_adapter, symbol=sym, position_engine=engine)
    purge_non_quantforg_from_engine(engine, symbol=sym)
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

    live_tickets = {
        int(getattr(row, "ticket", 0) or 0)
        for row in live_rows
        if int(getattr(row, "ticket", 0) or 0) > 0
    }
    stale_disk = [
        ticket for ticket in snapshot_by_ticket if ticket not in live_tickets
    ]
    if stale_disk:
        logger.warning(
            "pme_stale_disk_tickets_ignored",
            tickets=stale_disk,
            reason="absent_from_mt5_broker_truth",
        )

    existing = set(getattr(engine, "_positions", {}) or {})
    skipped_non_owned = 0
    for row in live_rows:
        ticket = int(getattr(row, "ticket", 0) or 0)
        if ticket <= 0:
            continue
        if not is_quantforg_owned_position(row, symbol=sym):
            skipped_non_owned += 1
            obs = ownership_observability(row, symbol=sym)
            logger.warning(
                "pme_skip_non_owned",
                ticket=ticket,
                reason="NOT_QUANTFORG_OWNED",
                **obs,
            )
            if ticket in existing:
                positions = getattr(engine, "_positions", None)
                if isinstance(positions, dict):
                    positions.pop(ticket, None)
            continue
        comment = str(getattr(row, "comment", "") or "")[:64]
        meta = merge_position_metadata(
            snapshot=snapshot_by_ticket.get(ticket, {}),
            comment=comment,
        )
        if ticket in existing:
            snap = snapshot_by_ticket.get(ticket)
            pos = engine.get(ticket) if hasattr(engine, "get") else None
            if pos is not None:
                try:
                    if snap is not None:
                        pos.be_moved = bool(snap.get("be_moved", pos.be_moved))
                        pos.partial_done = bool(
                            snap.get("partial_done", pos.partial_done)
                        )
                        pos.trailing_active = bool(
                            snap.get("trailing_active", pos.trailing_active)
                        )
                        state_raw = str(snap.get("state") or "")
                        if state_raw in {s.value for s in PositionLifecycleState}:
                            pos.state = PositionLifecycleState(state_raw)
                    _overlay_metadata(pos, meta)
                    restored += 1
                except Exception:
                    logger.exception("pme_flag_restore_failed", ticket=ticket)
            continue

        snap = snapshot_by_ticket.get(ticket, {})
        try:
            side = str(getattr(row, "side", "buy") or "buy").lower()
            entry = Decimal(str(getattr(row, "open_price", 0) or 0))
            volume = Decimal(str(getattr(row, "volume", 0) or 0))
            broker_sl = Decimal(str(getattr(row, "stop_loss", 0) or 0))
            broker_tp = Decimal(str(getattr(row, "take_profit", 0) or 0))
            snap_sl = Decimal(
                str(snap.get("current_stop") or snap.get("initial_stop") or 0)
            )
            snap_risk = Decimal(str(snap.get("risk_distance") or 0))
            snap_initial = Decimal(str(snap.get("initial_stop") or 0))
            be_offset = Decimal("0.2")
            be_already = False
            # Broker SL on the profit side of entry ⇒ BE (or better) already applied.
            if broker_sl > 0 and entry > 0:
                if side == "sell" and broker_sl < entry:
                    be_already = True
                elif side == "buy" and broker_sl > entry:
                    be_already = True

            if be_already and broker_sl > 0:
                # Reconstruct original 1R from BE geometry: BE ≈ entry ± 0.2R
                reconstructed = (abs(entry - broker_sl) / be_offset).quantize(
                    Decimal("0.0001")
                )
                if snap_risk > reconstructed:
                    risk = snap_risk
                else:
                    risk = reconstructed or Decimal("1")
                if snap_initial > 0:
                    initial_sl = snap_initial
                elif side == "sell":
                    initial_sl = entry + risk
                else:
                    initial_sl = entry - risk
                current_sl = broker_sl
            elif broker_sl > 0:
                # Protective stop still on risk side — broker defines 1R.
                initial_sl = (
                    snap_initial
                    if snap_initial > 0
                    and abs(entry - snap_initial) >= abs(entry - broker_sl)
                    else broker_sl
                )
                risk = abs(entry - initial_sl) or Decimal("1")
                if side == "sell":
                    current_sl = (
                        min(snap_sl, broker_sl) if snap_sl > 0 else broker_sl
                    )
                else:
                    current_sl = (
                        max(snap_sl, broker_sl) if snap_sl > 0 else broker_sl
                    )
            elif snap_sl > 0:
                initial_sl = snap_initial if snap_initial > 0 else snap_sl
                current_sl = snap_sl
                risk = snap_risk if snap_risk > 0 else (abs(entry - initial_sl) or Decimal("1"))
            else:
                initial_sl = (
                    entry * Decimal("0.99")
                    if side == "buy"
                    else entry * Decimal("1.01")
                )
                current_sl = initial_sl
                risk = abs(entry - initial_sl) or Decimal("1")

            tp = Decimal(str(snap.get("current_tp") or 0))
            if tp <= 0 and broker_tp > 0:
                tp = broker_tp
            opened = datetime.now(UTC)
            opened_raw = getattr(row, "opened_at", None)
            if isinstance(opened_raw, datetime):
                opened = (
                    opened_raw if opened_raw.tzinfo else opened_raw.replace(tzinfo=UTC)
                )
            state = PositionLifecycleState.OPEN
            state_raw = str(snap.get("state") or "")
            if state_raw in {s.value for s in PositionLifecycleState}:
                state = PositionLifecycleState(state_raw)
            be_moved = bool(snap.get("be_moved", False)) or be_already
            if be_moved and state is PositionLifecycleState.OPEN:
                state = PositionLifecycleState.BE_MOVED
            score = meta.get("opportunity_score")
            try:
                score_i = int(score) if score not in {None, ""} else None
            except (TypeError, ValueError):
                score_i = None
            trade_class = proven_trade_class(meta.get("trade_class"))
            profile = resolve_class_management(trade_class)
            managed = ManagedPosition(
                ticket=ticket,
                symbol=str(getattr(row, "symbol", sym) or sym),
                side=side,
                entry_price=entry,
                initial_volume=volume,
                remaining_volume=volume,
                initial_stop=initial_sl,
                risk_distance=risk,
                opened_at=opened,
                state=state,
                current_stop=current_sl,
                current_tp=tp,
                be_moved=be_moved,
                partial_done=bool(snap.get("partial_done", False)),
                trailing_active=bool(snap.get("trailing_active", False)),
                max_favorable_r=Decimal(str(snap.get("max_favorable_r") or 0)),
                magic=position_magic(row),
                comment=comment,
                cycle_id=str(meta.get("cycle_id") or ""),
                snapshot_id=str(meta.get("snapshot_id") or ""),
                position_plan_id=str(meta.get("position_plan_id") or ""),
                trade_class=trade_class,
                opportunity_score=score_i,
                management_profile=str(
                    meta.get("management_profile") or profile.profile_name
                ),
            )
            if hasattr(engine, "register"):
                engine.register(managed)
            else:
                engine._positions[ticket] = managed
            registered += 1
            restored += 1
            logger.warning(
                "PME recovered position",
                ticket=ticket,
                symbol=managed.symbol,
                side=side,
                risk_distance=str(risk),
                be_moved=be_moved,
                be_already_on_broker=be_already,
                state=state.value,
                trade_class=trade_class,
                cycle_id=managed.cycle_id,
                snapshot_id=managed.snapshot_id,
                position_plan_id=managed.position_plan_id,
                management_profile=managed.management_profile,
            )
            if trade_class == TRADE_CLASS_UNKNOWN:
                logger.warning(
                    "pme_trade_class_unknown_fallback",
                    ticket=ticket,
                    symbol=managed.symbol,
                    comment=comment,
                    detail="unproven class — safest management fallback",
                )
            if be_already:
                logger.warning(
                    "BREAK_EVEN",
                    ticket=ticket,
                    symbol=managed.symbol,
                    detail="broker SL already on profit side — PME BE_MOVED",
                    broker_sl=str(broker_sl),
                    entry=str(entry),
                    risk_distance=str(risk),
                    trade_class=trade_class,
                )
        except Exception:
            logger.exception("pme_recovery_register_failed", ticket=ticket)

    persist_pme_state(engine)
    logger.warning(
        "position_recovery_complete",
        mt5_positions=sync.mt5_positions,
        quantforg_positions=getattr(sync, "quantforg_positions", 0),
        registered=registered,
        restored=restored,
        skipped_non_owned=skipped_non_owned,
        stale_disk_ignored=stale_disk,
    )
    return {
        "ok": True,
        "mt5_positions": sync.mt5_positions,
        "registered": registered,
        "restored": restored,
        "skipped_non_owned": skipped_non_owned,
        "tickets": list(getattr(sync, "quantforg_tickets", None) or sync.tickets),
        "stale_disk_ignored": stale_disk,
    }
