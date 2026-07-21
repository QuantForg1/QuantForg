"""Strategy Research Lab orchestrator — lab isolation from live execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.strategy_research_lab.comparison import (
    StrategyRunMetrics,
    compare_strategy_runs,
)
from app.domain.strategy_research_lab.config import (
    DEFAULT_LAB_CONFIG,
    StrategyLabConfig,
)
from app.domain.strategy_research_lab.experiments import ParameterExperimentManager
from app.domain.strategy_research_lab.promotion import PromotionWorkflow
from app.domain.strategy_research_lab.registry import StrategyRegistry
from app.domain.strategy_research_lab.replay import HistoricalReplayEngine
from app.domain.strategy_research_lab.scorecards import (
    ScorecardInput,
    build_strategy_scorecard,
)
from app.domain.strategy_research_lab.validation_report import build_validation_report
from app.domain.strategy_research_lab.versioning import VersionHistoryStore
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class StrategyLabSnapshot:
    version: str
    symbol: str
    registry: dict[str, object]
    promotion_dashboard: dict[str, object]
    capabilities: dict[str, bool]
    config: dict[str, object]
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "registry": self.registry,
            "promotion_dashboard": self.promotion_dashboard,
            "capabilities": dict(self.capabilities),
            "config": self.config,
            "disclaimer": self.disclaimer,
        }


class StrategyResearchLab:
    """Institutional Strategy Research Lab V1."""

    def __init__(self, config: StrategyLabConfig | None = None) -> None:
        self.config = config or DEFAULT_LAB_CONFIG
        self.registry = StrategyRegistry()
        self.replay = HistoricalReplayEngine(self.config)
        self.experiments = ParameterExperimentManager(self.config)
        self.promotion = PromotionWorkflow(self.config)
        self.versions = VersionHistoryStore()

    def capabilities(self) -> dict[str, bool]:
        return {
            "strategy_registry": True,
            "historical_replay": True,
            "strategy_comparison": True,
            "parameter_experiments": True,
            "promotion_workflow": True,
            "strategy_scorecards": True,
            "explainable_validation_reports": True,
            "operator_approval": True,
            "version_history": True,
            "promotion_dashboard": True,
            "broker_order_submit": False,
            "affects_production_positions": False,
        }

    def status(self) -> dict[str, object]:
        snap = self.snapshot()
        return snap.to_dict()

    def snapshot(self) -> StrategyLabSnapshot:
        cfg = self.config.to_dict()
        return StrategyLabSnapshot(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            registry=self.registry.to_dict(),
            promotion_dashboard=self.promotion.dashboard(),
            capabilities=self.capabilities(),
            config=cfg,
            disclaimer=(
                "Strategy Research Lab is completely separated from live execution. "
                "Historical replay and paper validation never affect production "
                "positions. No mock production metrics. Never submits broker orders."
            ),
        )

    def scorecard(self, payload: dict[str, Any]) -> dict[str, object]:
        inp = ScorecardInput(
            strategy_key=str(payload.get("strategy_key") or "unknown"),
            profit_factor=_dec(payload.get("profit_factor")),
            sharpe=_dec(payload.get("sharpe")),
            max_drawdown_pct=_dec(payload.get("max_drawdown_pct")),
            trade_count=_int(payload.get("trade_count")),
            win_rate=_dec(payload.get("win_rate")),
            stability=_dec(payload.get("stability")),
        )
        card = build_strategy_scorecard(self.config, inp)
        return card.to_dict()

    def validate(self, payload: dict[str, Any]) -> dict[str, object]:
        card = build_strategy_scorecard(
            self.config,
            ScorecardInput(
                strategy_key=str(payload.get("strategy_key") or "unknown"),
                profit_factor=_dec(payload.get("profit_factor")),
                sharpe=_dec(payload.get("sharpe")),
                max_drawdown_pct=_dec(payload.get("max_drawdown_pct")),
                trade_count=_int(payload.get("trade_count")),
                win_rate=_dec(payload.get("win_rate")),
                stability=_dec(payload.get("stability")),
            ),
        )
        notes_raw = payload.get("notes") or []
        notes = tuple(str(n) for n in notes_raw) if isinstance(notes_raw, list) else ()
        report = build_validation_report(
            strategy_key=card.strategy_key,
            scorecard=card,
            notes=notes,
        )
        if card.passed:
            self.registry.set_status(card.strategy_key, "validating")
        return {
            "scorecard": card.to_dict(),
            "report": report.to_dict(),
            "never_submits_orders": True,
        }

    def compare(self, runs: list[dict[str, Any]]) -> dict[str, object]:
        parsed: list[StrategyRunMetrics] = []
        for row in runs:
            if not isinstance(row, dict):
                continue
            parsed.append(
                StrategyRunMetrics(
                    strategy_key=str(row.get("strategy_key") or "unknown"),
                    run_id=str(row.get("run_id") or "run"),
                    profit_factor=_dec(row.get("profit_factor")),
                    sharpe=_dec(row.get("sharpe")),
                    max_drawdown_pct=_dec(row.get("max_drawdown_pct")),
                    trade_count=_int(row.get("trade_count")),
                    win_rate=_dec(row.get("win_rate")),
                    net_pnl=_dec(row.get("net_pnl")),
                )
            )
        return compare_strategy_runs(tuple(parsed))

    def open_promotion(self, payload: dict[str, Any]) -> dict[str, object]:
        card = build_strategy_scorecard(
            self.config,
            ScorecardInput(
                strategy_key=str(payload.get("strategy_key") or "unknown"),
                profit_factor=_dec(payload.get("profit_factor")),
                sharpe=_dec(payload.get("sharpe")),
                max_drawdown_pct=_dec(payload.get("max_drawdown_pct")),
                trade_count=_int(payload.get("trade_count")),
                win_rate=_dec(payload.get("win_rate")),
                stability=_dec(payload.get("stability")),
            ),
        )
        validation_passed = bool(payload.get("validation_passed", card.passed))
        case = self.promotion.open_case(
            strategy_key=card.strategy_key,
            scorecard=card,
            validation_passed=validation_passed,
            notes=str(payload.get("notes") or ""),
        )
        if case["state"] == "rejected":
            self.registry.set_status(card.strategy_key, "rejected")
        else:
            self.registry.set_status(card.strategy_key, "validating")
        return case

    def approve(self, payload: dict[str, Any]) -> dict[str, object] | None:
        result = self.promotion.operator_decide(
            case_id=str(payload.get("case_id") or ""),
            decision=str(payload.get("decision") or "reject"),
            operator=str(payload.get("operator") or "operator"),
            reason=str(payload.get("reason") or ""),
        )
        if result:
            if result["state"] == "promoted":
                self.registry.set_status(str(result["strategy_key"]), "promoted")
            elif result["state"] == "rejected":
                self.registry.set_status(str(result["strategy_key"]), "rejected")
            elif result["state"] == "approved":
                self.registry.set_status(str(result["strategy_key"]), "approved")
        return result


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
