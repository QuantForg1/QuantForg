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


@dataclass(frozen=True, slots=True)
class WaterfallStage:
    name: StageName
    passed: bool
    required: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "reason": self.reason,
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


def evaluate_waterfall(
    config: DecisionIntelligenceConfig, inp: WaterfallInput
) -> tuple[WaterfallStage, ...]:
    stages: list[WaterfallStage] = []

    # Signal
    if inp.signal_present is None:
        stages.append(
            WaterfallStage(
                "signal",
                not config.require_signal,
                config.require_signal,
                "Signal not assessed — fail closed"
                if config.require_signal
                else "Signal optional/not supplied",
            )
        )
    else:
        stages.append(
            WaterfallStage(
                "signal",
                bool(inp.signal_present),
                config.require_signal,
                "Signal present" if inp.signal_present else "No signal",
            )
        )

    # Strategy consensus
    if inp.strategy_consensus_ok is None:
        stages.append(
            WaterfallStage(
                "strategy_consensus",
                not config.require_strategy_consensus,
                config.require_strategy_consensus,
                "Consensus not assessed — fail closed"
                if config.require_strategy_consensus
                else "Consensus optional/not supplied",
            )
        )
    else:
        stages.append(
            WaterfallStage(
                "strategy_consensus",
                bool(inp.strategy_consensus_ok),
                config.require_strategy_consensus,
                (
                    "Strategy consensus ok"
                    if inp.strategy_consensus_ok
                    else "Strategy consensus failed"
                ),
            )
        )

    # Market regime
    if inp.market_regime_ok is None:
        stages.append(
            WaterfallStage(
                "market_regime",
                not config.require_market_regime_ok,
                config.require_market_regime_ok,
                "Regime not assessed — fail closed"
                if config.require_market_regime_ok
                else "Regime optional/not supplied",
            )
        )
    else:
        stages.append(
            WaterfallStage(
                "market_regime",
                bool(inp.market_regime_ok),
                config.require_market_regime_ok,
                (
                    "Market regime acceptable"
                    if inp.market_regime_ok
                    else "Market regime blocks entry"
                ),
            )
        )

    # Confidence
    conf_ok = (
        inp.confidence is not None and inp.confidence >= config.min_confidence
    )
    stages.append(
        WaterfallStage(
            "confidence",
            conf_ok,
            True,
            (
                f"Confidence {inp.confidence} >= {config.min_confidence}"
                if conf_ok
                else (
                    f"Confidence {inp.confidence} below {config.min_confidence}"
                    if inp.confidence is not None
                    else "Confidence unavailable — fail closed"
                )
            ),
        )
    )

    # Veto checks
    stages.append(
        WaterfallStage(
            "veto_checks",
            inp.veto_clear,
            True,
            "No veto conditions" if inp.veto_clear else "Veto system blocked trade",
        )
    )

    # Risk — always required, fail closed
    if inp.risk_engine_passed is None:
        stages.append(
            WaterfallStage(
                "risk_engine",
                False,
                True,
                "Risk Engine not assessed — fail closed (never bypassed)",
            )
        )
    else:
        stages.append(
            WaterfallStage(
                "risk_engine",
                bool(inp.risk_engine_passed),
                True,
                (
                    "Risk Engine ALLOW"
                    if inp.risk_engine_passed
                    else "Risk Engine did not ALLOW"
                ),
            )
        )

    # Safety — always required, fail closed
    if inp.safety_engine_passed is None:
        stages.append(
            WaterfallStage(
                "safety_engine",
                False,
                True,
                "Safety Engine not assessed — fail closed (never bypassed)",
            )
        )
    else:
        stages.append(
            WaterfallStage(
                "safety_engine",
                bool(inp.safety_engine_passed),
                True,
                (
                    "Safety Engine ALLOW"
                    if inp.safety_engine_passed
                    else "Safety Engine did not ALLOW"
                ),
            )
        )

    required_ok = all(s.passed for s in stages if s.required)
    stages.append(
        WaterfallStage(
            "decision",
            required_ok,
            True,
            (
                "Waterfall clear for advisory APPROVE (execution still gated)"
                if required_ok
                else "Waterfall blocked — REJECT/HOLD"
            ),
        )
    )
    return tuple(stages)
