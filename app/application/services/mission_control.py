"""Application service — QuantForg Mission Control."""

from __future__ import annotations

from typing import Any

from app.application.services.ai_trading_robot import AiTradingRobotService
from app.application.services.decision_intelligence import DecisionIntelligenceService
from app.application.services.institutional_ai_decision import (
    InstitutionalAiDecisionService,
)
from app.application.services.market_intelligence import MarketIntelligenceService
from app.domain.institutional_trading.operations.control_plane import get_control_plane
from app.domain.institutional_trading.reliability.platform import (
    get_reliability_platform,
)
from app.domain.mission_control import MissionControlCenter, MissionFeeds
from app.domain.mission_control.config import DEFAULT_MC_CONFIG, MissionControlConfig


class MissionControlService:
    def __init__(self, config: MissionControlConfig | None = None) -> None:
        self._center = MissionControlCenter(config or DEFAULT_MC_CONFIG)
        self._di = DecisionIntelligenceService()
        self._iad = InstitutionalAiDecisionService()
        self._robot = AiTradingRobotService()
        self._mi = MarketIntelligenceService()

    def status(self) -> dict[str, object]:
        return self._center.status()

    def dashboard(
        self,
        *,
        capital: dict[str, Any] | None = None,
        positions: list[dict[str, Any]] | None = None,
        xauusd: dict[str, Any] | None = None,
        daily: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        feeds = self._collect_feeds(
            capital=capital,
            positions=positions,
            xauusd=xauusd,
            daily=daily,
        )
        return self._center.build_dashboard(feeds)

    def notes(self, *, limit: int = 50) -> dict[str, Any]:
        return self._center.list_notes(limit=limit)

    def add_note(
        self,
        text: str,
        *,
        operator: str = "operator",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._center.add_note(text, operator=operator, tags=tags)

    def search(self, query: str) -> dict[str, Any]:
        timeline = self._safe_timeline()
        return self._center.search(query, timeline=timeline)

    def _collect_feeds(
        self,
        *,
        capital: dict[str, Any] | None,
        positions: list[dict[str, Any]] | None,
        xauusd: dict[str, Any] | None,
        daily: dict[str, Any] | None,
    ) -> MissionFeeds:
        plane = get_control_plane()
        reliability = get_reliability_platform()
        try:
            control_center = plane.control_center()
        except Exception:
            control_center = None
        try:
            readiness = plane.readiness_dashboard()
        except Exception:
            readiness = None
        try:
            rel_dash = reliability.operational_dashboard()
        except Exception:
            rel_dash = None
        incidents: list[dict[str, Any]] | None
        try:
            incidents = [
                i.to_dict()
                for i in reliability.incidents.list(limit=20)
                if i.status.value != "RESOLVED"
            ]
        except Exception:
            incidents = None
        timeline = self._safe_timeline()

        di_status = self._safe_status(self._di.status)
        di_hist: list[dict[str, Any]] | None
        try:
            raw = self._di.history(limit=15)
            rows = raw.get("decisions") if isinstance(raw, dict) else None
            di_hist = (
                [r for r in rows if isinstance(r, dict)]
                if isinstance(rows, list)
                else []
            )
        except Exception:
            di_hist = None

        return MissionFeeds(
            control_center=control_center,
            readiness=readiness,
            reliability=rel_dash,
            incidents=incidents,
            timeline=timeline,
            decision_intelligence=di_status,
            decision_history=di_hist,
            institutional_decision=self._safe_status(self._iad.status),
            ai_robot=self._safe_status(self._robot.status),
            market_intelligence=self._safe_status(self._mi.status),
            capital=capital,
            positions=positions,
            xauusd=xauusd,
            daily=daily,
        )

    def _safe_timeline(self) -> list[dict[str, Any]] | None:
        try:
            platform = get_reliability_platform()
            rows = platform.timeline.search(limit=40)
            return [e.to_dict() for e in rows]
        except Exception:
            return None

    @staticmethod
    def _safe_status(fn: Any) -> dict[str, Any] | None:
        try:
            out = fn()
            return out if isinstance(out, dict) else None
        except Exception:
            return None
