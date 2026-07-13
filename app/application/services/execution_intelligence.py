"""Execution Intelligence service — lifecycle + analytics (never order_send)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums.execution import ExecutionOutcome
from app.domain.execution_intelligence import (
    LifecycleState,
    LifecycleStore,
    analyze_post_trades,
    build_broker_diagnostics,
    compute_execution_analytics,
    evaluate_checklist,
)


def _map_outcome_to_state(outcome: str) -> LifecycleState | None:
    o = outcome.strip().lower()
    mapping = {
        "success": LifecycleState.FILLED,
        "failed": LifecycleState.REJECTED,
        "disabled": LifecycleState.REJECTED,
        "retry": LifecycleState.SUBMITTED,
        "cancelled": LifecycleState.CANCELLED,
        "prepared": LifecycleState.VALIDATED,
        "allow": LifecycleState.VALIDATED,
        "reject": LifecycleState.REJECTED,
        "filled": LifecycleState.FILLED,
        "partially_filled": LifecycleState.PARTIALLY_FILLED,
        "accepted": LifecycleState.ACCEPTED,
    }
    return mapping.get(o)


@dataclass
class ExecutionIntelligenceService:
    """Trade lifecycle manager + execution analytics over real records."""

    store: LifecycleStore = field(default_factory=LifecycleStore)

    def observe(
        self,
        *,
        user_id: str,
        request_id: str,
        symbol: str,
        side: str,
        order_type: str,
        volume: str,
        state: str,
        reason: str,
        source: str = "observe",
        meta: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        try:
            target = LifecycleState(state)
        except ValueError:
            # also accept enum names
            try:
                target = LifecycleState[state.upper().replace(" ", "_")]
            except KeyError:
                return {
                    "ok": False,
                    "error": f"Unknown lifecycle state '{state}'",
                }

        existing = self.store.get(user_id, request_id)
        if existing is None:
            initial = (
                target
                if target == LifecycleState.DRAFT
                else LifecycleState.DRAFT
            )
            self.store.create(
                user_id=user_id,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                initial=initial,
                reason="lifecycle created",
                source=source,
            )
            if target != LifecycleState.DRAFT:
                return self.store.transition(
                    user_id=user_id,
                    request_id=request_id,
                    to_state=target,
                    reason=reason,
                    source=source,
                    meta=meta,
                    force=force or True,
                )
            return {"ok": True, "record": self.store.get(user_id, request_id)}

        return self.store.transition(
            user_id=user_id,
            request_id=request_id,
            to_state=target,
            reason=reason,
            source=source,
            meta=meta,
            force=force,
        )

    def ingest_attempts(
        self, *, user_id: str, attempts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Map persisted execution attempts into lifecycle archive."""
        out: list[dict[str, Any]] = []
        for a in attempts:
            request_id = str(a.get("request_id") or "").strip()
            if not request_id:
                continue
            outcome = str(a.get("outcome") or "")
            mapped = _map_outcome_to_state(outcome)
            self.observe(
                user_id=user_id,
                request_id=request_id,
                symbol=str(a.get("symbol") or "UNK"),
                side=str(a.get("side") or "unknown"),
                order_type=str(a.get("order_type") or "unknown"),
                volume=str(a.get("volume") or "0"),
                state=LifecycleState.SUBMITTED.value,
                reason="attempt recorded",
                source="execution_attempt",
                meta={"outcome": outcome, "retcode": a.get("retcode")},
                force=True,
            )
            if mapped is not None:
                result = self.observe(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=str(a.get("symbol") or "UNK"),
                    side=str(a.get("side") or "unknown"),
                    order_type=str(a.get("order_type") or "unknown"),
                    volume=str(a.get("volume") or "0"),
                    state=mapped.value,
                    reason=str(a.get("message") or outcome),
                    source="execution_attempt",
                    meta={"outcome": outcome, "retcode": a.get("retcode")},
                    force=True,
                )
                out.append(result)
        return out

    def ingest_decisions(
        self, *, user_id: str, decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for d in decisions:
            request_id = str(d.get("request_id") or "").strip()
            if not request_id:
                continue
            decision = str(d.get("decision") or "").lower()
            if decision == "allow":
                # If risk checks present and passed → Risk Approved else Validated
                checks = d.get("checks") or {}
                risk_ok = True
                if isinstance(checks, dict) and checks:
                    risk_ok = all(bool(v) for v in checks.values())
                state = (
                    LifecycleState.RISK_APPROVED
                    if risk_ok
                    else LifecycleState.VALIDATED
                )
            elif decision in {"reject", "rejected"}:
                state = LifecycleState.REJECTED
            else:
                state = LifecycleState.VALIDATED
            out.append(
                self.observe(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=str(d.get("symbol") or "UNK"),
                    side=str(d.get("side") or "unknown"),
                    order_type=str(d.get("order_type") or "unknown"),
                    volume=str(d.get("volume") or "0"),
                    state=state.value,
                    reason=str(d.get("decision") or "safety decision"),
                    source="execution_decision",
                    meta={"decision": decision},
                    force=True,
                )
            )
        return out

    def checklist(
        self,
        *,
        broker_connected: bool | None,
        market_open: bool | None,
        risk_passed: bool | None,
        margin_sufficient: bool | None,
        strategy_signal_valid: bool | None,
        execution_enabled: bool,
    ) -> dict[str, Any]:
        return evaluate_checklist(
            broker_connected=broker_connected,
            market_open=market_open,
            risk_passed=risk_passed,
            margin_sufficient=margin_sufficient,
            strategy_signal_valid=strategy_signal_valid,
            execution_enabled=execution_enabled,
        )

    def analytics(
        self, *, attempts: list[dict[str, Any]], fills: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return compute_execution_analytics(attempts=attempts, fills=fills)

    def post_trade(self, *, trades: list[dict[str, Any]]) -> dict[str, Any]:
        return analyze_post_trades(trades)

    def broker_diagnostics(self, **kwargs: Any) -> dict[str, Any]:
        return build_broker_diagnostics(**kwargs)

    def dashboard(
        self,
        *,
        user_id: str,
        attempts: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        fills: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        checklist_facts: dict[str, Any],
        broker_facts: dict[str, Any],
        execution_enabled: bool,
        recent_risk: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.ingest_decisions(user_id=user_id, decisions=decisions)
        self.ingest_attempts(user_id=user_id, attempts=attempts)
        lifecycle = self.store.list_for_user(user_id, limit=100)
        return {
            "execution_enabled": execution_enabled,
            "execution_enabled_note": (
                "Flag read-only — Execution Intelligence never changes it"
            ),
            "lifecycle": {
                "items": lifecycle,
                "count": len(lifecycle),
                "active": len([x for x in lifecycle if not x.get("archived")]),
                "archived": len([x for x in lifecycle if x.get("archived")]),
            },
            "timeline": lifecycle[:20],
            "analytics": self.analytics(attempts=attempts, fills=fills),
            "recent_orders": attempts[:20],
            "checklist": self.checklist(
                broker_connected=checklist_facts.get("broker_connected"),
                market_open=checklist_facts.get("market_open"),
                risk_passed=checklist_facts.get("risk_passed"),
                margin_sufficient=checklist_facts.get("margin_sufficient"),
                strategy_signal_valid=checklist_facts.get("strategy_signal_valid"),
                execution_enabled=execution_enabled,
            ),
            "post_trade": self.post_trade(trades=trades),
            "broker": self.broker_diagnostics(**broker_facts),
            "risk_decisions": list(recent_risk or decisions)[:20],
            "autonomous_trading": False,
            "outcomes_reference": [o.value for o in ExecutionOutcome],
        }
