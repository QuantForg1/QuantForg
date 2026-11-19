"""Read-only Decision Intelligence reports.

Projects an existing Signal Center row (and existing signal-history rows)
into an explanation. Does not score, size, authorize, or send orders.
Missing engine fields stay missing.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_ENGINE_DECISIONS = {
    "BUY",
    "SELL",
    "WAIT",
    "HOLD",
    "REJECT",
    "NO_TRADE",
    "EXECUTION_BLOCKED",
}
_NOT_AVAILABLE = "Not available"
_AWAITING = "Awaiting engine evidence"
_ORDER_NOTE = (
    "A BUY or SELL value is a research or strategy decision. "
    "It is not proof that an order was executed."
)
_HISTORY_NOTE = (
    "This historical signal record did not preserve every live field. "
    "Missing market, risk, and execution values stay unavailable. "
    "They are not reconstructed from the current market."
)
_RISK_NOTE = (
    "Risk results are copied from the signal record. "
    "This report does not calculate or replace a risk value."
)


def evidence_contract() -> dict[str, Any]:
    """Flags the report always publishes. Does not read signals or orders."""
    return {
        "read_only": True,
        "executes_orders": False,
        "invents_reasoning": False,
        "calculates_risk": False,
        "decision_is_not_an_order": True,
        "history_observation": False,
        "history_note": _HISTORY_NOTE,
    }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "—", "-", "None", "null", "UNKNOWN"}
    if isinstance(value, (list, dict, tuple)):
        return len(value) > 0
    return True


def _text(value: Any) -> str | None:
    if not _present(value):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".8g")
    if isinstance(value, (list, dict, tuple)):
        return None
    return str(value)[:500]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _decision_label(row: dict[str, Any]) -> str:
    detail = _dict(row.get("detail"))
    for raw in (
        row.get("decision"),
        row.get("direction"),
        row.get("signal_action"),
        detail.get("signal_action"),
    ):
        label = str(raw or "").strip().upper().replace(" ", "_")
        if label in _ENGINE_DECISIONS:
            return label
    return _NOT_AVAILABLE


def _timestamp(row: dict[str, Any], feed: dict[str, Any]) -> str | None:
    for raw in (
        row.get("time_generated"),
        row.get("observed_at"),
        row.get("scan_as_of"),
        row.get("as_of"),
        feed.get("as_of"),
    ):
        text = _text(raw)
        if text:
            return text
    return None


def _engine(row: dict[str, Any]) -> str:
    return (
        _text(row.get("strategy")) or _text(row.get("strategy_id")) or "signal_center"
    )


def _evidence(
    *,
    label: str,
    source: str,
    value: Any,
    timestamp: str | None,
    engine: str,
    result: str,
) -> dict[str, Any] | None:
    text = _text(value)
    if text is None and not isinstance(value, (list, dict)):
        return None
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in list(value.items())[:8]:
            shown = _text(item)
            if shown is not None:
                parts.append(f"{key}={shown}")
        text = ", ".join(parts) if parts else None
    if text is None:
        return None
    return {
        "label": label,
        "source": source,
        "value": text,
        "timestamp": timestamp,
        "engine": engine,
        "result": result,
    }


def _predicate_line(item: dict[str, Any]) -> str:
    name = _text(item.get("name")) or "predicate"
    bits = [name]
    actual = _text(item.get("actual"))
    required = _text(item.get("required"))
    if actual is not None:
        bits.append(f"actual {actual}")
    if required is not None:
        bits.append(f"required {required}")
    source = _text(item.get("source"))
    if source is not None:
        bits.append(f"source {source}")
    return " · ".join(bits)


def _gate_result(state: str | None) -> str:
    if state is None:
        return "not_available"
    label = state.upper()
    if label in {"BLOCK", "FAIL", "FAILED", "REJECT", "REJECTED"}:
        return "failed"
    if label in {"NOT_REACHED", "NOT_RUN"}:
        return "not_performed"
    if label in {"READY", "PASS", "PASSED"}:
        return "recorded_ready"
    return "recorded"


def project_decision_report(
    row: dict[str, Any] | None,
    *,
    feed: dict[str, Any] | None = None,
    source: str = "signal_center",
) -> dict[str, Any]:
    """Map one existing record. Never fills gaps with calculated substitutes."""
    feed = feed or {}
    if not isinstance(row, dict) or not row:
        return _empty_report(
            symbol=_text(feed.get("symbol")) or _NOT_AVAILABLE,
            source=source,
            reason=_AWAITING,
        )

    pipe = _dict(row.get("pipeline"))
    detail = _dict(row.get("detail"))
    decision = _decision_label(row)
    engine = _engine(row)
    timestamp = _timestamp(row, feed)
    symbol = _text(row.get("symbol")) or _NOT_AVAILABLE
    status = _text(row.get("status")) or decision
    synthetic = bool(
        row.get("test_synthetic")
        or feed.get("test_synthetic")
        or feed.get("fabricated")
    )
    data_state = _text(pipe.get("data"))
    age = pipe.get("data_age_seconds")
    stale = data_state == "STALE" or (
        isinstance(age, (int, float)) and not isinstance(age, bool) and float(age) > 120
    )
    lifecycle = str(pipe.get("execution_lifecycle") or "").upper()
    ticket = _text(pipe.get("ticket"))
    order_sent = lifecycle in {"ORDER_SENT", "FILLED"} or ticket is not None
    order_executed = lifecycle == "FILLED"

    evidence: list[dict[str, Any]] = []

    def add(label: str, src: str, value: Any, result: str | None = None) -> None:
        item = _evidence(
            label=label,
            source=src,
            value=value,
            timestamp=timestamp,
            engine=engine,
            result=result or decision,
        )
        if item is not None:
            evidence.append(item)

    add(
        "Decision",
        f"{source}.decision",
        decision if decision != _NOT_AVAILABLE else None,
    )
    add("Direction", f"{source}.direction", row.get("direction"))
    add("Status", f"{source}.status", row.get("status"))
    add("Strategy", f"{source}.strategy", row.get("strategy") or row.get("strategy_id"))
    add(
        "Recorded reason",
        f"{source}.reasoning",
        row.get("reasoning") or row.get("ai_explanation"),
    )
    add("Session", f"{source}.session", row.get("session"))
    add("Price", f"{source}.current_price", row.get("current_price"))
    add(
        "Trend",
        f"{source}.trend",
        None if row.get("trend") == "—" else row.get("trend"),
    )
    add("Structure", f"{source}.structure", row.get("structure"))
    add(
        "ATR",
        f"{source}.atr",
        row.get("atr") if _present(row.get("atr")) else pipe.get("atr"),
    )
    add(
        "Spread",
        f"{source}.spread",
        row.get("spread") if _present(row.get("spread")) else pipe.get("spread"),
    )
    add(
        "Market regime",
        f"{source}.pipeline.market_regime",
        pipe.get("market_regime") or pipe.get("volatility_regime"),
    )
    add(
        "Timeframe",
        f"{source}.pipeline.timeframe",
        pipe.get("zone_timeframe")
        or pipe.get("structure_timeframe")
        or pipe.get("atr_timeframe")
        or pipe.get("entry_timeframe"),
    )
    add("Market data state", f"{source}.pipeline.data", pipe.get("data"))
    add(
        "Tick time",
        f"{source}.pipeline.tick_time",
        pipe.get("tick_time") or detail.get("tick_time"),
    )
    add("Quote age seconds", f"{source}.pipeline.data_age_seconds", age)
    add("Setup state", f"{source}.pipeline.setup_state", pipe.get("setup_state"))
    add("Sniper", f"{source}.pipeline.sniper", pipe.get("sniper"))
    add(
        "Opportunity gate",
        f"{source}.pipeline.opportunity_gate",
        pipe.get("opportunity_gate"),
    )
    add("Risk gate", f"{source}.pipeline.risk", pipe.get("risk"))
    add("Safety gate", f"{source}.pipeline.safety", pipe.get("safety"))
    add("OMS gate", f"{source}.pipeline.oms", pipe.get("oms"))
    add(
        "Block code",
        f"{source}.block_code",
        row.get("block_code") or pipe.get("first_blocker"),
    )
    add("Waiting reason", f"{source}.waiting_reason", row.get("waiting_reason"))
    add(
        "Eligibility",
        f"{source}.pipeline.eligibility_status",
        pipe.get("eligibility_status"),
    )
    add(
        "Eligibility reason",
        f"{source}.pipeline.eligibility_reason",
        pipe.get("eligibility_reason"),
    )
    add(
        "Execution lifecycle",
        f"{source}.pipeline.execution_lifecycle",
        pipe.get("execution_lifecycle"),
    )
    add("Order ticket", f"{source}.pipeline.ticket", pipe.get("ticket"))
    add(
        "Recorded risk field",
        f"{source}.risk",
        row.get("risk") if _present(row.get("risk")) else detail.get("risk"),
    )
    add(
        "Live trading state",
        "signal_center.live_trading_state",
        feed.get("live_trading_state"),
    )
    add(
        "Live authorization",
        "signal_center.live_authorization",
        feed.get("live_authorization"),
    )
    add(
        "Orders may submit",
        "signal_center.orders_may_submit",
        feed.get("orders_may_submit"),
    )

    passed = [
        _predicate_line(p)
        for p in _items(pipe.get("passed_predicates"))
        if isinstance(p, dict)
    ]
    failed = [
        _predicate_line(p)
        for p in _items(pipe.get("failed_predicates"))
        if isinstance(p, dict)
    ]
    if _text(pipe.get("opportunity_gate")) == "PASS":
        passed.append("Opportunity gate PASS")
    elif _text(pipe.get("opportunity_gate")) == "WAIT":
        failed.append("Opportunity gate WAIT")

    reason = (
        _text(row.get("reasoning"))
        or _text(row.get("ai_explanation"))
        or _text(row.get("reason"))
    )
    blocking = (
        _text(row.get("blocking_gate"))
        or _text(row.get("block_code"))
        or _text(pipe.get("first_blocker"))
    )
    if reason is None and blocking is not None:
        reason = blocking

    invalidation: list[dict[str, Any]] = []
    invalidation_level = _text(pipe.get("original_invalidation"))
    if invalidation_level is not None:
        invalidation.append(
            {
                "label": "Recorded invalidation level",
                "value": invalidation_level,
                "source": f"{source}.pipeline.original_invalidation",
                "timestamp": timestamp,
                "engine": engine,
            }
        )
    for bucket in (
        _items(pipe.get("passed_predicates")),
        _items(pipe.get("failed_predicates")),
    ):
        for pred in bucket:
            if not isinstance(pred, dict):
                continue
            name = str(pred.get("name") or "")
            if "invalid" not in name.lower():
                continue
            line = _predicate_line(pred)
            invalidation.append(
                {
                    "label": name or "Invalidation predicate",
                    "value": line,
                    "source": f"{source}.pipeline.predicates",
                    "timestamp": timestamp,
                    "engine": engine,
                }
            )

    risk_checks: list[dict[str, Any]] = []
    for label, key in (
        ("Risk gate", "risk"),
        ("Safety gate", "safety"),
        ("Optimizer gate", "optimizer"),
        ("OMS gate", "oms"),
    ):
        state = _text(pipe.get(key))
        if state is None:
            continue
        risk_checks.append(
            {
                "name": label,
                "state": state,
                "result": _gate_result(state),
                "source": f"{source}.pipeline.{key}",
            }
        )
    if blocking is not None:
        risk_checks.append(
            {
                "name": "Block code",
                "state": blocking,
                "result": "failed"
                if _text(row.get("reject")) == "true" or row.get("reject") is True
                else "recorded",
                "source": f"{source}.block_code",
            }
        )

    missing_risk: list[str] = []
    if not any(item["name"] == "Risk gate" for item in risk_checks):
        missing_risk.append("No risk-gate result was attached to this decision record.")
    elif any(
        item["name"] == "Risk gate" and item["result"] == "not_performed"
        for item in risk_checks
    ):
        missing_risk.append(
            "The risk gate was not reached, so there is no risk approval result."
        )
    if not _present(row.get("risk")) and not _present(detail.get("risk")):
        missing_risk.append(
            "No risk limit or risk field was attached to this decision record."
        )
    if not _present(row.get("waiting_reason")) and not blocking:
        missing_risk.append("No rejection or withhold reason was recorded.")

    recorded_limit = _text(row.get("risk")) or _text(detail.get("risk"))
    market_facts = [
        item
        for item in evidence
        if item["label"]
        in {
            "Trend",
            "Structure",
            "ATR",
            "Spread",
            "Market regime",
            "Timeframe",
            "Market data state",
            "Tick time",
            "Quote age seconds",
            "Session",
            "Price",
        }
    ]
    strategy_available = bool(
        passed
        or failed
        or reason
        or _text(row.get("strategy") or row.get("strategy_id"))
    )

    return {
        "available": True,
        "empty_reason": None,
        "read_only": True,
        "executes_orders": False,
        "invents_reasoning": False,
        "calculates_risk": False,
        "decision_is_not_an_order": True,
        "order_note": _ORDER_NOTE,
        "history_note": _HISTORY_NOTE if source == "signal_history" else None,
        "source": source,
        "test_synthetic": synthetic,
        "stale": stale,
        "summary": {
            "symbol": symbol,
            "strategy": _text(row.get("strategy"))
            or _text(row.get("strategy_id"))
            or _NOT_AVAILABLE,
            "decision": decision,
            "status": status,
            "timestamp": timestamp or _NOT_AVAILABLE,
            "source_engine": engine,
            "signal_id": _text(row.get("signal_id")),
        },
        "market": {
            "available": bool(market_facts),
            "empty_reason": None if market_facts else _NOT_AVAILABLE,
            "data_state": data_state or _NOT_AVAILABLE,
            "stale": stale,
            "timestamp": _text(pipe.get("tick_time"))
            or _text(detail.get("tick_time"))
            or timestamp
            or _NOT_AVAILABLE,
            "timeframe": (
                _text(pipe.get("zone_timeframe"))
                or _text(pipe.get("structure_timeframe"))
                or _text(pipe.get("atr_timeframe"))
                or _text(pipe.get("entry_timeframe"))
                or _NOT_AVAILABLE
            ),
            "trend": (
                _text(None if row.get("trend") == "—" else row.get("trend"))
                or _NOT_AVAILABLE
            ),
            "volatility": (
                _text(pipe.get("volatility_regime"))
                or _text(pipe.get("market_regime"))
                or _NOT_AVAILABLE
            ),
            "structure": _text(row.get("structure")) or _NOT_AVAILABLE,
            "atr": _text(row.get("atr")) or _text(pipe.get("atr")) or _NOT_AVAILABLE,
            "spread": _text(row.get("spread"))
            or _text(pipe.get("spread"))
            or _NOT_AVAILABLE,
            "session": _text(row.get("session")) or _NOT_AVAILABLE,
            "price": _text(row.get("current_price")) or _NOT_AVAILABLE,
        },
        "strategy": {
            "available": strategy_available,
            "empty_reason": None if strategy_available else _AWAITING,
            "strategy": _text(row.get("strategy"))
            or _text(row.get("strategy_id"))
            or _NOT_AVAILABLE,
            "engine": engine,
            "satisfied": passed,
            "unsatisfied": failed,
            "reason": reason or _NOT_AVAILABLE,
        },
        "risk": {
            "available": bool(risk_checks or recorded_limit or missing_risk),
            "note": _RISK_NOTE,
            "checks": risk_checks,
            "recorded_limit": recorded_limit,
            "missing": missing_risk,
        },
        "evidence": evidence,
        "invalidation": {
            "available": bool(invalidation),
            "empty_reason": None if invalidation else _NOT_AVAILABLE,
            "conditions": invalidation,
        },
        "authorization": {
            "research_decision": decision,
            "strategy_evaluation": _text(pipe.get("setup_state"))
            or _text(pipe.get("sniper"))
            or _NOT_AVAILABLE,
            "risk_approval": _text(pipe.get("risk")) or _NOT_AVAILABLE,
            "execution_authorization": _text(feed.get("live_authorization"))
            or _text(pipe.get("oms"))
            or _NOT_AVAILABLE,
            "orders_may_submit": feed.get("orders_may_submit")
            if "orders_may_submit" in feed
            else None,
            "live_trading_state": _text(feed.get("live_trading_state"))
            or _NOT_AVAILABLE,
            "order_sent": order_sent,
            "order_executed": order_executed,
            "execution_lifecycle": lifecycle or _NOT_AVAILABLE,
            "ticket": ticket,
            "note": _ORDER_NOTE,
        },
    }


def _empty_report(*, symbol: str, source: str, reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "empty_reason": reason,
        "read_only": True,
        "executes_orders": False,
        "invents_reasoning": False,
        "calculates_risk": False,
        "decision_is_not_an_order": True,
        "order_note": _ORDER_NOTE,
        "history_note": _HISTORY_NOTE if source == "signal_history" else None,
        "source": source,
        "test_synthetic": False,
        "stale": False,
        "summary": {
            "symbol": symbol,
            "strategy": _NOT_AVAILABLE,
            "decision": _NOT_AVAILABLE,
            "status": _NOT_AVAILABLE,
            "timestamp": _NOT_AVAILABLE,
            "source_engine": _NOT_AVAILABLE,
            "signal_id": None,
        },
        "market": {"available": False, "empty_reason": reason},
        "strategy": {
            "available": False,
            "empty_reason": reason,
            "strategy": _NOT_AVAILABLE,
            "engine": _NOT_AVAILABLE,
            "satisfied": [],
            "unsatisfied": [],
            "reason": reason,
        },
        "risk": {
            "available": False,
            "note": _RISK_NOTE,
            "checks": [],
            "recorded_limit": None,
            "missing": [
                "No risk record is available until the engine publishes a decision."
            ],
        },
        "evidence": [],
        "invalidation": {"available": False, "empty_reason": reason, "conditions": []},
        "authorization": {
            "research_decision": _NOT_AVAILABLE,
            "strategy_evaluation": _NOT_AVAILABLE,
            "risk_approval": _NOT_AVAILABLE,
            "execution_authorization": _NOT_AVAILABLE,
            "orders_may_submit": None,
            "live_trading_state": _NOT_AVAILABLE,
            "order_sent": False,
            "order_executed": False,
            "execution_lifecycle": _NOT_AVAILABLE,
            "ticket": None,
            "note": _ORDER_NOTE,
        },
    }


def _select_row(items: list[Any], symbol: str | None) -> dict[str, Any] | None:
    rows = [item for item in items if isinstance(item, dict) and item.get("symbol")]
    if not rows:
        return None
    wanted = (symbol or "").strip().upper()
    if wanted:
        for row in rows:
            if str(row.get("symbol") or "").upper() == wanted:
                return row
        for row in rows:
            if wanted in str(row.get("symbol") or "").upper():
                return row
        return None
    try:
        from app.domain.trading.gold_only import is_gold_symbol

        for row in rows:
            if is_gold_symbol(str(row.get("symbol") or "")):
                return row
    except Exception:
        logger.exception("decision_evidence_gold_match_failed")
    return rows[0]


def build_live_report(symbol: str | None = None) -> dict[str, Any]:
    """Read the current Signal Center feed. Does not refresh or observe history."""
    from app.application.services.signal_center_service import list_live_signals

    payload = list_live_signals(
        q=(symbol or "").strip(),
        enabled_only=False,
        active_only=False,
    )
    feed = payload if isinstance(payload, dict) else {}
    if symbol:
        feed = {**feed, "symbol": symbol.strip().upper()}
    row = _select_row(list(feed.get("items") or []), symbol)
    report = project_decision_report(
        row, feed=feed, source=str(feed.get("source") or "signal_center")
    )
    report["feed_as_of"] = _text(feed.get("as_of"))
    report["scanner_status"] = _text(feed.get("scanner_status"))
    return report


def build_decision_history(
    *,
    symbol: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Read existing signal history. Never calls observe (that writes a snapshot)."""
    from app.application.services.signal_intelligence_service import list_signal_history

    cap = max(1, min(int(limit), 50))
    try:
        payload = list_signal_history(
            symbol=symbol,
            direction=None,
            limit=cap,
            observe=False,
        )
    except Exception:
        logger.exception("decision_evidence_history_unavailable")
        return {
            "available": False,
            "empty_reason": _NOT_AVAILABLE,
        "read_only": True,
        "executes_orders": False,
        "source": "signal_history",
        "history_note": _HISTORY_NOTE,
        "count": 0,
        "items": [],
    }
    rows = payload.get("items") if isinstance(payload, dict) else None
    items: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        report = project_decision_report(
            row, feed={"symbol": symbol}, source="signal_history"
        )
        summary = report["summary"]
        items.append(
            {
                "symbol": summary["symbol"],
                "decision": summary["decision"],
                "timestamp": summary["timestamp"],
                "strategy": summary["strategy"],
                "source": "signal_history",
                "report": report,
            }
        )
    return {
        "available": bool(items),
        "empty_reason": None if items else _AWAITING,
        "read_only": True,
        "executes_orders": False,
        "source": "signal_history",
        "history_note": _HISTORY_NOTE,
        "count": len(items),
        "items": items,
    }
