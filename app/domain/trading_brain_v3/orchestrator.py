"""Institutional Trading Brain V3 orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading_brain_v3.challenge import run_decision_challenge
from app.domain.trading_brain_v3.config import (
    DEFAULT_BRAIN_CONFIG,
    TradingBrainConfig,
)
from app.domain.trading_brain_v3.discipline import compute_discipline_score
from app.domain.trading_brain_v3.environment import evaluate_environment
from app.domain.trading_brain_v3.execution_readiness import (
    evaluate_execution_readiness,
)
from app.domain.trading_brain_v3.operator_advisor import advise_operator
from app.domain.trading_brain_v3.opportunity import (
    discover_opportunities,
    rank_opportunities,
)
from app.domain.trading_brain_v3.post_trade import evaluate_post_trade
from app.domain.trading_brain_v3.quality_dashboard import build_quality_dashboard
from app.domain.trading_brain_v3.supervisor import supervise_active_trade
from app.domain.trading_brain_v3.types import BrainInput


@dataclass
class TradingBrainV3:
    config: TradingBrainConfig = field(
        default_factory=lambda: DEFAULT_BRAIN_CONFIG
    )
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "environment_intelligence",
                "opportunity_discovery",
                "opportunity_ranking",
                "decision_challenge",
                "execution_readiness",
                "active_trade_supervisor",
                "post_trade_intelligence",
                "continuous_quality_dashboard",
                "operator_advisor",
                "institutional_discipline_score",
            ],
            "capabilities": {
                "xauusd_only": True,
                "uses_decision_center": True,
                "uses_risk_engine": True,
                "uses_safety_engine": True,
                "uses_execution_pipeline": True,
                "alternate_execution_path": False,
                "never_order_send": True,
                "never_bypass_risk": True,
                "never_bypass_safety": True,
                "never_invents_market_data": True,
                "explainable": True,
                "configurable_thresholds": True,
                "may_recommend_no_trade": True,
                "promise_profitability": False,
                "eliminates_losses": False,
                "symbol": GOLD_SYMBOL,
            },
            "recent": self.history[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.history[: max(1, min(limit, self.config.max_history))]
        return {"status": "available" if rows else "empty", "items": rows}

    def evaluate(self, inp: BrainInput) -> dict[str, Any]:
        audit_id = f"tb3_{uuid4().hex[:12]}"
        env = evaluate_environment(inp, self.config)
        discovery = discover_opportunities(inp, self.config)
        ranking = rank_opportunities(discovery, self.config)
        challenge = run_decision_challenge(inp, self.config)
        readiness = evaluate_execution_readiness(inp, self.config)
        supervisor = supervise_active_trade(inp, self.config)
        post = evaluate_post_trade(inp, self.config)

        module_scores = {
            "environment": env.score,
            "discovery": discovery.score,
            "ranking": ranking.score,
            "challenge": challenge.score,
            "readiness": readiness.score,
            "supervisor": supervisor.score,
            "post_trade": post.score,
        }
        quality = build_quality_dashboard(
            inp, self.config, module_scores=module_scores
        )
        discipline = compute_discipline_score(
            inp,
            self.config,
            env_score=env.score,
            challenge_score=challenge.score,
            readiness_score=readiness.score,
            post_trade_score=post.score,
            quality_score=quality.score,
        )

        # Final recommendation: No Trade unless core gates pass.
        gates = [env, ranking, challenge, readiness, discipline]
        no_trade = False
        gate_reasons: list[str] = []
        for g in gates:
            if g.passed is False or g.recommendation == "No Trade":
                no_trade = True
                gate_reasons.extend(list(g.reasons)[:1])
        if inp.risk_engine_passed is not True or inp.safety_engine_passed is not True:
            no_trade = True
            gate_reasons.append(
                "Risk/Safety must pass via existing engines — Brain never bypasses"
            )
        if inp.kill_switch is True:
            no_trade = True
            gate_reasons.append("Kill switch — No Trade")

        recommendation = "No Trade" if no_trade else "Proceed"
        advisor = advise_operator(
            inp,
            self.config,
            recommendation=recommendation,
            module_reasons=gate_reasons,
        )

        modules = {
            "environment_intelligence": env.to_dict(),
            "opportunity_discovery": discovery.to_dict(),
            "opportunity_ranking": ranking.to_dict(),
            "decision_challenge": challenge.to_dict(),
            "execution_readiness": readiness.to_dict(),
            "active_trade_supervisor": supervisor.to_dict(),
            "post_trade_intelligence": post.to_dict(),
            "continuous_quality_dashboard": quality.to_dict(),
            "operator_advisor": advisor.to_dict(),
            "institutional_discipline_score": discipline.to_dict(),
        }

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "side": inp.side,
            "recommendation": recommendation,
            "discipline_score": (
                str(discipline.score) if discipline.score is not None else None
            ),
            "modules": modules,
            "advisory_only": True,
            "never_order_send": True,
            "alternate_execution_path": False,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "uses_decision_center": inp.decision_center is not None,
            "uses_risk_engine": inp.risk_engine_passed is not None,
            "uses_safety_engine": inp.safety_engine_passed is not None,
            "execution_pipeline_unchanged": True,
            "invented_market_data": False,
            "promise_profitability": False,
            "eliminates_losses": False,
            "explainable": True,
            "inputs": _input_to_dict(inp),
        }
        self.history.insert(
            0,
            {
                "audit_id": audit_id,
                "recommendation": recommendation,
                "discipline_score": result["discipline_score"],
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def _input_to_dict(inp: BrainInput) -> dict[str, Any]:
    return {
        "side": inp.side,
        "spread": str(inp.spread) if inp.spread is not None else None,
        "atr": str(inp.atr) if inp.atr is not None else None,
        "regime": inp.regime,
        "session": inp.session,
        "news_blackout": inp.news_blackout,
        "kill_switch": inp.kill_switch,
        "confidence": str(inp.confidence) if inp.confidence is not None else None,
        "opportunity_candidates": inp.opportunity_candidates,
        "decision_center": inp.decision_center,
        "risk_engine_passed": inp.risk_engine_passed,
        "safety_engine_passed": inp.safety_engine_passed,
        "execution_mode": inp.execution_mode,
        "open_positions": inp.open_positions,
        "unrealized_pnl": (
            str(inp.unrealized_pnl) if inp.unrealized_pnl is not None else None
        ),
        "active_trade": inp.active_trade,
        "closed_trades": inp.closed_trades,
        "quality_metrics": inp.quality_metrics,
        "operator_notes": inp.operator_notes,
    }


def input_from_dict(data: dict[str, Any]) -> BrainInput:
    def _dec(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    def _opt_bool(v: Any) -> bool | None:
        return v if isinstance(v, bool) else None

    def _opt_int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    return BrainInput(
        side=str(data.get("side") or "buy"),
        spread=_dec(data.get("spread")),
        atr=_dec(data.get("atr")),
        regime=str(data["regime"]) if data.get("regime") else None,
        session=str(data["session"]) if data.get("session") else None,
        news_blackout=_opt_bool(data.get("news_blackout")),
        kill_switch=_opt_bool(data.get("kill_switch")),
        confidence=_dec(data.get("confidence")),
        opportunity_candidates=(
            data.get("opportunity_candidates")
            if isinstance(data.get("opportunity_candidates"), list)
            else None
        ),
        decision_center=(
            data.get("decision_center")
            if isinstance(data.get("decision_center"), dict)
            else None
        ),
        risk_engine_passed=_opt_bool(data.get("risk_engine_passed")),
        safety_engine_passed=_opt_bool(data.get("safety_engine_passed")),
        execution_mode=(
            str(data["execution_mode"]) if data.get("execution_mode") else None
        ),
        open_positions=_opt_int(data.get("open_positions")),
        unrealized_pnl=_dec(data.get("unrealized_pnl")),
        active_trade=(
            data.get("active_trade")
            if isinstance(data.get("active_trade"), dict)
            else None
        ),
        closed_trades=(
            data.get("closed_trades")
            if isinstance(data.get("closed_trades"), list)
            else None
        ),
        quality_metrics=(
            data.get("quality_metrics")
            if isinstance(data.get("quality_metrics"), dict)
            else None
        ),
        operator_notes=(
            [str(x) for x in data["operator_notes"]]
            if isinstance(data.get("operator_notes"), list)
            else None
        ),
    )
