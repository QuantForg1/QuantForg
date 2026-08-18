"""Read-only canonical autonomous execution context for Terminal / ops.

Does not submit orders, change Safety/Risk/OMS/Gateway, or call MT5.
Composes already-available in-process ITE / PME / last-cycle facts.

MT5 visible chart is NOT execution authority. Gateway has no ChartSetSymbol
API — ``symbol_select`` is a quotes/Market Watch probe, not chart focus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

MANUAL_HOME_SYMBOL = "XAUUSD_i"
MT5_CHART_SYNC = "unsupported"
MT5_CHART_SYNC_REASON = (
    "Gateway exposes quotes/symbol_select (Market Watch activation), "
    "not ChartSetSymbol. MT5 visible chart is display-only and must not "
    "override executionDecision.symbol."
)
SYMBOL_SOURCE_AUTONOMOUS = "AUTONOMOUS_EXECUTION"
SYMBOL_SOURCE_MANUAL = "MANUAL"

TERMINAL_MANUAL = "MANUAL"
TERMINAL_PENDING = "AUTONOMOUS_PENDING"
TERMINAL_EXECUTING = "AUTONOMOUS_EXECUTING"
TERMINAL_POSITION_OPEN = "AUTONOMOUS_POSITION_OPEN"
TERMINAL_POSITION_CLOSING = "AUTONOMOUS_POSITION_CLOSING"
TERMINAL_RECONCILIATION = "AUTONOMOUS_RECONCILIATION"
TERMINAL_RETURNING = "RETURNING_TO_MANUAL"

STATUS_IDLE = "IDLE"
STATUS_PENDING = "PENDING"
STATUS_EXECUTING = "EXECUTING"
STATUS_POSITION_OPEN = "POSITION_OPEN"
STATUS_POSITION_CLOSING = "POSITION_CLOSING"
STATUS_RECONCILIATION = "RECONCILIATION"
STATUS_CLOSED = "CLOSED"

MT5_CONNECTED = "MT5_CONNECTED"
MT5_CONNECTING = "MT5_CONNECTING"
MT5_UNAVAILABLE = "MT5_UNAVAILABLE"
GATEWAY_UNAVAILABLE = "GATEWAY_UNAVAILABLE"
BROKER_SYMBOL_UNAVAILABLE = "BROKER_SYMBOL_UNAVAILABLE"
SYMBOL_NOT_TRADEABLE = "SYMBOL_NOT_TRADEABLE"
NO_LIVE_TICK = "NO_LIVE_TICK"
EXECUTION_REJECTED = "EXECUTION_REJECTED"
RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def collect_pme_positions_from_runtime(runtime: Any) -> list[dict[str, Any]]:
    """In-process PME rows only — no Gateway I/O."""
    rows: list[dict[str, Any]] = []
    if runtime is None:
        return rows
    try:
        engine = getattr(getattr(runtime, "position_management", None), "engine", None)
        positions = getattr(engine, "_positions", None) or {}
        for ticket, pos in positions.items():
            state = _text(
                getattr(getattr(pos, "state", None), "value", None)
                or getattr(pos, "state", "")
            ).upper()
            if state == "EXITED":
                continue
            symbol = _text(getattr(pos, "symbol", ""))
            if not symbol:
                continue
            rows.append(
                {
                    "position_id": str(getattr(pos, "ticket", ticket)),
                    "symbol": symbol,
                    "side": _text(getattr(pos, "side", "")).lower(),
                    "volume": str(getattr(pos, "remaining_volume", "") or ""),
                    "state": state or "OPEN",
                    "entry": str(getattr(pos, "entry_price", "") or ""),
                }
            )
    except Exception:
        return rows
    return rows


def _resolve_broker_symbol(symbol: str, diagnostics: dict[str, Any]) -> str | None:
    """Reuse existing catalogue resolver. Never invent a suffix."""
    raw = _text(
        diagnostics.get("broker_symbol_resolved")
        or diagnostics.get("resolved_symbol")
        or diagnostics.get("symbol")
        or symbol
    )
    if not raw:
        return None
    try:
        from app.domain.institutional_trading.ai_scalping.universe_discovery import (
            resolve_seed_to_broker_symbol,
        )

        rows = diagnostics.get("broker_symbol_rows")
        if isinstance(rows, (list, tuple)) and rows:
            return resolve_seed_to_broker_symbol(raw, broker_symbol_rows=rows) or raw
        return resolve_seed_to_broker_symbol(raw, discovered=()) or raw
    except Exception:
        return raw.upper()


def _classify_mt5_status(
    *,
    gateway_connected: bool | None,
    broker_connected: bool | None,
) -> str:
    if gateway_connected is False:
        return GATEWAY_UNAVAILABLE
    if broker_connected is False:
        return MT5_UNAVAILABLE
    if gateway_connected is None or broker_connected is None:
        return MT5_CONNECTING
    if broker_connected:
        return MT5_CONNECTED
    return MT5_UNAVAILABLE


def _failure_mode(
    *,
    mt5_status: str,
    abort: str,
    cycle_outcome: str,
    diagnostics: dict[str, Any],
) -> str:
    abort_u = abort.upper()
    outcome_u = cycle_outcome.upper()
    if "RECONCIL" in abort_u or "RECONCIL" in outcome_u or abort_u == "UNKNOWN":
        return RECONCILIATION_REQUIRED
    if mt5_status == GATEWAY_UNAVAILABLE:
        return GATEWAY_UNAVAILABLE
    if mt5_status == MT5_UNAVAILABLE:
        return MT5_UNAVAILABLE
    joined = " ".join(
        [
            abort_u,
            outcome_u,
            _text(diagnostics.get("market_context_reason")).upper(),
            _text(diagnostics.get("ticks")).upper(),
            _text(diagnostics.get("trade_mode")).upper(),
        ]
    )
    if (
        "NO_LIVE_TICK" in joined
        or joined.strip() == "STALE"
        or ("TICK" in abort_u and "NONE" in abort_u)
    ):
        return NO_LIVE_TICK
    if "NOT_TRADEABLE" in joined or "TRADE_DISABLED" in joined or "CLOSEONLY" in joined:
        return SYMBOL_NOT_TRADEABLE
    if (
        "BROKER_SYMBOL" in joined
        or "UNKNOWN_SYMBOL" in joined
        or "SYMBOL_UNAVAILABLE" in joined
    ):
        return BROKER_SYMBOL_UNAVAILABLE
    if abort_u and abort_u not in {"", "NONE", "OK", "SUCCESS"}:
        return EXECUTION_REJECTED
    return "NONE"


@dataclass(frozen=True, slots=True)
class AutonomousExecutionContext:
    """Canonical live execution view — not an order path."""

    execution_id: str | None
    symbol: str | None
    broker_symbol: str | None
    side: str | None
    status: str
    order_id: str | None
    position_id: str | None
    source: str
    timestamp: str
    manual_symbol: str
    terminal_mode: str
    active_execution_symbol: str | None
    terminal_symbol: str
    position_symbols: tuple[str, ...]
    open_position_count: int
    unresolved_order_count: int
    execution_status: str
    mt5_status: str
    mt5_chart_symbol: str | None
    mt5_chart_sync: str
    mt5_chart_sync_reason: str
    symbol_source: str
    failure_mode: str
    position_id_list: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "symbol": self.symbol,
            "broker_symbol": self.broker_symbol,
            "side": self.side,
            "status": self.status,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "source": self.source,
            "timestamp": self.timestamp,
            "manual_symbol": self.manual_symbol,
            "terminal_mode": self.terminal_mode,
            "active_execution_symbol": self.active_execution_symbol,
            "terminal_symbol": self.terminal_symbol,
            "execution_symbol": self.symbol,
            "position_symbol": self.position_symbols[0]
            if self.position_symbols
            else None,
            "position_symbols": list(self.position_symbols),
            "open_position_count": self.open_position_count,
            "unresolved_order_count": self.unresolved_order_count,
            "execution_status": self.execution_status,
            "mt5_status": self.mt5_status,
            "mt5_chart_symbol": self.mt5_chart_symbol,
            "mt5_chart_sync": self.mt5_chart_sync,
            "mt5_chart_sync_reason": self.mt5_chart_sync_reason,
            "symbol_source": self.symbol_source,
            "failure_mode": self.failure_mode,
            "position_ids": list(self.position_id_list),
        }


def build_autonomous_execution_context(
    *,
    orchestrator: dict[str, Any] | None = None,
    recent_attempts: list[dict[str, Any]] | None = None,
    pme_positions: list[dict[str, Any]] | None = None,
    live: dict[str, Any] | None = None,
    gateway_connected: bool | None = None,
    broker_connected: bool | None = None,
    now: datetime | None = None,
) -> AutonomousExecutionContext:
    orch = _as_dict(orchestrator)
    last = _as_dict(orch.get("last_cycle"))
    live_d = _as_dict(live)
    diag = _as_dict(last.get("market_context_diagnostics"))
    attempts = [a for a in (recent_attempts or []) if isinstance(a, dict)]

    if gateway_connected is None:
        gateway_connected = live_d.get("gateway_connected")
        if gateway_connected is None:
            gateway_connected = live_d.get("gateway_available")
    if broker_connected is None:
        broker_connected = live_d.get("broker_connected")
        if broker_connected is None:
            broker_connected = live_d.get("mt5_connected")

    mt5_status = _classify_mt5_status(
        gateway_connected=None
        if gateway_connected is None
        else bool(gateway_connected),
        broker_connected=None if broker_connected is None else bool(broker_connected),
    )

    positions = [
        row
        for row in (pme_positions or [])
        if isinstance(row, dict) and _text(row.get("symbol"))
    ]
    position_symbols = tuple(_text(r.get("symbol")) for r in positions)
    position_ids = tuple(
        _text(r.get("position_id"))
        for r in positions
        if r.get("position_id") is not None
    )
    open_count = len(positions)

    forwarded = bool(last.get("forwarded_to_oms"))
    ticket = last.get("mt5_ticket")
    has_ticket = ticket is not None and _text(ticket) != ""
    action = _text(last.get("decision_action")).upper()
    buy_sell = action in {"BUY", "SELL"}
    abort = _text(last.get("abort_reason"))
    abort_soft = abort.upper() in {"", "NONE", "OK", "SUCCESS"}
    cycle_outcome = _text(last.get("cycle_outcome"))
    closing = "CLOSE" in cycle_outcome.upper() or "CLOSING" in abort.upper()

    unresolved_orders = 0
    if forwarded and open_count == 0 and buy_sell and abort_soft:
        unresolved_orders = 1
    if attempts:
        latest = attempts[0]
        status = _text(latest.get("status")).lower()
        if status in {"forwarded"} and not latest.get("mt5_ticket") and open_count == 0:
            unresolved_orders = max(unresolved_orders, 1)

    execution_symbol = _text(diag.get("symbol")) or None
    if not execution_symbol and buy_sell and attempts:
        execution_symbol = _text(attempts[0].get("symbol")) or None
    broker_symbol = (
        _resolve_broker_symbol(execution_symbol or "", diag)
        if execution_symbol
        else None
    )

    side = (
        action.lower()
        if buy_sell
        else (_text(positions[0].get("side")).lower() if positions else None) or None
    )
    execution_id = _text(last.get("trace_id") or last.get("signal_id")) or None
    order_id = _text(ticket) if has_ticket else None
    position_id = position_ids[0] if position_ids else None

    failure = _failure_mode(
        mt5_status=mt5_status,
        abort=abort,
        cycle_outcome=cycle_outcome,
        diagnostics=diag,
    )

    reconnecting = mt5_status in {MT5_UNAVAILABLE, GATEWAY_UNAVAILABLE, MT5_CONNECTING}
    reconciling = failure == RECONCILIATION_REQUIRED or (
        reconnecting and (open_count > 0 or unresolved_orders > 0 or forwarded)
    )

    if reconciling and (
        open_count > 0 or unresolved_orders > 0 or forwarded or buy_sell
    ):
        status = STATUS_RECONCILIATION
        terminal_mode = TERMINAL_RECONCILIATION
    elif open_count > 1 or (open_count == 1 and not closing):
        status = STATUS_POSITION_OPEN
        terminal_mode = TERMINAL_POSITION_OPEN
    elif open_count == 1 and closing:
        status = STATUS_POSITION_CLOSING
        terminal_mode = TERMINAL_POSITION_CLOSING
    elif forwarded and buy_sell and abort_soft:
        status = STATUS_EXECUTING
        terminal_mode = TERMINAL_EXECUTING
    elif buy_sell and not forwarded and abort_soft:
        status = STATUS_PENDING
        terminal_mode = TERMINAL_PENDING
    elif failure == EXECUTION_REJECTED:
        status = STATUS_IDLE
        terminal_mode = TERMINAL_MANUAL
        execution_symbol = None
        broker_symbol = None
    else:
        status = STATUS_IDLE
        terminal_mode = TERMINAL_MANUAL

    autonomous = terminal_mode not in {TERMINAL_MANUAL, TERMINAL_RETURNING}
    focus_symbol = None
    if autonomous:
        focus_symbol = (
            position_symbols[0]
            if position_symbols
            else (broker_symbol or execution_symbol)
        )
    terminal_symbol = focus_symbol or MANUAL_HOME_SYMBOL
    source = SYMBOL_SOURCE_AUTONOMOUS if autonomous else SYMBOL_SOURCE_MANUAL
    stamp = (now or datetime.now(UTC)).isoformat()

    return AutonomousExecutionContext(
        execution_id=execution_id,
        symbol=execution_symbol or (position_symbols[0] if position_symbols else None),
        broker_symbol=broker_symbol
        or (position_symbols[0] if position_symbols else None),
        side=side or None,
        status=status,
        order_id=order_id,
        position_id=position_id,
        source=source,
        timestamp=stamp,
        manual_symbol=MANUAL_HOME_SYMBOL,
        terminal_mode=terminal_mode,
        active_execution_symbol=focus_symbol,
        terminal_symbol=terminal_symbol,
        position_symbols=position_symbols,
        open_position_count=open_count,
        unresolved_order_count=unresolved_orders,
        execution_status=status,
        mt5_status=mt5_status,
        mt5_chart_symbol=None,
        mt5_chart_sync=MT5_CHART_SYNC,
        mt5_chart_sync_reason=MT5_CHART_SYNC_REASON,
        symbol_source=source,
        failure_mode=failure if autonomous or failure != "NONE" else "NONE",
        position_id_list=position_ids,
    )
