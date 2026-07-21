"""Intelligence Platform orchestrator — research aggregation only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.intelligence_platform.config import (
    DEFAULT_IP_CONFIG,
    IntelligencePlatformConfig,
)
from app.domain.intelligence_platform.knowledge import KnowledgeBaseStore
from app.domain.intelligence_platform.panel import PanelSnapshot, panel


@dataclass
class IntelligenceFeeds:
    """Recorded / live research feeds only. Missing → unavailable/empty."""

    decision_history: list[dict[str, Any]] | None = None
    decision_replay: dict[str, Any] | None = None
    decision_status: dict[str, Any] | None = None
    lab_registry: dict[str, Any] | None = None
    lab_promotion: dict[str, Any] | None = None
    lab_replay: dict[str, Any] | None = None
    lab_status: dict[str, Any] | None = None
    ai_robot_status: dict[str, Any] | None = None
    institutional_decision_status: dict[str, Any] | None = None
    market_intelligence_status: dict[str, Any] | None = None
    execution_journal: list[dict[str, Any]] | None = None
    execution_audits: list[dict[str, Any]] | None = None
    execution_analytics: dict[str, Any] | None = None
    candles: list[dict[str, Any]] | None = None
    weekly_report: dict[str, Any] | None = None
    monthly_report: dict[str, Any] | None = None
    library: list[dict[str, Any]] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    reliability_timeline: list[dict[str, Any]] | None = None


@dataclass
class IntelligencePlatformCenter:
    config: IntelligencePlatformConfig = field(
        default_factory=lambda: DEFAULT_IP_CONFIG
    )
    knowledge: KnowledgeBaseStore = field(default_factory=KnowledgeBaseStore)

    def __post_init__(self) -> None:
        self.knowledge.max_entries = self.config.max_knowledge

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "capabilities": {
                "research_only": True,
                "never_submits_orders": True,
                "never_affects_production": True,
                "fabricate_metrics": False,
                "broker_orders": False,
                "replay_isolated": True,
                "knowledge_base": True,
                "strategy_registry_compose": True,
                "promotion_compose": True,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def add_knowledge(
        self,
        *,
        title: str,
        body: str,
        author: str = "researcher",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.knowledge.add(
            title=title, body=body, author=author, tags=tags
        ).to_dict()

    def list_knowledge(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.knowledge.list(limit=limit)
        return {
            "status": "available" if rows else "empty",
            "source": "intelligence_platform.knowledge",
            "entries": [e.to_dict() for e in rows],
        }

    def search_knowledge(self, query: str) -> dict[str, Any]:
        rows = self.knowledge.search(query)
        return {
            "query": query.strip(),
            "status": "available" if rows else "empty",
            "entries": [e.to_dict() for e in rows],
        }

    def build_dashboard(self, feeds: IntelligenceFeeds) -> dict[str, Any]:
        panels = [
            self._replay_studio(feeds),
            self._candle_playback(feeds),
            self._decision_inspector(feeds),
            self._trade_review(feeds),
            self._ai_evaluation(feeds),
            self._research_workspace(),
            self._knowledge_panel(feeds),
            self._weekly(feeds),
            self._monthly(feeds),
            self._promotion(feeds),
            self._registry(feeds),
            self._governance(feeds),
        ]
        return {
            "product": self.config.product,
            "version": self.config.version,
            "never_submits_orders": True,
            "never_affects_production": True,
            "fabricates_metrics": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "panels": {p.panel_id: p.to_dict() for p in panels},
            "panel_order": [p.panel_id for p in panels],
            "deep_links": {
                "research": "/research",
                "strategy_lab": "/strategy-lab",
                "trade_replay": "/trade-replay",
                "decision_intelligence": "/decision-intelligence",
                "journal": "/journal",
                "analytics": "/analytics",
            },
        }

    def _replay_studio(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        audits = feeds.execution_audits
        di_hist = feeds.decision_history
        lab = feeds.lab_replay
        if audits is None and di_hist is None and lab is None:
            return panel(
                "replay_studio",
                "Replay Studio",
                source="execution.audits|decision_intelligence|strategy_lab.replay",
                status="unavailable",
                message="No recorded replay feeds",
            )
        data: dict[str, Any] = {
            "production_isolated": True,
            "never_submits_orders": True,
            "deep_link": "/trade-replay",
        }
        if audits is not None:
            rows = audits[: self.config.max_audits]
            data["audits"] = rows
            data["audit_count"] = len(rows)
        if di_hist is not None:
            data["decision_count"] = len(di_hist)
            data["recent_decisions"] = di_hist[:10]
        if lab is not None:
            data["lab_replay"] = lab
        empty = (
            (audits is not None and len(audits) == 0)
            and (di_hist is not None and len(di_hist) == 0)
            and (lab is None or not lab)
        )
        if empty:
            return panel(
                "replay_studio",
                "Replay Studio",
                source="execution.audits|decision_intelligence|strategy_lab.replay",
                status="empty",
                message="No recorded audits or decisions to replay",
                data=data,
            )
        return panel(
            "replay_studio",
            "Replay Studio",
            source="execution.audits|decision_intelligence|strategy_lab.replay",
            data=data,
            message="Research replay only — never affects production",
        )

    def _candle_playback(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        candles = feeds.candles
        lab = feeds.lab_replay
        if candles is None and lab is None:
            return panel(
                "candle_playback",
                "Candle-by-Candle Playback",
                source="mt5.candles|strategy_lab.replay",
                status="unavailable",
                message="Awaiting recorded bars (never invents candles)",
            )
        data: dict[str, Any] = {
            "production_isolated": True,
            "invents_candles": False,
        }
        if candles is not None:
            data["candle_count"] = len(candles)
            data["preview"] = candles[:5]
            data["symbol"] = self.config.symbol
        if lab is not None:
            data["lab_replay"] = lab
        if candles is not None and len(candles) == 0 and not lab:
            return panel(
                "candle_playback",
                "Candle-by-Candle Playback",
                source="mt5.candles|strategy_lab.replay",
                status="empty",
                message="No bars loaded",
                data=data,
            )
        return panel(
            "candle_playback",
            "Candle-by-Candle Playback",
            source="mt5.candles|strategy_lab.replay",
            data=data,
            message="Playback uses supplied bars only — lab-isolated",
        )

    def _decision_inspector(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        hist = feeds.decision_history
        replay = feeds.decision_replay
        if hist is None and replay is None:
            return panel(
                "decision_inspector",
                "Decision Inspector",
                source="decision_intelligence.history|replay",
                status="unavailable",
                message="Decision history feed unavailable",
            )
        data: dict[str, Any] = {
            "deep_link": "/decision-intelligence",
            "never_force_execution": True,
        }
        if hist is not None:
            rows = hist[: self.config.max_decisions]
            data["decisions"] = rows
            data["count"] = len(rows)
        if replay is not None:
            data["replay"] = replay
        if hist is not None and len(hist) == 0 and replay is None:
            return panel(
                "decision_inspector",
                "Decision Inspector",
                source="decision_intelligence.history|replay",
                status="empty",
                message="No auditable decisions yet",
                data=data,
            )
        return panel(
            "decision_inspector",
            "Decision Inspector",
            source="decision_intelligence.history|replay",
            data=data,
        )

    def _trade_review(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        journal = feeds.execution_journal
        closed = feeds.closed_trades
        if journal is None and closed is None:
            return panel(
                "trade_review_center",
                "Trade Review Center",
                source="execution.journal|portfolio.history",
                status="unavailable",
                message="Awaiting recorded trade history",
            )
        data: dict[str, Any] = {"deep_link": "/journal"}
        if journal is not None:
            rows = journal[: self.config.max_trades]
            data["journal"] = rows
            data["journal_count"] = len(rows)
        if closed is not None:
            rows = closed[: self.config.max_trades]
            data["closed_trades"] = rows
            data["closed_count"] = len(rows)
        empty_j = journal is not None and len(journal) == 0
        empty_c = closed is not None and len(closed) == 0
        if (journal is None or empty_j) and (closed is None or empty_c):
            return panel(
                "trade_review_center",
                "Trade Review Center",
                source="execution.journal|portfolio.history",
                status="empty",
                message="No recorded trades",
                data=data,
            )
        return panel(
            "trade_review_center",
            "Trade Review Center",
            source="execution.journal|portfolio.history",
            data=data,
            message="Recorded trades only — no mock fills",
        )

    def _ai_evaluation(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        modules = {
            "decision_intelligence": feeds.decision_status,
            "institutional_decision": feeds.institutional_decision_status,
            "ai_robot": feeds.ai_robot_status,
            "market_intelligence": feeds.market_intelligence_status,
            "strategy_lab": feeds.lab_status,
        }
        present = {k: v for k, v in modules.items() if isinstance(v, dict)}
        analytics = feeds.execution_analytics
        if not present and analytics is None:
            return panel(
                "ai_evaluation_dashboard",
                "AI Evaluation Dashboard",
                source="ai.*.status|execution.analytics",
                status="unavailable",
                message="AI status feeds unavailable",
            )
        data: dict[str, Any] = {
            "modules": {
                name: {
                    "product": body.get("product") or name,
                    "ok": True,
                }
                for name, body in present.items()
            },
            "module_count": len(present),
            "never_submits_orders": True,
        }
        if analytics is not None:
            # Pass through only — never invent sample metrics.
            data["execution_analytics"] = analytics
            data["analytics_status"] = analytics.get("status")
        return panel(
            "ai_evaluation_dashboard",
            "AI Evaluation Dashboard",
            source="ai.*.status|execution.analytics",
            data=data,
        )

    def _research_workspace(self) -> PanelSnapshot:
        return panel(
            "research_workspace",
            "Research Workspace",
            source="research.os",
            data={
                "href": "/research",
                "label": "Open Research OS",
                "hint": "Idea → promote pipeline (advisory)",
            },
            message="Deep-link to Research OS — no duplicated workflow widgets",
        )

    def _knowledge_panel(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        owned = self.knowledge.list(limit=20)
        library = feeds.library
        data: dict[str, Any] = {
            "entries": [e.to_dict() for e in owned],
            "entry_count": len(owned),
        }
        if library is not None:
            data["library"] = library[:30]
            data["library_count"] = len(library)
        if not owned and (library is None or len(library) == 0):
            return panel(
                "knowledge_base",
                "Knowledge Base",
                source="intelligence_platform.knowledge|research.library",
                status="empty",
                message="No knowledge entries yet",
                data=data,
            )
        return panel(
            "knowledge_base",
            "Knowledge Base",
            source="intelligence_platform.knowledge|research.library",
            data=data,
        )

    def _weekly(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        report = feeds.weekly_report
        if report is None:
            return panel(
                "weekly_reports",
                "Weekly Reports",
                source="ecosystem.reports.weekly",
                status="unavailable",
                message="Weekly report feed unavailable",
            )
        if not report:
            return panel(
                "weekly_reports",
                "Weekly Reports",
                source="ecosystem.reports.weekly",
                status="empty",
                message="No weekly report artifact",
                data={"period": "weekly"},
            )
        return panel(
            "weekly_reports",
            "Weekly Reports",
            source="ecosystem.reports.weekly",
            data={"period": "weekly", "report": report},
            message="Generated from recorded ecosystem data only",
        )

    def _monthly(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        report = feeds.monthly_report
        analytics = feeds.execution_analytics
        if report is None and analytics is None:
            return panel(
                "monthly_performance_reports",
                "Monthly Performance Reports",
                source="ecosystem.reports.monthly|execution.analytics",
                status="unavailable",
                message="Monthly performance feeds unavailable",
            )
        data: dict[str, Any] = {"period": "monthly"}
        if report is not None:
            data["report"] = report
        if analytics is not None:
            data["execution_analytics"] = analytics
            data["analytics_status"] = analytics.get("status")
        if (not report) and (analytics is None or not analytics):
            return panel(
                "monthly_performance_reports",
                "Monthly Performance Reports",
                source="ecosystem.reports.monthly|execution.analytics",
                status="empty",
                message="Insufficient recorded history",
                data=data,
            )
        return panel(
            "monthly_performance_reports",
            "Monthly Performance Reports",
            source="ecosystem.reports.monthly|execution.analytics",
            data=data,
            message="Recorded analytics only — no fabricated P&L",
        )

    def _promotion(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        promo = feeds.lab_promotion
        if promo is None:
            return panel(
                "strategy_promotion_workflow",
                "Strategy Promotion Workflow",
                source="strategy_lab.promotion",
                status="unavailable",
                message="Promotion feed unavailable",
            )
        data = {
            "dashboard": promo,
            "deep_link": "/strategy-lab",
            "forwarded_to_live_execution": False,
            "never_submits_orders": True,
        }
        cases = promo.get("cases") or promo.get("open_cases") or []
        if isinstance(cases, list) and len(cases) == 0 and not promo:
            return panel(
                "strategy_promotion_workflow",
                "Strategy Promotion Workflow",
                source="strategy_lab.promotion",
                status="empty",
                message="No promotion cases",
                data=data,
            )
        return panel(
            "strategy_promotion_workflow",
            "Strategy Promotion Workflow",
            source="strategy_lab.promotion",
            data=data,
            message="Lab promotion only — never enables live order_send",
        )

    def _registry(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        reg = feeds.lab_registry
        if reg is None:
            return panel(
                "strategy_registry_foundation",
                "Strategy Registry Foundation",
                source="strategy_lab.registry",
                status="unavailable",
                message="Registry feed unavailable",
            )
        strategies = (
            reg.get("strategies")
            or reg.get("items")
            or reg.get("entries")
            or []
        )
        if not isinstance(strategies, list):
            strategies = []
        data = {
            "registry": reg,
            "strategy_count": len(strategies),
            "deep_link": "/strategy-lab",
        }
        if len(strategies) == 0 and not reg:
            return panel(
                "strategy_registry_foundation",
                "Strategy Registry Foundation",
                source="strategy_lab.registry",
                status="empty",
                message="Registry empty",
                data=data,
            )
        return panel(
            "strategy_registry_foundation",
            "Strategy Registry Foundation",
            source="strategy_lab.registry",
            data=data,
        )

    def _governance(self, feeds: IntelligenceFeeds) -> PanelSnapshot:
        audits = feeds.execution_audits
        di = feeds.decision_history
        timeline = feeds.reliability_timeline
        promo = feeds.lab_promotion
        if audits is None and di is None and timeline is None and promo is None:
            return panel(
                "ai_governance_audit",
                "AI Governance & Audit",
                source="execution.audits|decision_intelligence|reliability",
                status="unavailable",
                message="Governance feeds unavailable",
            )
        data: dict[str, Any] = {
            "never_submits_orders": True,
            "never_affects_production": True,
        }
        if audits is not None:
            data["audit_count"] = len(audits)
            data["audits"] = audits[:15]
        if di is not None:
            data["decision_audit_count"] = len(di)
            data["decisions"] = di[:15]
        if timeline is not None:
            data["timeline"] = timeline[:20]
            data["timeline_count"] = len(timeline)
        if promo is not None:
            data["promotion"] = promo
        empty = (
            (audits is None or len(audits) == 0)
            and (di is None or len(di) == 0)
            and (timeline is None or len(timeline) == 0)
        )
        if empty and promo is None:
            return panel(
                "ai_governance_audit",
                "AI Governance & Audit",
                source="execution.audits|decision_intelligence|reliability",
                status="empty",
                message="No audit trail rows yet",
                data=data,
            )
        return panel(
            "ai_governance_audit",
            "AI Governance & Audit",
            source="execution.audits|decision_intelligence|reliability",
            data=data,
            message="Cross-source audit of recorded events only",
        )
