"""Alpha Engine V1 orchestrator — market quality before execution (advisory)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    AlphaEngineConfig,
)
from app.domain.alpha_engine.engines import (
    score_confluence,
    score_continuous,
    score_execution_optimizer,
    score_exit,
    score_liquidity,
    score_opportunity,
    score_order_flow,
    score_regime,
    score_structure,
    score_trade,
)
from app.domain.alpha_engine.history import AlphaHistoryStore
from app.domain.alpha_engine.score import EngineScore
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class AlphaEngineInput:
    regime: dict[str, Any] | None = None
    liquidity: dict[str, Any] | None = None
    structure: dict[str, Any] | None = None
    order_flow: dict[str, Any] | None = None
    opportunities: list[dict[str, Any]] | None = None
    execution: dict[str, Any] | None = None
    exit_context: dict[str, Any] | None = None
    trade_factors: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    side: str = "buy"
    technique: str | None = None


@dataclass(frozen=True, slots=True)
class AlphaEngineResult:
    version: str
    symbol: str
    audit_id: str
    composite_score: Decimal | None
    market_quality_band: str
    market_quality_ok: bool | None
    engines: dict[str, EngineScore]
    decision_center_inputs: dict[str, Any]
    policies: dict[str, object]
    advisory_only: bool = True
    never_places_orders: bool = True
    promise_profitability: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "audit_id": self.audit_id,
            "composite_score": (
                str(self.composite_score)
                if self.composite_score is not None
                else None
            ),
            "market_quality_band": self.market_quality_band,
            "market_quality_ok": self.market_quality_ok,
            "engines": {k: v.to_dict() for k, v in self.engines.items()},
            "decision_center_inputs": dict(self.decision_center_inputs),
            "policies": dict(self.policies),
            "advisory_only": True,
            "never_places_orders": True,
            "promise_profitability": False,
            "changes_execution_architecture": False,
            "bypasses_risk": False,
            "bypasses_safety": False,
        }


@dataclass
class AlphaEngine:
    config: AlphaEngineConfig = field(default_factory=lambda: DEFAULT_ALPHA_CONFIG)
    history: AlphaHistoryStore = field(default_factory=AlphaHistoryStore)

    def __post_init__(self) -> None:
        self.history.max_events = self.config.max_history

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "capabilities": {
                "advisory_only": True,
                "never_places_orders": True,
                "never_invents_market_data": True,
                "promise_profitability": False,
                "bypass_risk": False,
                "bypass_safety": False,
                "explainable_scores": True,
                "configurable_thresholds": True,
                "auditable": True,
                "decision_center_integration": True,
                "symbol": GOLD_SYMBOL,
            },
            "recent": self.history.list(limit=10),
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        self.history.max_events = self.config.max_history
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.history.list(limit=limit)

    def replay(self, audit_id: str) -> dict[str, Any]:
        row = self.history.get(audit_id)
        if row is None:
            return {
                "status": "unavailable",
                "reason": "Unknown audit_id — no invented replay",
            }
        return {"status": "available", "replay": row}

    def evaluate(self, inp: AlphaEngineInput) -> AlphaEngineResult:
        engines: dict[str, EngineScore] = {
            "market_regime": score_regime(self.config, inp.regime),
            "liquidity": score_liquidity(self.config, inp.liquidity),
            "market_structure": score_structure(self.config, inp.structure),
            "order_flow": score_order_flow(self.config, inp.order_flow),
        }
        engines["confluence"] = score_confluence(self.config, engines)
        engines["opportunity"] = score_opportunity(self.config, inp.opportunities)
        engines["execution_optimizer"] = score_execution_optimizer(
            self.config, inp.execution
        )
        engines["exit_intelligence"] = score_exit(self.config, inp.exit_context)
        engines["trade_scoring"] = score_trade(self.config, inp.trade_factors)
        engines["continuous_evaluation"] = score_continuous(
            self.config, inp.closed_trades
        )

        available = [
            e for e in engines.values()
            if e.status == "available" and e.score is not None
        ]
        composite: Decimal | None = None
        market_quality_ok: bool | None = None
        if available:
            composite = (
                sum((e.score for e in available), Decimal("0"))
                / Decimal(str(len(available)))
            ).quantize(Decimal("0.01"))
            market_quality_ok = composite >= self.config.min_composite_for_quality_ok

        band = _band(composite)
        di_inputs = _to_decision_center_inputs(
            engines, composite, market_quality_ok, inp.side
        )

        draft_dict = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "composite_score": str(composite) if composite is not None else None,
            "market_quality_band": band,
            "market_quality_ok": market_quality_ok,
            "engines": {k: v.to_dict() for k, v in engines.items()},
            "decision_center_inputs": di_inputs,
            "policies": self.config.to_dict(),
            "advisory_only": True,
            "never_places_orders": True,
            "promise_profitability": False,
            "changes_execution_architecture": False,
            "bypasses_risk": False,
            "bypasses_safety": False,
        }
        audit_id = self.history.record(draft_dict)
        return AlphaEngineResult(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            audit_id=audit_id,
            composite_score=composite,
            market_quality_band=band,
            market_quality_ok=market_quality_ok,
            engines=engines,
            decision_center_inputs=di_inputs,
            policies=self.config.to_dict(),
        )


def _band(score: Decimal | None) -> str:
    if score is None:
        return "unavailable"
    if score >= Decimal("80"):
        return "institutional"
    if score >= Decimal("65"):
        return "good"
    if score >= Decimal("50"):
        return "fair"
    return "poor"


def _to_decision_center_inputs(
    engines: dict[str, EngineScore],
    composite: Decimal | None,
    market_quality_ok: bool | None,
    side: str,
) -> dict[str, Any]:
    """Map Alpha scores to Decision Center advisory fields — never Risk/Safety."""

    def _factor(engine_id: str) -> Decimal | None:
        e = engines.get(engine_id)
        if e and e.status == "available" and e.score is not None:
            return e.score
        return None

    conf: dict[str, Any] = {}
    if _factor("opportunity") is not None:
        conf["signal_strength"] = str(_factor("opportunity"))
    if _factor("market_structure") is not None:
        conf["structure_align"] = str(_factor("market_structure"))
    if _factor("confluence") is not None:
        conf["consensus"] = str(_factor("confluence"))
    if _factor("market_regime") is not None:
        conf["regime_fit"] = str(_factor("market_regime"))
    if _factor("execution_optimizer") is not None:
        conf["execution_quality"] = str(_factor("execution_optimizer"))

    return {
        "side": side,
        "market_regime_ok": market_quality_ok,
        "confidence_factors": conf,
        "alpha_composite_score": str(composite) if composite is not None else None,
        "alpha_market_quality_band": _band(composite),
        "note": (
            "Advisory Alpha mapping only — Risk Engine and Safety Engine "
            "remain mandatory and unchanged"
        ),
        "never_sets_risk_or_safety": True,
    }
