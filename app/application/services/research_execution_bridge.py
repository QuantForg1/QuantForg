"""Bridge cached global research into the existing ITE execution handoff.

Does not create a second scanner, worker, OMS, or gateway.
Does not submit orders. ITE still runs strategy, risk, OMS, and MT5.
Research snapshots remain advisory until the live-trading controller is ENABLED.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from app.domain.institutional_trading.auto_trading import prefer_allowlisted_handoff
from app.domain.institutional_trading.live_trading_control import (
    get_live_trading_controller,
    orders_may_submit,
    public_authorization_state,
)
from app.domain.trading.execution_universe import execution_symbol_allowed
from core.logging import get_logger

logger = get_logger(__name__)

_BUY_SELL = frozenset({"BUY", "SELL"})
_STALE = frozenset({"STALE", "EXPIRED", "DATA_STALE"})
_MAX_FOCUS = 36


def live_authorization_snapshot() -> dict[str, Any]:
    """Authoritative controller projection. Fail-closed on error."""
    try:
        ctrl = get_live_trading_controller()
        state = ctrl.snapshot_state()
        may_submit = orders_may_submit(state)
        return {
            "live_trading_state": state,
            "orders_may_submit": may_submit,
            "live_authorization": public_authorization_state(
                state, orders_may_submit_flag=may_submit
            ),
            "research_can_execute": ctrl.research_can_execute(),
        }
    except Exception:
        logger.warning("live_authorization_snapshot_failed")
        return {
            "live_trading_state": "UNAVAILABLE",
            "orders_may_submit": False,
            "live_authorization": "LIVE_DISABLED",
            "research_can_execute": False,
        }


def _ranked_research_buy_sell(
    snap: dict[str, Any],
    *,
    limit: int,
) -> list[str]:
    ranked: list[tuple[float, str]] = []
    seen: set[str] = set()
    for row in _research_signal_rows(snap):
        direction = str(row.get("direction") or "").strip().upper()
        if direction not in _BUY_SELL:
            continue
        if _row_is_stale(row):
            continue
        sym = str(row.get("broker_symbol") or row.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        score = _score(row)
        ranked.append((score, sym))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [sym for _score_v, sym in ranked[: max(1, int(limit or _MAX_FOCUS))]]


def research_scan_focus_symbols(*, limit: int = _MAX_FOCUS) -> list[str]:
    """BUY/SELL research desks for scan membership. Independent of live trading.

    Does not authorize an order. Missing/stale snapshot → empty.
    """
    try:
        from app.application.services.market_universe_service import (
            get_last_market_universe_snapshot,
        )

        snap = get_last_market_universe_snapshot() or {}
    except Exception:
        logger.info("research_scan_snapshot_unavailable")
        return []
    return _ranked_research_buy_sell(snap, limit=limit)


def research_live_focus_symbols(*, limit: int = _MAX_FOCUS) -> list[str]:
    """BUY/SELL research symbols for ITE evaluation when live trading is ENABLED.

    Empty when the controller is not ENABLED. Does not authorize an order.
    """
    auth = live_authorization_snapshot()
    if not auth.get("orders_may_submit"):
        return []
    return research_scan_focus_symbols(limit=limit)


def merge_research_into_execution_handoff(
    eligible: Sequence[str] | Iterable[str],
    *,
    universe: Sequence[str] | Iterable[str] | None = None,
    research_focus: Sequence[str] | None = None,
    limit: int = _MAX_FOCUS,
) -> list[str]:
    """Prefer cached research BUY/SELL symbols already in the scan universe.

    Symbols outside the current execution universe are not injected.
    Scanner-eligible symbols are never dropped to make room for extras.
    ITE still evaluates strategy/risk/OMS and may WAIT.
    """
    focus = [
        str(s).strip().upper()
        for s in (
            research_focus
            if research_focus is not None
            else research_live_focus_symbols()
        )
        if str(s).strip()
    ]
    ordered = _clamp_handoff_to_execution_policy(
        prefer_allowlisted_handoff(eligible, focus)
    )
    if not focus:
        return ordered
    uni = {str(s).strip().upper() for s in (universe or ()) if str(s).strip()}
    if not uni:
        return ordered
    seen = set(ordered)
    extra: list[str] = []
    for sym in focus:
        if sym in seen:
            continue
        if not execution_symbol_allowed(sym, uni):
            continue
        extra.append(sym)
        seen.add(sym)
    universe_cap = max(len(ordered), min(int(limit or _MAX_FOCUS), _MAX_FOCUS))
    extras_room = max(0, universe_cap - len(ordered))
    merged = extra[:extras_room] + ordered
    return _clamp_handoff_to_execution_policy(merged)


def signal_execution_status(
    row: dict[str, Any] | None,
    *,
    live_state: str | None = None,
    orders_ok: bool = False,
    research_focus: Sequence[str] | None = None,
    open_symbols: Sequence[str] | None = None,
) -> str:
    """Per-signal execution label. Never claims a fill without a ticket/position."""
    if not isinstance(row, dict):
        return "RESEARCH_ONLY"
    pipe = row.get("pipeline") if isinstance(row.get("pipeline"), dict) else {}
    lifecycle = str(
        pipe.get("execution_lifecycle") or row.get("execution_state") or ""
    ).strip().upper()
    ticket = pipe.get("ticket") or row.get("ticket")
    direction = str(row.get("direction") or "").strip().upper()
    sym = str(row.get("symbol") or row.get("broker_symbol") or "").strip().upper()
    open_set = {str(s).strip().upper() for s in (open_symbols or ()) if str(s).strip()}
    open_keys = {_desk_key(s) for s in open_set}
    if sym and (sym in open_set or _desk_key(sym) in open_keys):
        return "POSITION_OPEN"
    if ticket and lifecycle in {"ORDER_SENT", "EXECUTING", "FILLED"}:
        return "ORDER_SUBMITTED"
    if ticket and str(pipe.get("broker") or "").upper() in {"SUBMITTED", "ACK"}:
        return "ORDER_SUBMITTED"
    if lifecycle == "FILLED" and not ticket:
        return "EXECUTION_BLOCKED"
    oms = str(pipe.get("oms") or row.get("oms") or "").strip().upper()
    risk = str(pipe.get("risk") or row.get("risk") or "").strip().upper()
    abort = str(
        pipe.get("abort_reason") or row.get("abort_reason") or ""
    ).strip().upper()
    if risk in {"REJECT", "REJECTED", "BLOCK"} or "RISK" in abort:
        return "RISK_BLOCKED"
    if oms in {"REJECT", "REJECTED", "BLOCK"}:
        return "EXECUTION_BLOCKED"
    if _row_is_stale(row):
        return "EXPIRED"
    if lifecycle == "EXECUTION_BLOCKED":
        return "EXECUTION_BLOCKED"
    state = str(live_state or "").strip().upper()
    if state in {"ARMED", "READY_FOR_REVIEW"} and direction in _BUY_SELL:
        return "READY_FOR_REVIEW"
    if state not in {"ENABLED", "LIVE_ENABLED"}:
        return "RESEARCH_ONLY"
    if direction not in _BUY_SELL:
        return "RESEARCH_ONLY"
    if not _symbol_in_execution_universe(sym):
        return "RESEARCH_ONLY"
    focus = {str(s).strip().upper() for s in (research_focus or ()) if str(s).strip()}
    focus_keys = {_desk_key(s) for s in focus}
    if (
        focus
        and not _gold_only_execution()
        and sym not in focus
        and _desk_key(sym) not in focus_keys
    ):
        return "RESEARCH_ONLY"
    if not orders_ok:
        return "EXECUTION_BLOCKED"
    return "LIVE_ELIGIBLE"


def signal_card_lifecycle(
    row: dict[str, Any] | None,
    *,
    execution_status: str | None = None,
    scan_eligible: Sequence[str] | None = None,
) -> dict[str, str]:
    """Shared card/Telegram lifecycle. Never claims EXECUTED without a ticket."""
    status = str(execution_status or "").strip().upper()
    if not isinstance(row, dict):
        return {
            "lifecycle": "DISCOVERED",
            "card_status": "WAITING",
            "reason": "NO_SIGNAL_ROW",
        }
    pipe = row.get("pipeline") if isinstance(row.get("pipeline"), dict) else {}
    ticket = pipe.get("ticket") or row.get("ticket") or row.get("mt5_ticket")
    try:
        ticket_n = int(ticket) if ticket not in (None, "", "0", 0) else 0
    except (TypeError, ValueError):
        ticket_n = 0
    reason = str(
        pipe.get("abort_reason")
        or row.get("abort_reason")
        or row.get("block_code")
        or row.get("reject_reason")
        or row.get("waiting_reason")
        or ""
    ).strip()
    direction = str(row.get("direction") or "").strip().upper()
    if ticket_n > 0:
        return {
            "lifecycle": "EXECUTED",
            "card_status": "EXECUTED",
            "reason": reason or "MT5_TICKET",
        }
    if status == "POSITION_OPEN":
        if ticket_n > 0:
            return {
                "lifecycle": "EXECUTED",
                "card_status": "EXECUTED",
                "reason": reason or "POSITION_OPEN",
            }
        return {
            "lifecycle": "WAITING",
            "card_status": "WAITING",
            "reason": reason or "POSITION_OPEN",
        }
    if status == "EXPIRED" or _row_is_stale(row):
        return {
            "lifecycle": "EXPIRED",
            "card_status": "EXPIRED",
            "reason": reason or "STALE_SIGNAL",
        }
    if status == "RISK_BLOCKED":
        return {
            "lifecycle": "RISK_REJECTED",
            "card_status": "RISK_BLOCKED",
            "reason": reason or "RISK_REJECTED",
        }
    abort = str(pipe.get("abort_reason") or row.get("abort_reason") or "").upper()
    oms = str(pipe.get("oms") or "").upper()
    if "MIN_LOT" in abort or "SIZING" in abort:
        return {
            "lifecycle": "SIZING_REJECTED",
            "card_status": "REJECTED",
            "reason": reason or abort or "SIZING_REJECTED",
        }
    if oms in {"REJECT", "REJECTED", "BLOCK"} or "OMS" in abort:
        return {
            "lifecycle": "OMS_REJECTED",
            "card_status": "REJECTED",
            "reason": reason or abort or "OMS_REJECTED",
        }
    if "BROKER" in abort:
        return {
            "lifecycle": "BROKER_REJECTED",
            "card_status": "REJECTED",
            "reason": reason or abort or "BROKER_REJECTED",
        }
    lifecycle = str(pipe.get("execution_lifecycle") or "").upper()
    if status == "EXECUTION_BLOCKED" or lifecycle == "EXECUTION_BLOCKED":
        return {
            "lifecycle": "EXECUTION_ERROR"
            if "ERROR" in abort or "TIMEOUT" in abort
            else "FILTERED",
            "card_status": "REJECTED",
            "reason": reason or abort or "EXECUTION_BLOCKED",
        }
    if status == "ORDER_SUBMITTED":
        return {
            "lifecycle": "ORDER_SUBMITTED",
            "card_status": "WAITING",
            "reason": reason or "AWAITING_BROKER_TICKET",
        }
    if status == "READY_FOR_REVIEW":
        return {
            "lifecycle": "STRATEGY_VALID",
            "card_status": "WAITING",
            "reason": reason or "READY_FOR_REVIEW",
        }
    if status == "RESEARCH_ONLY" or direction not in _BUY_SELL:
        return {
            "lifecycle": "DISCOVERED" if direction not in _BUY_SELL else "FILTERED",
            "card_status": "WAITING" if direction not in _BUY_SELL else "REJECTED",
            "reason": reason
            or ("NO_DIRECTION" if direction not in _BUY_SELL else "RESEARCH_ONLY"),
        }
    eligible = {str(s).strip().upper() for s in (scan_eligible or ()) if str(s).strip()}
    sym = str(row.get("symbol") or row.get("broker_symbol") or "").strip().upper()
    opp = row.get("opportunity_eligible")
    desk_keys = {_desk_key(s) for s in eligible}
    in_scan = bool(sym) and (sym in eligible or _desk_key(sym) in desk_keys)
    if opp is True or (eligible and in_scan):
        missing = reason or str(row.get("reject_reason") or "WAITING_FOR_SETUP")
        if opp is True and not reason:
            missing = "STRATEGY_PENDING"
        return {
            "lifecycle": "TRADEABLE" if opp is True else "ANALYZING",
            "card_status": "TRADEABLE" if opp is True else "WAITING",
            "reason": missing,
        }
    return {
        "lifecycle": "WAITING",
        "card_status": "WAITING",
        "reason": reason or "WAITING_FOR_SETUP",
    }


def _gold_only_execution() -> bool:
    try:
        from app.domain.trading.gold_only import gold_only_enabled

        return bool(gold_only_enabled())
    except Exception:
        return False


def _clamp_handoff_to_execution_policy(
    symbols: Sequence[str] | Iterable[str],
) -> list[str]:
    """Research focus must not re-inject desks outside the live execution universe."""
    out = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not _gold_only_execution():
        return out
    try:
        from app.domain.trading.gold_only import filter_autonomous_symbols

        return list(filter_autonomous_symbols(out))
    except Exception:
        logger.exception("research_handoff_gold_clamp_failed")
        return [s for s in out if _desk_key(s) in {"XAUUSD", "GOLD"}]


def _symbol_in_execution_universe(sym: str) -> bool:
    if not sym:
        return False
    try:
        return bool(execution_symbol_allowed(sym))
    except Exception:
        if not _gold_only_execution():
            return False
        try:
            from app.domain.trading.gold_only import is_gold_symbol

            return bool(is_gold_symbol(sym))
        except Exception:
            return _desk_key(sym) in {"XAUUSD", "GOLD"}


def overlay_cycle_matches_row(row: dict[str, Any], last: dict[str, Any]) -> bool:
    """True when last ITE cycle should paint this signal row."""
    row_sym = str(row.get("symbol") or row.get("broker_symbol") or "").strip().upper()
    last_sym = str(last.get("symbol") or last.get("fill_symbol") or "").strip().upper()
    if not last_sym or not row_sym:
        return True
    if row_sym == last_sym:
        return True
    return _desk_key(row_sym) == _desk_key(last_sym)


def _desk_key(sym: str) -> str:
    return (
        str(sym or "")
        .strip()
        .upper()
        .replace("_I", "")
        .replace(".I", "")
        .replace("-", "")
    )


def _research_signal_rows(snap: dict[str, Any]) -> list[dict[str, Any]]:
    board = snap.get("opportunity_board")
    rows: list[Any] = []
    if isinstance(board, dict):
        rows = list(board.get("live_ranked") or board.get("rows") or [])
    rs = snap.get("research_signals")
    if isinstance(rs, dict) and not rows:
        rows = list(rs.get("signals") or [])
    return [r for r in rows if isinstance(r, dict)]


def _row_is_stale(row: dict[str, Any]) -> bool:
    freshness = str(row.get("freshness") or row.get("data_state") or "").strip().upper()
    return freshness in _STALE


def _score(row: dict[str, Any]) -> float:
    for key in ("opportunity_score", "research_rank_score", "score", "quality"):
        raw = row.get(key)
        try:
            if raw is not None and raw != "":
                return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0
