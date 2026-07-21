"""Trading Kernel V1 orchestrator — composes stages, never bypasses Risk/Safety."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading_kernel.certification import build_certification_workflow
from app.domain.trading_kernel.config import DEFAULT_KERNEL_CONFIG, KernelConfig
from app.domain.trading_kernel.decision_graph import DecisionGraph
from app.domain.trading_kernel.event_bus import KernelEventBus
from app.domain.trading_kernel.plugins import PluginRegistry
from app.domain.trading_kernel.policy import (
    FeatureFlagFramework,
    PolicyEngine,
    RuleEngine,
)
from app.domain.trading_kernel.replay import (
    deterministic_replay,
    freeze_cycle_record,
    stage_replay,
)
from app.domain.trading_kernel.state_machine import KernelState, TradingStateMachine


@dataclass(frozen=True, slots=True)
class KernelCycleInput:
    """Supplied facts only — Risk/Safety outcomes from existing engines."""

    side: str = "buy"
    spread: Decimal | None = None
    confidence: Decimal | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    execution_mode: str | None = None
    alpha: dict[str, Any] | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    decision: str | None = None
    plugin_snapshot: dict[str, Any] | None = None
    certification: dict[str, Any] | None = None
    go_nogo: str | None = None


@dataclass
class TradingKernel:
    config: KernelConfig = field(default_factory=lambda: DEFAULT_KERNEL_CONFIG)
    bus: KernelEventBus = field(default_factory=KernelEventBus)
    machine: TradingStateMachine = field(default_factory=TradingStateMachine)
    plugins: PluginRegistry = field(default_factory=PluginRegistry)
    cycles: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.bus.max_events = self.config.max_events
        self.policy = PolicyEngine(self.config)
        self.flags = FeatureFlagFramework(self.config)
        self.rules = RuleEngine()

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "state": self.machine.to_dict(),
            "plugins": self.plugins.list(),
            "feature_flags": self.flags.snapshot(),
            "capabilities": {
                "orchestrates_only": True,
                "never_order_send": True,
                "never_bypass_risk": True,
                "never_bypass_safety": True,
                "auditable_events": True,
                "plugins_isolated": True,
                "deterministic_replay": self.config.deterministic_replay,
                "execution_pipeline_unchanged": True,
                "risk_engine_unchanged": True,
                "safety_engine_unchanged": True,
                "symbol": GOLD_SYMBOL,
            },
            "recent_cycles": self.cycles[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        self.bus.max_events = self.config.max_events
        self.policy = PolicyEngine(self.config)
        self.flags = FeatureFlagFramework(self.config)
        return self.config.to_dict()

    def list_events(
        self, *, limit: int = 100, trace_id: str | None = None
    ) -> dict[str, Any]:
        rows = [e.to_dict() for e in self.bus.list(limit=limit, trace_id=trace_id)]
        return {
            "status": "available" if rows else "empty",
            "events": rows,
        }

    def stage_replay(
        self, *, trace_id: str, stage: str | None = None
    ) -> dict[str, Any]:
        return stage_replay(self.bus, trace_id=trace_id, stage=stage).to_dict()

    def deterministic_replay_cycle(self, trace_id: str) -> dict[str, Any]:
        recorded = next((c for c in self.cycles if c.get("trace_id") == trace_id), None)
        if recorded is None:
            return {
                "status": "unavailable",
                "detail": "Unknown cycle — never invents replay",
            }
        # Re-run with identical frozen inputs and the same trace_id
        inp = _input_from_dict(recorded["inputs"])
        recomputed = self.run_cycle(
            inp, freeze=False, trace_id=str(recorded["trace_id"])
        )
        return deterministic_replay(
            recorded["inputs"],
            recorded["outputs"],
            recompute_outputs=recomputed["outputs"],
        ).to_dict()

    def certification(
        self,
        certification: dict[str, Any] | None = None,
        go_nogo: str | None = None,
    ) -> dict[str, Any]:
        return build_certification_workflow(
            certification, go_nogo=go_nogo
        ).to_dict()

    def run_cycle(
        self,
        inp: KernelCycleInput,
        *,
        freeze: bool = True,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Orchestrate one advisory cycle. Never calls order_send."""
        # Deterministic replay reuses the recorded trace_id so graph hashes match.
        cycle_trace = trace_id or f"tk_{uuid4().hex[:12]}"
        self.machine.reset()
        stage_rows: list[dict[str, Any]] = []

        def emit(event_type: str, stage: str, payload: dict[str, Any]) -> None:
            self.bus.publish(
                event_type=event_type,
                stage=stage,
                payload=payload,
                trace_id=cycle_trace,
            )

        self.machine.transition(KernelState.EVALUATING, reason="cycle_start")
        emit("cycle.started", "evaluating", {"side": inp.side, "symbol": GOLD_SYMBOL})
        stage_rows.append(
            {
                "stage": "evaluating",
                "ok": True,
                "detail": "Cycle started",
                "inputs": {"side": inp.side},
                "outputs": {"started": True},
            }
        )

        # Alpha stage (optional advisory payload)
        if self.flags.is_enabled("kernel_alpha_stage"):
            self.machine.transition(KernelState.ALPHA, reason="alpha")
            alpha_ok = inp.alpha is not None
            emit(
                "alpha.observed",
                "alpha",
                {"present": alpha_ok, "alpha": inp.alpha or {}},
            )
            stage_rows.append(
                {
                    "stage": "alpha",
                    "ok": True,
                    "detail": "Alpha advisory observed"
                    if alpha_ok
                    else "No alpha payload",
                    "inputs": {},
                    "outputs": {"alpha_present": alpha_ok},
                }
            )

        facts = {
            "spread": str(inp.spread) if inp.spread is not None else None,
            "confidence": str(inp.confidence) if inp.confidence is not None else None,
            "news_blackout": inp.news_blackout,
            "kill_switch": inp.kill_switch,
            "execution_mode": inp.execution_mode,
        }
        policy = self.policy.evaluate({k: v for k, v in facts.items() if v is not None})
        emit("policy.evaluated", "policy", policy.to_dict())
        stage_rows.append(
            {
                "stage": "policy",
                "ok": policy.allowed,
                "detail": "; ".join(policy.reasons),
                "inputs": facts,
                "outputs": policy.to_dict(),
            }
        )

        rules = self.rules.evaluate(
            {k: v for k, v in facts.items() if v is not None}, self.config
        )
        emit("rules.evaluated", "rules", rules.to_dict())
        stage_rows.append(
            {
                "stage": "rules",
                "ok": rules.passed,
                "detail": "; ".join(rules.reasons),
                "inputs": facts,
                "outputs": rules.to_dict(),
            }
        )

        plugin_outs: list[dict[str, Any]] = []
        if self.flags.is_enabled("kernel_plugins"):
            plugin_outs = self.plugins.run_all(inp.plugin_snapshot or facts)
            emit("plugins.ran", "plugins", {"results": plugin_outs})
            stage_rows.append(
                {
                    "stage": "plugins",
                    "ok": True,
                    "detail": f"{len(plugin_outs)} plugins (isolated)",
                    "inputs": inp.plugin_snapshot or {},
                    "outputs": {"results": plugin_outs},
                }
            )

        # Risk — supplied by existing Risk Engine only
        self.machine.transition(KernelState.RISK, reason="risk")
        risk_ok = inp.risk_engine_passed
        if risk_ok is None:
            emit(
                "risk.missing",
                "risk",
                {"risk_engine_passed": None, "fail_closed": True},
            )
            stage_rows.append(
                {
                    "stage": "risk",
                    "ok": False,
                    "detail": "Risk Engine not assessed — fail closed (unchanged)",
                    "inputs": {},
                    "outputs": {"risk_engine_passed": None},
                }
            )
            self.machine.transition(KernelState.HOLD, reason="risk_missing")
            return self._finalize(
                cycle_trace, inp, stage_rows, "HOLD", False, freeze=freeze
            )
        if risk_ok is False:
            emit("risk.failed", "risk", {"risk_engine_passed": False})
            stage_rows.append(
                {
                    "stage": "risk",
                    "ok": False,
                    "detail": "Risk Engine rejected — kernel does not bypass",
                    "inputs": {},
                    "outputs": {"risk_engine_passed": False},
                }
            )
            self.machine.transition(KernelState.HOLD, reason="risk_fail")
            return self._finalize(
                cycle_trace, inp, stage_rows, "HOLD", False, freeze=freeze
            )
        emit("risk.passed", "risk", {"risk_engine_passed": True})
        stage_rows.append(
            {
                "stage": "risk",
                "ok": True,
                "detail": "Risk Engine passed (external, unchanged)",
                "inputs": {},
                "outputs": {"risk_engine_passed": True},
            }
        )

        # Safety — supplied by existing Safety Engine only
        self.machine.transition(KernelState.SAFETY, reason="safety")
        safety_ok = inp.safety_engine_passed
        if safety_ok is None:
            emit(
                "safety.missing",
                "safety",
                {"safety_engine_passed": None, "fail_closed": True},
            )
            stage_rows.append(
                {
                    "stage": "safety",
                    "ok": False,
                    "detail": "Safety Engine not assessed — fail closed (unchanged)",
                    "inputs": {},
                    "outputs": {"safety_engine_passed": None},
                }
            )
            self.machine.transition(KernelState.HOLD, reason="safety_missing")
            return self._finalize(
                cycle_trace, inp, stage_rows, "HOLD", False, freeze=freeze
            )
        if safety_ok is False:
            emit("safety.failed", "safety", {"safety_engine_passed": False})
            stage_rows.append(
                {
                    "stage": "safety",
                    "ok": False,
                    "detail": "Safety Engine rejected — kernel does not bypass",
                    "inputs": {},
                    "outputs": {"safety_engine_passed": False},
                }
            )
            self.machine.transition(KernelState.HOLD, reason="safety_fail")
            return self._finalize(
                cycle_trace, inp, stage_rows, "HOLD", False, freeze=freeze
            )
        emit("safety.passed", "safety", {"safety_engine_passed": True})
        stage_rows.append(
            {
                "stage": "safety",
                "ok": True,
                "detail": "Safety Engine passed (external, unchanged)",
                "inputs": {},
                "outputs": {"safety_engine_passed": True},
            }
        )

        if not policy.allowed or not rules.passed:
            self.machine.transition(KernelState.DECISION, reason="policy_rules")
            self.machine.transition(KernelState.HOLD, reason="policy_or_rules")
            emit("decision.hold", "decision", {"reason": "policy_or_rules"})
            stage_rows.append(
                {
                    "stage": "decision",
                    "ok": False,
                    "detail": "HOLD due to policy/rules",
                    "inputs": {},
                    "outputs": {"decision": "HOLD"},
                }
            )
            return self._finalize(
                cycle_trace, inp, stage_rows, "HOLD", False, freeze=freeze
            )

        self.machine.transition(KernelState.DECISION, reason="decide")
        decision = (inp.decision or "HOLD").upper()
        if decision not in {"HOLD", "APPROVE", "REJECT"}:
            decision = "HOLD"
        allow = decision == "APPROVE"
        # APPROVE is advisory only — never triggers execution pipeline.
        target = {
            "HOLD": KernelState.HOLD,
            "APPROVE": KernelState.APPROVE,
            "REJECT": KernelState.REJECT,
        }[decision]
        self.machine.transition(target, reason="terminal")
        emit(
            "decision.made",
            "decision",
            {
                "decision": decision,
                "allow_execution_path": allow,
                "advisory_only": True,
                "never_order_send": True,
            },
        )
        stage_rows.append(
            {
                "stage": "decision",
                "ok": True,
                "detail": f"Terminal {decision} (advisory)",
                "inputs": {"decision": inp.decision},
                "outputs": {
                    "decision": decision,
                    "allow_execution_path": allow,
                },
            }
        )
        return self._finalize(
            cycle_trace, inp, stage_rows, decision, allow, freeze=freeze
        )

    def _finalize(
        self,
        trace_id: str,
        inp: KernelCycleInput,
        stage_rows: list[dict[str, Any]],
        decision: str,
        allow: bool,
        *,
        freeze: bool,
    ) -> dict[str, Any]:
        graph = DecisionGraph.build(stage_rows)
        cert = build_certification_workflow(inp.certification, go_nogo=inp.go_nogo)
        inputs = _input_to_dict(inp)
        outputs = {
            "decision": decision,
            "allow_execution_path": allow,
            "state": self.machine.state.value,
            "graph": graph.to_dict(),
        }
        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "trace_id": trace_id,
            "decision": decision,
            "allow_execution_path": allow,
            "advisory_only": True,
            "never_order_send": True,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "execution_pipeline_unchanged": True,
            "state": self.machine.to_dict(),
            "graph": graph.to_dict(),
            "events": [e.to_dict() for e in self.bus.by_trace(trace_id)],
            "certification": cert.to_dict(),
            "feature_flags": self.flags.snapshot(),
            "inputs": inputs,
            "outputs": outputs,
        }
        if freeze:
            record = freeze_cycle_record(
                trace_id=trace_id,
                inputs=inputs,
                outputs=outputs,
                events=self.bus.by_trace(trace_id),
            )
            self.cycles.insert(0, record)
            if len(self.cycles) > self.config.max_cycles:
                self.cycles = self.cycles[: self.config.max_cycles]
        self.machine.transition(KernelState.IDLE, reason="reset")
        return result


def _input_to_dict(inp: KernelCycleInput) -> dict[str, Any]:
    return {
        "side": inp.side,
        "spread": str(inp.spread) if inp.spread is not None else None,
        "confidence": str(inp.confidence) if inp.confidence is not None else None,
        "news_blackout": inp.news_blackout,
        "kill_switch": inp.kill_switch,
        "execution_mode": inp.execution_mode,
        "alpha": inp.alpha,
        "risk_engine_passed": inp.risk_engine_passed,
        "safety_engine_passed": inp.safety_engine_passed,
        "decision": inp.decision,
        "plugin_snapshot": inp.plugin_snapshot,
        "certification": inp.certification,
        "go_nogo": inp.go_nogo,
    }


def _input_from_dict(data: dict[str, Any]) -> KernelCycleInput:
    def _dec(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    return KernelCycleInput(
        side=str(data.get("side") or "buy"),
        spread=_dec(data.get("spread")),
        confidence=_dec(data.get("confidence")),
        news_blackout=data.get("news_blackout")
        if isinstance(data.get("news_blackout"), bool)
        else None,
        kill_switch=data.get("kill_switch")
        if isinstance(data.get("kill_switch"), bool)
        else None,
        execution_mode=str(data["execution_mode"])
        if data.get("execution_mode")
        else None,
        alpha=data.get("alpha") if isinstance(data.get("alpha"), dict) else None,
        risk_engine_passed=data.get("risk_engine_passed")
        if isinstance(data.get("risk_engine_passed"), bool)
        else None,
        safety_engine_passed=data.get("safety_engine_passed")
        if isinstance(data.get("safety_engine_passed"), bool)
        else None,
        decision=str(data["decision"]) if data.get("decision") else None,
        plugin_snapshot=data.get("plugin_snapshot")
        if isinstance(data.get("plugin_snapshot"), dict)
        else None,
        certification=data.get("certification")
        if isinstance(data.get("certification"), dict)
        else None,
        go_nogo=str(data["go_nogo"]) if data.get("go_nogo") else None,
    )
