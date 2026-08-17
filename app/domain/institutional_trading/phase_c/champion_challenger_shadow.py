"""Champion / Challenger shadow layer — challenger NEVER executes.

Wraps existing performance_lab.champion_challenger and hard-blocks OMS /
ExecutionBridge / Gateway / MT5 for challenger paths.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

FORBIDDEN_CHALLENGER_CALLS = frozenset(
    {
        "OMS",
        "ExecutionBridge",
        "Gateway",
        "MT5",
        "order_send",
        "submit_market",
    }
)


class ChallengerExecutionForbidden(RuntimeError):
    """Raised if any code path attempts challenger live execution."""


def assert_challenger_cannot_execute() -> None:
    """Hard invariant used by tests and runtime guards."""
    # Import existing hard flag
    try:
        from app.domain.institutional_trading.performance_lab.config import (
            DEFAULT_LAB_CONFIG,
        )

        if bool(getattr(DEFAULT_LAB_CONFIG, "challenger_may_execute", False)):
            raise ChallengerExecutionForbidden(
                "performance_lab.challenger_may_execute must be False"
            )
    except ChallengerExecutionForbidden:
        raise
    except Exception:
        pass


def forbid_challenger_execution(target: str) -> None:
    if str(target) in FORBIDDEN_CHALLENGER_CALLS:
        raise ChallengerExecutionForbidden(
            f"Challenger must not call {target}"
        )


@dataclass
class ShadowOpportunity:
    id: str
    timestamp: str
    symbol: str
    direction: str
    strategy: str
    champion_score: float | None
    challenger_score: float | None
    champion_action: str
    challenger_action: str
    market_regime: str
    execution_assumptions: dict[str, Any]
    hypothetical_R: float | None
    hypothetical_outcome: str | None
    challenger_executed: bool = False
    oms_called: bool = False
    gateway_called: bool = False
    mt5_called: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy": self.strategy,
            "champion_score": self.champion_score,
            "challenger_score": self.challenger_score,
            "champion_action": self.champion_action,
            "challenger_action": self.challenger_action,
            "market_regime": self.market_regime,
            "execution_assumptions": dict(self.execution_assumptions),
            "hypothetical_R": self.hypothetical_R,
            "hypothetical_outcome": self.hypothetical_outcome,
            "challenger_executed": False,
            "oms_called": False,
            "gateway_called": False,
            "mt5_called": False,
            "execution_authority": False,
        }


@dataclass
class ChampionChallengerShadowStore:
    champion_version: str = "production"
    challenger_version: str | None = None
    opportunities: deque[ShadowOpportunity] = field(
        default_factory=lambda: deque(maxlen=500)
    )
    _lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        assert_challenger_cannot_execute()

    def record_shadow(self, **kwargs: Any) -> ShadowOpportunity:
        assert_challenger_cannot_execute()
        # Refuse any attempt to mark executed
        if kwargs.get("challenger_executed") or kwargs.get("oms_called"):
            raise ChallengerExecutionForbidden(
                "Cannot mark challenger as executed / OMS-called"
            )
        opp = ShadowOpportunity(
            id=str(kwargs.get("id") or uuid4()),
            timestamp=str(kwargs.get("timestamp") or datetime.now(UTC).isoformat()),
            symbol=str(kwargs.get("symbol") or ""),
            direction=str(kwargs.get("direction") or ""),
            strategy=str(kwargs.get("strategy") or ""),
            champion_score=(
                float(kwargs["champion_score"])
                if kwargs.get("champion_score") is not None
                else None
            ),
            challenger_score=(
                float(kwargs["challenger_score"])
                if kwargs.get("challenger_score") is not None
                else None
            ),
            champion_action=str(kwargs.get("champion_action") or "UNKNOWN"),
            challenger_action=str(kwargs.get("challenger_action") or "SHADOW_ONLY"),
            market_regime=str(kwargs.get("market_regime") or "UNKNOWN"),
            execution_assumptions=dict(kwargs.get("execution_assumptions") or {}),
            hypothetical_R=(
                float(kwargs["hypothetical_R"])
                if kwargs.get("hypothetical_R") is not None
                else None
            ),
            hypothetical_outcome=kwargs.get("hypothetical_outcome"),
            challenger_executed=False,
            oms_called=False,
            gateway_called=False,
            mt5_called=False,
        )
        with self._lock:
            if kwargs.get("challenger_version"):
                self.challenger_version = str(kwargs["challenger_version"])
            if kwargs.get("champion_version"):
                self.champion_version = str(kwargs["champion_version"])
            self.opportunities.append(opp)
        return opp

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [o.to_dict() for o in self.opportunities]
            hyp_r = [
                float(o.hypothetical_R)
                for o in self.opportunities
                if o.hypothetical_R is not None
            ]
            champ_r = [
                float(o.champion_score)
                for o in self.opportunities
                if o.champion_score is not None
            ]
        hyp_metrics: dict[str, Any] | None = None
        relative: dict[str, Any] | None = None
        if hyp_r:
            n = len(hyp_r)
            wins = [r for r in hyp_r if r > 0]
            avg = sum(hyp_r) / n
            eq = 0.0
            peak = 0.0
            max_dd = 0.0
            for r in hyp_r:
                eq += r
                peak = max(peak, eq)
                max_dd = max(max_dd, peak - eq)
            hyp_metrics = {
                "sample_count": n,
                "hypothetical_expectancy": round(avg, 6),
                "hypothetical_drawdown": round(max_dd, 6),
                "win_rate": round(100.0 * len(wins) / n, 2) if n else None,
                "state": "COMPUTED" if n >= 20 else "INSUFFICIENT_SAMPLE",
            }
        if hyp_r and champ_r and min(len(hyp_r), len(champ_r)) >= 1:
            from app.domain.institutional_trading.phase_c.fair_comparison import (
                compare_champion_challenger,
            )

            # Matched on available length — never invent superiority on thin data
            m = min(len(hyp_r), len(champ_r))
            relative = compare_champion_challenger(
                champion_r=champ_r[-m:],
                challenger_r=hyp_r[-m:],
                min_sample=20,
            )
        return {
            "champion_version": self.champion_version,
            "challenger_version": self.challenger_version,
            "shadow_samples": len(rows),
            "challenger_execution_authority": False,
            "challenger_may_call_oms": False,
            "challenger_may_call_gateway": False,
            "challenger_may_call_mt5": False,
            "hypothetical": hyp_metrics,
            "relative_performance": relative,
            "recent": rows[-20:],
        }
