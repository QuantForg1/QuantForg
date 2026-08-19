"""Decision waterfall — ordered institutional stages."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.domain.decision_intelligence.config import DecisionIntelligenceConfig

StageName = Literal[
    "signal",
    "strategy_consensus",
    "market_regime",
    "confidence",
    "veto_checks",
    "risk_engine",
    "safety_engine",
    "decision",
]

StageState = Literal["PASS", "FAIL", "NOT_ASSESSED"]


@dataclass(frozen=True, slots=True)
class WaterfallStage:
    name: StageName
    passed: bool
    required: bool
    reason: str
    state: StageState = "FAIL"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "reason": self.reason,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class WaterfallInput:
    signal_present: bool | None = None
    strategy_consensus_ok: bool | None = None
    market_regime_ok: bool | None = None
    confidence: Decimal | None = None
    veto_clear: bool = True
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    risk_engine_reason: str | None = None
    safety_engine_reason: str | None = None


def _stage(
    name: StageName,
    *,
    passed: bool,
    required: bool,
    reason: str,
    assessed: bool = True,
) -> WaterfallStage:
    if not assessed:
        state: StageState = "NOT_ASSESSED"
        passed = False
    elif passed:
        state = "PASS"
    else:
        state = "FAIL"
    return WaterfallStage(
        name=name,
        passed=passed,
        required=required,
        reason=reason,
        state=state,
    )


def evaluate_waterfall(
    config: DecisionIntelligenceConfig, inp: WaterfallInput
) -> tuple[WaterfallStage, ...]:
    stages: list[WaterfallStage] = []

    # Signal
    if inp.signal_present is None:
        stages.append(
            _stage(
                "signal",
                passed=not config.require_signal,
                required=config.require_signal,
                reason=(
                    "Signal not assessed — fail closed"
                    if config.require_signal
                    else "Signal optional/not supplied"
                ),
                assessed=not config.require_signal,
            )
        )
    else:
        stages.append(
            _stage(
                "signal",
                passed=bool(inp.signal_present),
                required=config.require_signal,
                reason="Signal present" if inp.signal_present else "No signal",
            )
        )

    # Strategy consensus
    if inp.strategy_consensus_ok is None:
        stages.append(
            _stage(
                "strategy_consensus",
                passed=not config.require_strategy_consensus,
                required=config.require_strategy_consensus,
                reason=(
                    "Consensus not assessed — fail closed"
                    if config.require_strategy_consensus
                    else "Consensus optional/not supplied"
                ),
                assessed=not config.require_strategy_consensus,
            )
        )
    else:
        stages.append(
            _stage(
                "strategy_consensus",
                passed=bool(inp.strategy_consensus_ok),
                required=config.require_strategy_consensus,
                reason=(
                    "Strategy consensus ok"
                    if inp.strategy_consensus_ok
                    else "Strategy consensus failed"
                ),
            )
        )

    # Market regime
    if inp.market_regime_ok is None:
        stages.append(
            _stage(
                "market_regime",
                passed=not config.require_market_regime_ok,
                required=config.require_market_regime_ok,
                reason=(
                    "Regime not assessed — fail closed"
                    if config.require_market_regime_ok
                    else "Regime optional/not supplied"
                ),
                assessed=not config.require_market_regime_ok,
            )
        )
    else:
        stages.append(
            _stage(
                "market_regime",
                passed=bool(inp.market_regime_ok),
                required=config.require_market_regime_ok,
                reason=(
                    "Market regime acceptable"
                    if inp.market_regime_ok
                    else "Market regime blocks entry"
                ),
            )
        )

    # Confidence
    conf_ok = inp.confidence is not None and inp.confidence >= config.min_confidence
    if inp.confidence is None:
        conf_reason = "Confidence unavailable — fail closed"
        conf_assessed = False
    elif conf_ok:
        conf_reason = f"Confidence {inp.confidence} >= {config.min_confidence}"
        conf_assessed = True
    else:
        conf_reason = f"Confidence {inp.confidence} below {config.min_confidence}"
        conf_assessed = True
    stages.append(
        _stage(
            "confidence",
            passed=conf_ok,
            required=True,
            reason=conf_reason,
            assessed=conf_assessed,
        )
    )

    # Veto checks
    stages.append(
        _stage(
            "veto_checks",
            passed=inp.veto_clear,
            required=True,
            reason=(
                "No veto conditions"
                if inp.veto_clear
                else "Veto system blocked trade"
            ),
        )
    )

    # Risk — always required, fail closed. None is NOT_ASSESSED, not FAIL.
    if inp.risk_engine_passed is None:
        stages.append(
            _stage(
                "risk_engine",
                passed=False,
                required=True,
                reason="Risk Engine not assessed — fail closed (never bypassed)",
                assessed=False,
            )
        )
    else:
        stages.append(
            _stage(
                "risk_engine",
                passed=bool(inp.risk_engine_passed),
                required=True,
                reason=(
                    inp.risk_engine_reason
                    or (
                        "Risk Engine ALLOW"
                        if inp.risk_engine_passed
                        else "Risk Engine did not ALLOW"
                    )
                ),
            )
        )

    # Safety — always required, fail closed. None is NOT_ASSESSED, not FAIL.
    if inp.safety_engine_passed is None:
        stages.append(
            _stage(
                "safety_engine",
                passed=False,
                required=True,
                reason="Safety Engine not assessed — fail closed (never bypassed)",
                assessed=False,
            )
        )
    else:
        stages.append(
            _stage(
                "safety_engine",
                passed=bool(inp.safety_engine_passed),
                required=True,
                reason=(
                    inp.safety_engine_reason
                    or (
                        "Safety Engine ALLOW"
                        if inp.safety_engine_passed
                        else "Safety Engine did not ALLOW"
                    )
                ),
            )
        )

    required_ok = all(s.passed for s in stages if s.required)
    stages.append(
        _stage(
            "decision",
            passed=required_ok,
            required=True,
            reason=(
                "Waterfall clear for advisory APPROVE (execution still gated)"
                if required_ok
                else "Waterfall blocked — REJECT/HOLD"
            ),
        )
    )
    return tuple(stages)
