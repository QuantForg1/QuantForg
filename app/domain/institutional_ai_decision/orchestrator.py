"""Decision Engine V1 orchestrator — dry-run by default; never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.ai_trading_robot.invariants import (
    assert_no_forbidden_technique,
    reject_averaging_into_loss,
)
from app.domain.ai_trading_robot.strategy_health import (
    StrategyHealth,
    compute_strategy_performance,
    score_strategy_health,
)
from app.domain.institutional_ai_decision.adaptive_risk import (
    AdaptiveRiskAllocation,
    allocate_adaptive_risk,
)
from app.domain.institutional_ai_decision.confidence import (
    InstitutionalConfidence,
    score_institutional_confidence,
)
from app.domain.institutional_ai_decision.config import (
    DEFAULT_DECISION_CONFIG,
    DecisionEngineV1Config,
)
from app.domain.institutional_ai_decision.decision_card import (
    DecisionCard,
    build_decision_card,
)
from app.domain.institutional_ai_decision.layers import (
    PIPELINE_LAYERS,
    LayerHints,
    LayerResult,
    evaluate_layers,
    required_layers_passed,
)
from app.domain.institutional_ai_decision.loss_protection import (
    LossProtectionResult,
    evaluate_loss_protection,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class DecisionEvaluateInput:
    side: str = "buy"
    strategy_id: str = "default"
    technique: str | None = None
    dry_run: bool = True
    equity: Decimal = Decimal("10000")
    stop_distance: Decimal = Decimal("5")
    consecutive_losses: int = 0
    daily_drawdown_pct: Decimal = Decimal("0")
    closed_pnls: tuple[Decimal, ...] = ()
    open_side: str | None = None
    open_unrealized_pnl: Decimal | None = None
    layers: LayerHints = field(default_factory=LayerHints)


@dataclass(frozen=True, slots=True)
class DecisionEvaluateResult:
    version: str
    symbol: str
    decision: str
    dry_run: bool
    allow_trade_idea: bool
    layers: tuple[LayerResult, ...]
    confidence: InstitutionalConfidence
    adaptive_risk: AdaptiveRiskAllocation
    loss_protection: LossProtectionResult
    health: StrategyHealth
    card: DecisionCard
    blocked_reasons: tuple[str, ...]
    capabilities: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "decision": self.decision,
            "dry_run": self.dry_run,
            "allow_trade_idea": self.allow_trade_idea,
            "layers": [layer.to_dict() for layer in self.layers],
            "confidence": self.confidence.to_dict(),
            "adaptive_risk": self.adaptive_risk.to_dict(),
            "loss_protection": self.loss_protection.to_dict(),
            "health": self.health.to_dict(),
            "card": self.card.to_dict(),
            "blocked_reasons": list(self.blocked_reasons),
            "capabilities": dict(self.capabilities),
            "execution_note": (
                "Decision Engine V1 never calls order_send. Dry-run validates "
                "signals without sending orders. Live paths must use the "
                "unchanged Execution Gateway after Risk + Safety ALLOW."
            ),
        }


class DecisionEngineV1:
    """Institutional AI Decision Engine V1."""

    def __init__(self, config: DecisionEngineV1Config | None = None) -> None:
        self.config = config or DEFAULT_DECISION_CONFIG

    def capabilities(self) -> dict[str, bool]:
        return {
            "multi_layer_pipeline": True,
            "institutional_confidence_score": True,
            "adaptive_risk_allocation": True,
            "strategy_health_monitoring": True,
            "automatic_strategy_suspension": True,
            "explainable_decision_cards": True,
            "loss_protection": True,
            "dry_run_mode": True,
            "martingale": False,
            "grid": False,
            "average_down": False,
        }

    def status(self) -> dict[str, object]:
        cfg = self.config.to_dict()
        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "mission": cfg["mission"],
            "pipeline": list(PIPELINE_LAYERS),
            "capabilities": self.capabilities(),
            "config": cfg,
            "disclaimer": (
                "Institutional AI Decision Engine V1 maximizes discipline and "
                "capital preservation. It never promises profitability and never "
                "bypasses Risk Engine or Safety Engine."
            ),
        }

    def evaluate(self, inp: DecisionEvaluateInput) -> DecisionEvaluateResult:
        blocked: list[str] = []
        dry_run = bool(inp.dry_run)

        tech = assert_no_forbidden_technique(inp.technique)
        if not tech.ok:
            blocked.extend(tech.reasons)
        avg = reject_averaging_into_loss(
            open_side=inp.open_side,
            proposed_side=inp.side,
            open_unrealized_pnl=inp.open_unrealized_pnl,
        )
        if not avg.ok:
            blocked.extend(avg.reasons)

        layers = evaluate_layers(self.config, inp.layers)
        for layer in layers:
            if layer.required and not layer.passed:
                blocked.append(layer.reason)

        loss = evaluate_loss_protection(
            self.config,
            consecutive_losses=inp.consecutive_losses,
            daily_drawdown_pct=inp.daily_drawdown_pct,
            spread=inp.layers.spread,
            atr=inp.layers.atr,
            price=inp.layers.price,
        )
        if not loss.passed:
            blocked.extend(r for r in loss.reasons if "clear" not in r.lower())

        perf = compute_strategy_performance(
            strategy_id=inp.strategy_id,
            closed_pnls=list(inp.closed_pnls),
        )
        # Map robot health thresholds onto decision config
        from app.domain.ai_trading_robot.config import RobotV1Config

        health_cfg = RobotV1Config(
            min_health_score=self.config.min_health_score,
            auto_pause_health_below=self.config.auto_suspend_health_below,
        )
        health = score_strategy_health(health_cfg, perf)
        if health.auto_pause:
            blocked.append(
                f"Strategy {health.strategy_id} auto-suspended "
                f"(health {health.score} < {self.config.auto_suspend_health_below})."
            )

        confidence = score_institutional_confidence(
            self.config,
            layers,
            strategy_health=health.score,
            consecutive_losses=inp.consecutive_losses,
            daily_drawdown_pct=inp.daily_drawdown_pct,
        )
        if not confidence.passed:
            blocked.append(
                f"Institutional confidence {confidence.score} below "
                f"{self.config.min_confidence}."
            )

        adaptive = allocate_adaptive_risk(
            self.config,
            confidence,
            equity=inp.equity,
            stop_distance=inp.stop_distance,
            daily_drawdown_pct=inp.daily_drawdown_pct,
            consecutive_losses=inp.consecutive_losses,
        )

        layers_ok = required_layers_passed(layers)
        allow = (
            tech.ok
            and avg.ok
            and layers_ok
            and loss.passed
            and confidence.passed
            and not health.auto_pause
            and adaptive.approved_lots > 0
        )

        if health.auto_pause:
            decision = "SUSPENDED"
        elif allow:
            decision = "TRADE_IDEA"
        else:
            decision = "WAIT"

        # Deduplicate blocked
        seen: set[str] = set()
        unique: list[str] = []
        for reason in blocked:
            if reason not in seen:
                seen.add(reason)
                unique.append(reason)

        card = build_decision_card(
            decision=decision,
            layers=layers,
            confidence=confidence,
            risk=adaptive,
            loss_protection=loss,
            health=health,
            dry_run=dry_run,
        )

        return DecisionEvaluateResult(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            decision=decision,
            dry_run=dry_run,
            allow_trade_idea=decision == "TRADE_IDEA",
            layers=layers,
            confidence=confidence,
            adaptive_risk=adaptive,
            loss_protection=loss,
            health=health,
            card=card,
            blocked_reasons=tuple(unique),
            capabilities=self.capabilities(),
        )
