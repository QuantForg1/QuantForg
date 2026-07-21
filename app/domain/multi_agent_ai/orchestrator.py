"""Multi-Agent AI orchestrator — collaborate before trade approval."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.multi_agent_ai.agents import AGENT_RUNNERS
from app.domain.multi_agent_ai.config import (
    DEFAULT_MULTI_AGENT_CONFIG,
    MultiAgentConfig,
)
from app.domain.multi_agent_ai.coordinator import coordinate
from app.domain.multi_agent_ai.events import AgentEventBus
from app.domain.multi_agent_ai.governance import evaluate_governance
from app.domain.multi_agent_ai.memory import AIMemory
from app.domain.multi_agent_ai.types import CollaborationInput
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class MultiAgentSystem:
    config: MultiAgentConfig = field(
        default_factory=lambda: DEFAULT_MULTI_AGENT_CONFIG
    )
    bus: AgentEventBus = field(default_factory=AgentEventBus)
    memory: AIMemory = field(default_factory=AIMemory)
    sessions: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.bus.max_events = self.config.max_events
        self.memory.max_memory = self.config.max_memory

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "agents": [name for name, _ in AGENT_RUNNERS],
            "memory": self.memory.status(),
            "capabilities": {
                "xauusd_only": True,
                "agents_communicate_via_events": True,
                "explainable_outputs": True,
                "auditable_decisions": True,
                "coordinator_may_reject": True,
                "never_bypass_risk": True,
                "never_bypass_safety": True,
                "risk_safety_authoritative": True,
                "execution_pipeline_unchanged": True,
                "never_order_send": True,
                "memory_never_rewrites_rules": True,
                "confidence_voting": True,
                "ai_governance": True,
                "symbol": GOLD_SYMBOL,
            },
            "recent_sessions": self.sessions[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        self.bus.max_events = self.config.max_events
        self.memory.max_memory = self.config.max_memory
        return self.config.to_dict()

    def list_events(
        self, *, limit: int = 100, session_id: str | None = None
    ) -> dict[str, Any]:
        rows = [
            e.to_dict()
            for e in self.bus.list(limit=limit, session_id=session_id)
        ]
        return {"status": "available" if rows else "empty", "events": rows}

    def list_memory(
        self, *, limit: int = 50, kind: str | None = None
    ) -> dict[str, Any]:
        rows = self.memory.list(limit=limit, kind=kind)
        return {
            "status": "available" if rows else "empty",
            "records": rows,
            "allow_memory_rewrite_rules": False,
            **self.memory.status(),
        }

    def store_memory(
        self,
        *,
        kind: str,
        agent: str,
        content: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        result = self.memory.store(
            kind=kind, agent=agent, content=content, session_id=session_id
        )
        if isinstance(result, dict):
            return result
        return result.to_dict()

    def governance_status(self) -> dict[str, Any]:
        # Empty governance snapshot for operators.
        gov = evaluate_governance(
            config=self.config,
            outputs=[],
            decision="HOLD",
            allow_execution_path=False,
            risk_engine_passed=None,
            safety_engine_passed=None,
        )
        return {
            **gov.to_dict(),
            "detail": "Operator governance view — hard locks enforced",
            "checklist": [
                {**item, "done": False} for item in gov.to_dict()["checklist"]
            ],
        }

    def collaborate(self, inp: CollaborationInput) -> dict[str, Any]:
        session_id = f"ma_{uuid4().hex[:12]}"
        self.bus.publish(
            event_type="session.started",
            agent="coordinator",
            payload={"side": inp.side, "symbol": GOLD_SYMBOL},
            session_id=session_id,
        )

        outputs = []
        for _name, runner in AGENT_RUNNERS:
            outputs.append(runner(inp, session_id=session_id, bus=self.bus))

        decision = coordinate(
            inp=inp,
            outputs=outputs,
            config=self.config,
            session_id=session_id,
            bus=self.bus,
        )

        gov = evaluate_governance(
            config=self.config,
            outputs=outputs,
            decision=decision.decision,
            allow_execution_path=decision.allow_execution_path,
            risk_engine_passed=inp.risk_engine_passed,
            safety_engine_passed=inp.safety_engine_passed,
        )

        # Memory: observations + session report only — never rules.
        for out in outputs:
            self.memory.store(
                kind="observation",
                agent=out.agent,
                content={
                    "vote": out.vote,
                    "confidence": str(out.confidence),
                    "reasons": list(out.reasons),
                },
                session_id=session_id,
            )
        self.memory.store(
            kind="report",
            agent="coordinator",
            content={
                "decision": decision.decision,
                "reasons": list(decision.reasons),
            },
            session_id=session_id,
        )
        self.memory.store(
            kind="session",
            agent="system",
            content={"session_id": session_id, "agents": len(outputs)},
            session_id=session_id,
        )

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "session_id": session_id,
            "side": inp.side,
            "agents": [o.to_dict() for o in outputs],
            "decision": decision.decision,
            "allow_execution_path": decision.allow_execution_path,
            "advisory_only": True,
            "never_order_send": True,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "execution_pipeline_unchanged": True,
            "risk_engine_authoritative": True,
            "safety_engine_authoritative": True,
            "coordinator": decision.to_dict(),
            "voting": decision.vote_tally.to_dict(),
            "governance": gov.to_dict(),
            "events": [e.to_dict() for e in self.bus.by_session(session_id)],
            "memory_note": "Observations and reports stored; rules not rewritten",
            "inputs": _input_to_dict(inp),
        }
        self.sessions.insert(0, {
            "session_id": session_id,
            "decision": decision.decision,
            "allow_execution_path": decision.allow_execution_path,
            "agent_count": len(outputs),
        })
        if len(self.sessions) > self.config.max_sessions:
            self.sessions = self.sessions[: self.config.max_sessions]
        return result


def _input_to_dict(inp: CollaborationInput) -> dict[str, Any]:
    return {
        "side": inp.side,
        "spread": str(inp.spread) if inp.spread is not None else None,
        "confidence": str(inp.confidence) if inp.confidence is not None else None,
        "regime": inp.regime,
        "strategy_id": inp.strategy_id,
        "strategy_signal": inp.strategy_signal,
        "portfolio_exposure": (
            str(inp.portfolio_exposure)
            if inp.portfolio_exposure is not None
            else None
        ),
        "open_positions": inp.open_positions,
        "execution_mode": inp.execution_mode,
        "news_blackout": inp.news_blackout,
        "kill_switch": inp.kill_switch,
        "risk_engine_passed": inp.risk_engine_passed,
        "safety_engine_passed": inp.safety_engine_passed,
        "market_snapshot": inp.market_snapshot,
        "strategy_snapshot": inp.strategy_snapshot,
        "portfolio_snapshot": inp.portfolio_snapshot,
        "execution_snapshot": inp.execution_snapshot,
    }


def input_from_dict(data: dict[str, Any]) -> CollaborationInput:
    def _dec(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    def _opt_bool(v: Any) -> bool | None:
        if isinstance(v, bool):
            return v
        return None

    def _opt_int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    return CollaborationInput(
        side=str(data.get("side") or "buy"),
        spread=_dec(data.get("spread")),
        confidence=_dec(data.get("confidence")),
        regime=str(data["regime"]) if data.get("regime") else None,
        strategy_id=str(data["strategy_id"]) if data.get("strategy_id") else None,
        strategy_signal=(
            str(data["strategy_signal"]) if data.get("strategy_signal") else None
        ),
        portfolio_exposure=_dec(data.get("portfolio_exposure")),
        open_positions=_opt_int(data.get("open_positions")),
        execution_mode=(
            str(data["execution_mode"]) if data.get("execution_mode") else None
        ),
        news_blackout=_opt_bool(data.get("news_blackout")),
        kill_switch=_opt_bool(data.get("kill_switch")),
        risk_engine_passed=_opt_bool(data.get("risk_engine_passed")),
        safety_engine_passed=_opt_bool(data.get("safety_engine_passed")),
        market_snapshot=(
            data.get("market_snapshot")
            if isinstance(data.get("market_snapshot"), dict)
            else None
        ),
        strategy_snapshot=(
            data.get("strategy_snapshot")
            if isinstance(data.get("strategy_snapshot"), dict)
            else None
        ),
        portfolio_snapshot=(
            data.get("portfolio_snapshot")
            if isinstance(data.get("portfolio_snapshot"), dict)
            else None
        ),
        execution_snapshot=(
            data.get("execution_snapshot")
            if isinstance(data.get("execution_snapshot"), dict)
            else None
        ),
    )
