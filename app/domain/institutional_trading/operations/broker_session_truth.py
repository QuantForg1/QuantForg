"""Broker-authoritative session truth for Gold autonomous entries.

UTC named-session classification remains the soft quality source.
Hard open/closed for new entries follows broker/symbol truth whenever
that evidence is available. Never hard-codes a desk clock as "allowed".
Does not bypass Risk, OMS, or kill switch.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.market_context.enums import MarketSession
from core.logging import get_logger

logger = get_logger(__name__)

BROKER_SESSION_CLOSED = "BROKER_SESSION_CLOSED"
BROKER_SESSION_OPEN = "BROKER_SESSION_OPEN"
SAFETY_SESSION_CLOSED = "SAFETY_SESSION_CLOSED"
SAFETY_SESSION_OPEN = "SAFETY_SESSION_OPEN"
UNKNOWN = "UNKNOWN"
SESSION_STATE_INCONSISTENCY = "SESSION_STATE_INCONSISTENCY"
SESSION_OPEN_DETECTED = "SESSION_OPEN_DETECTED"

_CLOSE_ONLY = frozenset({"closeonly", "close_only", "3"})
_DISABLED = frozenset({"disabled", "0"})
_OPEN_MODES = frozenset(
    {"full", "longonly", "shortonly", "long_only", "short_only", "4", "1", "2"}
)
_CLOSED_UTC = frozenset({MarketSession.OFF_HOURS.value, MarketSession.CLOSED.value})

_LOCK = threading.Lock()
_LAST_BROKER: str = UNKNOWN
_LAST_TRANSITION: str | None = None
_LAST_TRANSITION_MONO: float = 0.0


@dataclass(frozen=True, slots=True)
class BrokerSessionSnapshot:
    broker_session: str
    safety_session: str
    utc_session: str
    broker_session_open: bool | None
    safety_allowed: bool
    inconsistency: bool
    session_source: str
    reason: str
    broker_server_time: str | None
    local_time: str
    next_expected_open: str | None
    session_age_ms: int | None
    last_session_transition: str | None
    trade_mode: str
    trade_allowed: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_state": self.broker_session,
            "broker_session": self.broker_session,
            "safety_session": self.safety_session,
            "utc_session": self.utc_session,
            "broker_session_open": self.broker_session_open,
            "safety_allowed": self.safety_allowed,
            "inconsistency": self.inconsistency,
            "session_source": self.session_source,
            "schedule_source": self.session_source,
            "reason": self.reason,
            "broker_server_time": self.broker_server_time,
            "local_time": self.local_time,
            "timezone": "UTC",
            "next_expected_open": self.next_expected_open,
            "session_age_ms": self.session_age_ms,
            "last_session_transition": self.last_session_transition,
            "last_refresh": self.local_time,
            "trade_mode": self.trade_mode,
            "trade_allowed": self.trade_allowed,
        }


def reset_broker_session_truth() -> None:
    """Test helper — drop transition memory."""
    global _LAST_BROKER, _LAST_TRANSITION, _LAST_TRANSITION_MONO
    with _LOCK:
        _LAST_BROKER = UNKNOWN
        _LAST_TRANSITION = None
        _LAST_TRANSITION_MONO = 0.0


def _norm_mode(raw: Any) -> str:
    return str(raw or "").strip().lower().replace(" ", "")


def classify_broker_session_open(
    *,
    trade_mode: str | None = None,
    trade_allowed: bool | None = None,
    market_open: bool | None = None,
    market_data_live: bool | None = None,
    cooled: bool = False,
) -> bool | None:
    """True=open, False=closed, None=unknown. Never invents open."""
    mode = _norm_mode(trade_mode)
    if cooled and (
        mode in _CLOSE_ONLY or trade_allowed is False or market_open is False
    ):
        return False
    if mode in _CLOSE_ONLY or mode in _DISABLED:
        return False
    if trade_allowed is False:
        return False
    if market_open is False:
        return False
    if mode in _OPEN_MODES and trade_allowed is True:
        return True
    if mode in _OPEN_MODES and market_data_live is True and trade_allowed is not False:
        return True
    if trade_allowed is True and market_data_live is True and not mode:
        return True
    return None


def _next_expected_open_utc(*, broker_open: bool | None, now: datetime) -> str | None:
    if broker_open is True:
        return None
    # Weltrade / FX gold typically re-opens Sunday ~22:00 UTC after weekend.
    if now.weekday() >= 5:
        days_ahead = 6 - now.weekday()  # Sunday
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=22, minute=0, second=0, microsecond=0
        )
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def build_broker_session_snapshot(
    *,
    utc_session: str,
    broker_open: bool | None,
    trade_mode: str = "",
    trade_allowed: bool | None = None,
    broker_server_time: str | None = None,
    now: datetime | None = None,
) -> BrokerSessionSnapshot:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    utc_key = str(utc_session or "").strip().lower() or MarketSession.OFF_HOURS.value
    utc_closed = utc_key in _CLOSED_UTC
    inconsistency = broker_open is True and utc_closed
    if broker_open is True:
        broker_state = BROKER_SESSION_OPEN
        safety_state = SAFETY_SESSION_OPEN
        safety_allowed = True
        source = "broker_symbol_trade_mode"
        reason = (
            f"{SESSION_STATE_INCONSISTENCY}: UTC '{utc_key}' vs broker OPEN"
            if inconsistency
            else f"{BROKER_SESSION_OPEN} (utc={utc_key})"
        )
    elif broker_open is False:
        broker_state = BROKER_SESSION_CLOSED
        safety_state = SAFETY_SESSION_CLOSED
        safety_allowed = False
        source = "broker_symbol_trade_mode"
        reason = (
            f"{BROKER_SESSION_CLOSED} (utc={utc_key} trade_mode={trade_mode or '-'})"
        )
    else:
        broker_state = UNKNOWN
        safety_allowed = not utc_closed
        safety_state = SAFETY_SESSION_OPEN if safety_allowed else SAFETY_SESSION_CLOSED
        source = "utc_classifier"
        reason = (
            f"UTC session '{utc_key}'"
            if safety_allowed
            else f"Session '{utc_key}' not allowed"
        )
    with _LOCK:
        age_ms = (
            int((time.monotonic() - _LAST_TRANSITION_MONO) * 1000)
            if _LAST_TRANSITION_MONO > 0
            else None
        )
        last_tr = _LAST_TRANSITION
    return BrokerSessionSnapshot(
        broker_session=broker_state,
        safety_session=safety_state,
        utc_session=utc_key,
        broker_session_open=broker_open,
        safety_allowed=safety_allowed,
        inconsistency=inconsistency,
        session_source=source,
        reason=reason,
        broker_server_time=broker_server_time,
        local_time=moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        next_expected_open=_next_expected_open_utc(
            broker_open=broker_open, now=moment
        ),
        session_age_ms=age_ms,
        last_session_transition=last_tr,
        trade_mode=str(trade_mode or ""),
        trade_allowed=trade_allowed,
    )


def note_broker_session(broker_open: bool | None) -> str | None:
    """Record transition. Returns SESSION_OPEN_DETECTED when closed→open."""
    global _LAST_BROKER, _LAST_TRANSITION, _LAST_TRANSITION_MONO
    if broker_open is True:
        state = BROKER_SESSION_OPEN
    elif broker_open is False:
        state = BROKER_SESSION_CLOSED
    else:
        state = UNKNOWN
    event: str | None = None
    with _LOCK:
        prev = _LAST_BROKER
        if (
            prev in {BROKER_SESSION_CLOSED, UNKNOWN}
            and state == BROKER_SESSION_OPEN
        ):
            event = SESSION_OPEN_DETECTED
            _LAST_TRANSITION = event
            _LAST_TRANSITION_MONO = time.monotonic()
        elif prev != state and state != UNKNOWN:
            _LAST_TRANSITION = f"{prev}->{state}"
            _LAST_TRANSITION_MONO = time.monotonic()
        _LAST_BROKER = state
    return event


def overlay_snapshot_session(snapshot: Any, *, broker_open: bool | None) -> Any:
    """When broker is open, do not let UTC off_hours fail eligibility."""
    if snapshot is None or broker_open is not True:
        return snapshot
    sess = getattr(snapshot, "session", None)
    if sess is None or bool(getattr(sess, "allowed", False)):
        return snapshot
    utc_name = str(
        getattr(getattr(sess, "session", None), "value", None)
        or getattr(sess, "session", None)
        or MarketSession.OFF_HOURS.value
    )
    new_sess = replace(
        sess,
        allowed=True,
        reason=(
            f"BROKER_SESSION_OPEN overrides UTC '{utc_name}' "
            "(broker trade_mode is the session authority)"
        ),
    )
    try:
        return replace(snapshot, session=new_sess)
    except Exception:
        return snapshot


def apply_session_open_side_effects(*, symbol: str | None, event: str | None) -> None:
    """Clear stale market-closed cooldown and wake the next cycle."""
    if event != SESSION_OPEN_DETECTED:
        return
    try:
        from app.application.services.market_closed_cooldown import clear_market_closed

        clear_market_closed(symbol)
    except Exception:
        logger.exception("session_open_clear_cooldown_failed")
    try:
        from app.domain.institutional_trading.operations.decision_cycle import (
            note_cycle_event,
        )

        note_cycle_event("session_open")
    except Exception:
        logger.exception("session_open_wakeup_failed")
    try:
        logger.warning(
            SESSION_OPEN_DETECTED,
            symbol=symbol,
            event=event,
        )
    except Exception:
        logger.exception("session_open_log_failed")


def resolve_from_diagnostics(
    diagnostics: dict[str, Any] | None,
    *,
    utc_session: str,
    symbol_tradable: bool = False,
    market_data_live: bool = False,
    cooled: bool = False,
) -> BrokerSessionSnapshot:
    diag = dict(diagnostics or {})
    explicit = diag.get("broker_session_open")
    trade_mode = str(
        diag.get("symbol_trade_mode") or diag.get("trade_mode") or ""
    )
    raw_allowed = diag.get("symbol_trade_allowed")
    if raw_allowed is None:
        raw_allowed = diag.get("trade_allowed")
    trade_allowed: bool | None
    if raw_allowed is True or raw_allowed is False:
        trade_allowed = bool(raw_allowed)
    else:
        trade_allowed = None
    market_open = diag.get("symbol_market_open")
    if market_open is None:
        market_open = diag.get("market_open")
    if market_open is True or market_open is False:
        market_open_b: bool | None = bool(market_open)
    else:
        market_open_b = None
    if explicit is True or explicit is False:
        broker_open: bool | None = bool(explicit)
    else:
        broker_open = classify_broker_session_open(
            trade_mode=trade_mode,
            trade_allowed=trade_allowed,
            market_open=market_open_b,
            market_data_live=market_data_live or symbol_tradable,
            cooled=cooled,
        )
        if broker_open is None and symbol_tradable and market_data_live and trade_mode:
            broker_open = classify_broker_session_open(
                trade_mode=trade_mode,
                trade_allowed=True if trade_allowed is None else trade_allowed,
                market_open=market_open_b,
                market_data_live=True,
                cooled=cooled,
            )
    return build_broker_session_snapshot(
        utc_session=utc_session,
        broker_open=broker_open,
        trade_mode=trade_mode,
        trade_allowed=trade_allowed,
        broker_server_time=str(diag.get("server_time") or "") or None,
    )
