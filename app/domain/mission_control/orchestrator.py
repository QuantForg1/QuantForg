"""Mission Control orchestrator — executive aggregation of live feeds only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.mission_control.config import (
    DEFAULT_MC_CONFIG,
    MissionControlConfig,
)
from app.domain.mission_control.notes import OperatorNotesStore
from app.domain.mission_control.panel import PanelSnapshot, panel
from app.domain.mission_control.search import (
    SearchHit,
    search_desks,
    search_notes,
    search_timeline_rows,
)


@dataclass
class MissionFeeds:
    """Live production snapshots only. Missing feeds → unavailable/empty."""

    control_center: dict[str, Any] | None = None
    readiness: dict[str, Any] | None = None
    reliability: dict[str, Any] | None = None
    incidents: list[dict[str, Any]] | None = None
    timeline: list[dict[str, Any]] | None = None
    decision_intelligence: dict[str, Any] | None = None
    decision_history: list[dict[str, Any]] | None = None
    institutional_decision: dict[str, Any] | None = None
    ai_robot: dict[str, Any] | None = None
    market_intelligence: dict[str, Any] | None = None
    capital: dict[str, Any] | None = None
    positions: list[dict[str, Any]] | None = None
    xauusd: dict[str, Any] | None = None
    daily: dict[str, Any] | None = None


@dataclass
class MissionControlCenter:
    config: MissionControlConfig = field(default_factory=lambda: DEFAULT_MC_CONFIG)
    notes: OperatorNotesStore = field(default_factory=OperatorNotesStore)

    def __post_init__(self) -> None:
        self.notes.max_notes = self.config.max_notes

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "capabilities": {
                "executive_dashboard": True,
                "monitoring_duplicate": False,
                "fabricate_metrics": False,
                "force_execution": False,
                "bypass_risk": False,
                "bypass_safety": False,
                "operator_notes": True,
                "global_search": True,
                "emergency_deep_link": "/ops",
                "client_live_feeds": [
                    "capital_overview",
                    "live_positions",
                    "xauusd_watchlist",
                ],
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def add_note(
        self,
        text: str,
        *,
        operator: str = "operator",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        note = self.notes.add(text, operator=operator, tags=tags)
        return note.to_dict()

    def list_notes(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.notes.list(limit=limit)
        return {
            "status": "available" if rows else "empty",
            "source": "mission_control.operator_notes",
            "notes": [n.to_dict() for n in rows],
        }

    def search(
        self,
        query: str,
        *,
        timeline: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        q = query.strip()
        if not q:
            return {
                "query": "",
                "status": "empty",
                "hits": [],
                "message": "Enter a query",
            }
        note_hits = search_notes(self.notes.search(q, limit=10), q)
        desk_hits = search_desks(q, self.config)
        time_hits = search_timeline_rows(timeline or [], q)[:10]
        hits: list[SearchHit] = [*desk_hits, *note_hits, *time_hits]
        return {
            "query": q,
            "status": "available" if hits else "empty",
            "source": "mission_control.global_search",
            "hits": [h.to_dict() for h in hits],
            "message": "" if hits else "No live matches",
        }

    def build_dashboard(self, feeds: MissionFeeds) -> dict[str, Any]:
        panels = [
            self._executive(feeds),
            self._capital(feeds),
            self._risk(feeds),
            self._ai_decisions(feeds),
            self._positions(feeds),
            self._incidents(feeds),
            self._timeline(feeds),
            self._system_health(feeds),
            self._ai_health(feeds),
            self._emergency(feeds),
            self._xauusd(feeds),
            self._daily(feeds),
            self._notes_panel(),
            self._search_panel(),
            self._fab_panel(),
        ]
        return {
            "product": self.config.product,
            "version": self.config.version,
            "is_monitoring": False,
            "fabricates_metrics": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "panels": {p.panel_id: p.to_dict() for p in panels},
            "panel_order": [p.panel_id for p in panels],
            "deep_links": {
                "monitoring": "/monitoring",
                "ops": "/ops",
                "terminal": "/terminal",
                "risk": "/risk",
                "decision_intelligence": "/decision-intelligence",
            },
        }

    def _executive(self, feeds: MissionFeeds) -> PanelSnapshot:
        cc = feeds.control_center
        rd = feeds.readiness
        if not cc and not rd:
            return panel(
                "executive_status",
                "Executive Status",
                source="ite.ops.control_center",
                status="unavailable",
                message="Control center feed unavailable",
            )
        data: dict[str, Any] = {}
        if cc:
            data.update(
                {
                    "system_status": cc.get("system_status"),
                    "execution_mode": cc.get("execution_mode"),
                    "kill_switch": cc.get("kill_switch"),
                    "gateway_status": cc.get("gateway_status"),
                    "mt5_status": cc.get("mt5_status"),
                    "oms_orders_allowed": cc.get("oms_orders_allowed"),
                    "config_version": cc.get("config_version"),
                    "strategy_version": cc.get("strategy_version"),
                    "unacked_alerts": cc.get("unacked_alerts"),
                }
            )
        if rd:
            data["readiness"] = {
                k: rd.get(k)
                for k in (
                    "risk_status",
                    "promotion_status",
                    "health_score",
                    "current_mode",
                )
                if k in rd
            }
        return panel(
            "executive_status",
            "Executive Status",
            source="ite.ops.control_center",
            data=data,
        )

    def _capital(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.capital is None:
            return panel(
                "capital_overview",
                "Capital Overview",
                source="mt5.account|portfolio",
                status="unavailable",
                message="Awaiting live broker/portfolio feed",
            )
        cap = {k: v for k, v in feeds.capital.items() if v is not None}
        if not cap:
            return panel(
                "capital_overview",
                "Capital Overview",
                source="mt5.account|portfolio",
                status="empty",
                message="No capital fields reported",
            )
        return panel(
            "capital_overview",
            "Capital Overview",
            source="mt5.account|portfolio",
            data=cap,
        )

    def _risk(self, feeds: MissionFeeds) -> PanelSnapshot:
        cc = feeds.control_center or {}
        risk = cc.get("risk") if isinstance(cc.get("risk"), dict) else None
        if risk is None and feeds.readiness is None:
            return panel(
                "risk_radar",
                "Risk Radar",
                source="ite.ops.control_center.risk",
                status="unavailable",
                message="Risk feed unavailable",
            )
        data: dict[str, Any] = dict(risk or {})
        if feeds.readiness:
            data["risk_status"] = feeds.readiness.get("risk_status")
        data["kill_switch"] = cc.get("kill_switch")
        data["daily_loss_exceeded"] = (risk or {}).get("daily_loss_exceeded")
        return panel(
            "risk_radar",
            "Risk Radar",
            source="ite.ops.control_center.risk",
            data=data,
        )

    def _ai_decisions(self, feeds: MissionFeeds) -> PanelSnapshot:
        hist = feeds.decision_history
        if hist is None:
            return panel(
                "live_ai_decisions",
                "Live AI Decisions",
                source="decision_intelligence.history",
                status="unavailable",
                message="Decision history feed unavailable",
            )
        rows = hist[: self.config.max_decisions]
        if not rows:
            return panel(
                "live_ai_decisions",
                "Live AI Decisions",
                source="decision_intelligence.history",
                status="empty",
                message="No auditable decisions yet",
                data={"decisions": []},
            )
        return panel(
            "live_ai_decisions",
            "Live AI Decisions",
            source="decision_intelligence.history",
            data={"decisions": rows, "count": len(rows)},
        )

    def _positions(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.positions is None:
            return panel(
                "live_positions",
                "Live Positions",
                source="portfolio.positions",
                status="unavailable",
                message="Awaiting live positions feed",
            )
        rows = [p for p in feeds.positions if isinstance(p, dict)]
        if not rows:
            return panel(
                "live_positions",
                "Live Positions",
                source="portfolio.positions",
                status="empty",
                message="No open positions",
                data={"positions": [], "count": 0},
            )
        return panel(
            "live_positions",
            "Live Positions",
            source="portfolio.positions",
            data={"positions": rows, "count": len(rows)},
        )

    def _incidents(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.incidents is None and feeds.reliability is None:
            return panel(
                "incident_center",
                "Incident Center",
                source="ite.reliability.incidents",
                status="unavailable",
                message="Reliability feed unavailable",
            )
        rows = list(feeds.incidents or [])
        if not rows and isinstance(feeds.reliability, dict):
            active = feeds.reliability.get("active_incidents")
            if isinstance(active, list):
                rows = [r for r in active if isinstance(r, dict)]
        if not rows:
            return panel(
                "incident_center",
                "Incident Center",
                source="ite.reliability.incidents",
                status="empty",
                message="No open incidents",
                data={"incidents": [], "open_count": 0},
            )
        return panel(
            "incident_center",
            "Incident Center",
            source="ite.reliability.incidents",
            data={
                "incidents": rows[: self.config.max_incidents],
                "open_count": len(rows),
            },
        )

    def _timeline(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.timeline is None:
            return panel(
                "production_timeline",
                "Production Timeline",
                source="ite.reliability.timeline",
                status="unavailable",
                message="Timeline feed unavailable",
            )
        rows = [r for r in feeds.timeline if isinstance(r, dict)][
            : self.config.max_timeline
        ]
        if not rows:
            return panel(
                "production_timeline",
                "Production Timeline",
                source="ite.reliability.timeline",
                status="empty",
                message="No timeline events",
                data={"events": []},
            )
        return panel(
            "production_timeline",
            "Production Timeline",
            source="ite.reliability.timeline",
            data={"events": rows, "count": len(rows)},
        )

    def _system_health(self, feeds: MissionFeeds) -> PanelSnapshot:
        """Executive health posture — not Monitoring execution strip."""
        cc = feeds.control_center or {}
        health = cc.get("health") if isinstance(cc.get("health"), dict) else None
        rd = feeds.readiness or {}
        if health is None and not rd and not cc:
            return panel(
                "system_health",
                "System Health",
                source="ite.ops.control_center.health",
                status="unavailable",
                message="Health feed unavailable",
            )
        data: dict[str, Any] = {
            "gateway_status": cc.get("gateway_status"),
            "mt5_status": cc.get("mt5_status"),
            "system_status": cc.get("system_status"),
            "execution_mode": cc.get("execution_mode"),
        }
        if health:
            data["health"] = health
        if rd.get("health_score") is not None:
            data["health_score"] = rd.get("health_score")
        return panel(
            "system_health",
            "System Health",
            source="ite.ops.control_center.health",
            data=data,
            message="Executive posture — deep diagnostics on Monitoring",
        )

    def _ai_health(self, feeds: MissionFeeds) -> PanelSnapshot:
        modules = {
            "decision_intelligence": feeds.decision_intelligence,
            "institutional_decision": feeds.institutional_decision,
            "ai_robot": feeds.ai_robot,
            "market_intelligence": feeds.market_intelligence,
        }
        present = {k: v for k, v in modules.items() if isinstance(v, dict)}
        if not present:
            return panel(
                "ai_health",
                "AI Health",
                source="ai.*.status",
                status="unavailable",
                message="AI status feeds unavailable",
            )
        summary = {
            name: {
                "product": body.get("product") or body.get("version") or name,
                "ok": True,
                "keys": sorted(body.keys())[:8],
            }
            for name, body in present.items()
        }
        return panel(
            "ai_health",
            "AI Health",
            source="ai.*.status",
            data={"modules": summary, "module_count": len(summary)},
        )

    def _emergency(self, feeds: MissionFeeds) -> PanelSnapshot:
        cc = feeds.control_center
        if not cc:
            return panel(
                "emergency_panel",
                "Emergency Panel",
                source="ite.ops.control_center",
                status="unavailable",
                message="Emergency posture unavailable",
            )
        auto_raw = cc.get("auto_trading")
        auto = auto_raw if isinstance(auto_raw, dict) else {}
        data = {
            "kill_switch": cc.get("kill_switch"),
            "system_status": cc.get("system_status"),
            "oms_orders_allowed": cc.get("oms_orders_allowed"),
            "execution_mode": cc.get("execution_mode"),
            "auto_trading_status": auto.get("status"),
            "auto_trading_enabled": auto.get("enabled"),
            "actions_href": "/ops",
            "never_force_execution": True,
        }
        return panel(
            "emergency_panel",
            "Emergency Panel",
            source="ite.ops.control_center",
            data=data,
            message="Mutations only via Ops control — Mission Control is advisory",
        )

    def _xauusd(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.xauusd is None:
            return panel(
                "xauusd_watchlist",
                "XAUUSD Watchlist",
                source="mt5.ticks",
                status="unavailable",
                message="Awaiting live XAUUSD tick",
            )
        tick = {k: v for k, v in feeds.xauusd.items() if v is not None}
        if not tick:
            return panel(
                "xauusd_watchlist",
                "XAUUSD Watchlist",
                source="mt5.ticks",
                status="empty",
                message="No tick fields",
            )
        tick.setdefault("symbol", self.config.symbol)
        return panel(
            "xauusd_watchlist",
            "XAUUSD Watchlist",
            source="mt5.ticks",
            data=tick,
        )

    def _daily(self, feeds: MissionFeeds) -> PanelSnapshot:
        if feeds.daily is not None:
            daily = {k: v for k, v in feeds.daily.items() if v is not None}
            if daily:
                return panel(
                    "daily_summary",
                    "Daily Summary",
                    source="live.daily",
                    data=daily,
                )
        # Derive only from available live feeds — never invent P&L.
        derived: dict[str, Any] = {"derived": True}
        if feeds.decision_history is not None:
            decisions = feeds.decision_history
            counts: dict[str, int] = {}
            for row in decisions:
                d = str(row.get("decision") or "UNKNOWN")
                counts[d] = counts.get(d, 0) + 1
            derived["decision_counts"] = counts
            derived["decision_events"] = len(decisions)
        if feeds.incidents is not None:
            derived["open_incidents"] = len(feeds.incidents)
        elif isinstance(feeds.reliability, dict):
            err = feeds.reliability.get("errors")
            if isinstance(err, dict) and err.get("open_incidents") is not None:
                derived["open_incidents"] = err.get("open_incidents")
        if feeds.control_center:
            derived["execution_mode"] = feeds.control_center.get("execution_mode")
            derived["kill_switch"] = feeds.control_center.get("kill_switch")
        if len(derived) <= 1:
            return panel(
                "daily_summary",
                "Daily Summary",
                source="mission_control.derived",
                status="empty",
                message="No live daily inputs yet",
            )
        return panel(
            "daily_summary",
            "Daily Summary",
            source="mission_control.derived",
            data=derived,
            message="Derived from live feeds only — no fabricated P&L",
        )

    def _notes_panel(self) -> PanelSnapshot:
        rows = self.notes.list(limit=20)
        if not rows:
            return panel(
                "operator_notes",
                "Operator Notes",
                source="mission_control.operator_notes",
                status="empty",
                message="No operator notes",
                data={"notes": []},
            )
        return panel(
            "operator_notes",
            "Operator Notes",
            source="mission_control.operator_notes",
            data={"notes": [n.to_dict() for n in rows]},
        )

    def _search_panel(self) -> PanelSnapshot:
        return panel(
            "global_search",
            "Global Search",
            source="mission_control.global_search",
            data={"desks": list(self.config.desk_catalog)},
            message="Search desks, notes, and production timeline",
        )

    def _fab_panel(self) -> PanelSnapshot:
        return panel(
            "floating_action_bar",
            "Floating Action Bar",
            source="mission_control.fab",
            data={
                "actions": [
                    {"label": "Terminal", "href": "/terminal"},
                    {"label": "Ops", "href": "/ops"},
                    {"label": "Monitoring", "href": "/monitoring"},
                    {"label": "Risk", "href": "/risk"},
                    {"label": "Decision Center", "href": "/decision-intelligence"},
                    {"label": "Emergency", "href": "/ops", "tone": "danger"},
                ]
            },
        )
