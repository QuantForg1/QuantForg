"""Application service — QuantForg Intelligence Platform."""

from __future__ import annotations

from typing import Any

from app.application.services.ai_trading_robot import AiTradingRobotService
from app.application.services.decision_intelligence import DecisionIntelligenceService
from app.application.services.institutional_ai_decision import (
    InstitutionalAiDecisionService,
)
from app.application.services.market_intelligence import MarketIntelligenceService
from app.application.services.strategy_research_lab import StrategyResearchLabService
from app.domain.institutional_trading.reliability.platform import (
    get_reliability_platform,
)
from app.domain.intelligence_platform import (
    IntelligenceFeeds,
    IntelligencePlatformCenter,
)
from app.domain.intelligence_platform.config import (
    DEFAULT_IP_CONFIG,
    IntelligencePlatformConfig,
)


class IntelligencePlatformService:
    """Research facade — never order_send; never mutates production execution."""

    def __init__(self, config: IntelligencePlatformConfig | None = None) -> None:
        self._center = IntelligencePlatformCenter(config or DEFAULT_IP_CONFIG)
        self._di = DecisionIntelligenceService()
        self._lab = StrategyResearchLabService()
        self._iad = InstitutionalAiDecisionService()
        self._robot = AiTradingRobotService()
        self._mi = MarketIntelligenceService()

    def status(self) -> dict[str, object]:
        return self._center.status()

    def dashboard(
        self,
        *,
        execution_journal: list[dict[str, Any]] | None = None,
        execution_audits: list[dict[str, Any]] | None = None,
        execution_analytics: dict[str, Any] | None = None,
        candles: list[dict[str, Any]] | None = None,
        weekly_report: dict[str, Any] | None = None,
        monthly_report: dict[str, Any] | None = None,
        library: list[dict[str, Any]] | None = None,
        closed_trades: list[dict[str, Any]] | None = None,
        decision_replay: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        feeds = self._collect_feeds(
            execution_journal=execution_journal,
            execution_audits=execution_audits,
            execution_analytics=execution_analytics,
            candles=candles,
            weekly_report=weekly_report,
            monthly_report=monthly_report,
            library=library,
            closed_trades=closed_trades,
            decision_replay=decision_replay,
        )
        return self._center.build_dashboard(feeds)

    def knowledge(self, *, limit: int = 50) -> dict[str, Any]:
        return self._center.list_knowledge(limit=limit)

    def add_knowledge(
        self,
        *,
        title: str,
        body: str,
        author: str = "researcher",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._center.add_knowledge(
            title=title, body=body, author=author, tags=tags
        )

    def search_knowledge(self, query: str) -> dict[str, Any]:
        return self._center.search_knowledge(query)

    def replay_load(self, payload: dict[str, Any]) -> dict[str, object]:
        """Lab-isolated candle replay — delegates to Strategy Lab; never production."""
        return self._lab.replay_load(payload)

    def replay_control(self, action: str) -> dict[str, object]:
        return self._lab.replay_control(action)

    def decision_replay(self, audit_id: str) -> dict[str, object]:
        return self._di.replay(audit_id)

    def _collect_feeds(
        self,
        *,
        execution_journal: list[dict[str, Any]] | None,
        execution_audits: list[dict[str, Any]] | None,
        execution_analytics: dict[str, Any] | None,
        candles: list[dict[str, Any]] | None,
        weekly_report: dict[str, Any] | None,
        monthly_report: dict[str, Any] | None,
        library: list[dict[str, Any]] | None,
        closed_trades: list[dict[str, Any]] | None,
        decision_replay: dict[str, Any] | None,
    ) -> IntelligenceFeeds:
        di_hist: list[dict[str, Any]] | None
        try:
            raw = self._di.history(limit=30)
            rows = raw.get("decisions") if isinstance(raw, dict) else None
            di_hist = (
                [r for r in rows if isinstance(r, dict)]
                if isinstance(rows, list)
                else []
            )
        except Exception:
            di_hist = None

        timeline: list[dict[str, Any]] | None
        try:
            events = get_reliability_platform().timeline.search(limit=30)
            timeline = [e.to_dict() for e in events]
        except Exception:
            timeline = None

        lab_replay: dict[str, Any] | None
        try:
            snap = self._lab.replay_control("snapshot")
            lab_replay = snap if isinstance(snap, dict) else None
        except Exception:
            lab_replay = None

        return IntelligenceFeeds(
            decision_history=di_hist,
            decision_replay=decision_replay,
            decision_status=self._safe(self._di.status),
            lab_registry=self._safe(self._lab.registry),
            lab_promotion=self._safe(self._lab.promotion_dashboard),
            lab_replay=lab_replay,
            lab_status=self._safe(self._lab.status),
            ai_robot_status=self._safe(self._robot.status),
            institutional_decision_status=self._safe(self._iad.status),
            market_intelligence_status=self._safe(self._mi.status),
            execution_journal=execution_journal,
            execution_audits=execution_audits,
            execution_analytics=execution_analytics,
            candles=candles,
            weekly_report=weekly_report,
            monthly_report=monthly_report,
            library=library,
            closed_trades=closed_trades,
            reliability_timeline=timeline,
        )

    @staticmethod
    def _safe(fn: Any) -> dict[str, Any] | None:
        try:
            out = fn()
            return out if isinstance(out, dict) else None
        except Exception:
            return None
