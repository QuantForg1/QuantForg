"""Trading Ecosystem service — workflow hub, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.decision_engine.paper_tracker import get_paper_tracker
from app.domain.ecosystem import (
    build_period_report,
    coach_from_trades,
    get_ecosystem_store,
)
from app.infrastructure.intelligence.runtime import TtlCache
from core.config.settings import get_settings

_HUB_CACHE = TtlCache(ttl_seconds=20.0, max_items=64)


def _security() -> dict[str, Any]:
    settings = get_settings()
    return {
        "advisory_only": True,
        "autonomous_trading": False,
        "never_submits_orders": True,
        "never_bypasses_execution_enabled": True,
        "never_bypasses_decision_engine": True,
        "never_modifies_broker_state": True,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        "promises_profit": False,
        "decision_engine_gatekeeper": True,
    }


@dataclass(frozen=True, slots=True)
class EcosystemService:
    """Personal trading workflow OS — advisory ecosystem only."""

    async def hub(self, *, user_id: UUID) -> dict[str, Any]:
        cache_key = f"eco:hub:{user_id}"
        cached = _HUB_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        store = get_ecosystem_store()
        journal = store.list_journal(user_id, limit=5)
        stats = store.journal_stats(user_id)
        payload = {
            "status": "available",
            "module": "ecosystem",
            "version": "1.0",
            "modules": [
                "trading_journal",
                "playbooks",
                "performance_coach",
                "watchlists",
                "workspaces",
                "notifications",
                "learning_center",
                "report_center",
                "settings",
                "cloud_sync",
            ],
            "preview": {
                "journal_count": stats.get("count", 0),
                "playbooks": len(store.list_playbooks(user_id)),
                "watchlists": len(store.list_watchlists(user_id)),
                "workspaces": len(store.list_workspaces(user_id)),
                "unread_alerts": sum(
                    1 for a in store.list_alerts(user_id) if not a.get("read")
                ),
                "recent_journal": journal,
            },
            "links": {
                "platform_notifications": "/notifications",
                "platform_settings": "/settings",
                "decision_engine": "/decision-engine",
                "research_lab": "/research-lab",
            },
            "data_policy": {
                "mock": False,
                "sources": [
                    "ecosystem_store",
                    "decision_engine_paper_tracker",
                    "user_journal",
                ],
            },
            **_security(),
        }
        _HUB_CACHE.set(cache_key, payload)
        return payload

    def journal_list(
        self, *, user_id: UUID, query: str = "", tag: str | None = None
    ) -> dict[str, Any]:
        store = get_ecosystem_store()
        items = (
            store.search_journal(user_id, query=query, tag=tag)
            if query or tag
            else store.list_journal(user_id)
        )
        return {
            "status": "available",
            "items": items,
            "stats": store.journal_stats(user_id),
            **_security(),
        }

    def journal_upsert(self, *, user_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        store = get_ecosystem_store()
        # Auto-enrich from DE paper when trade/signal id present
        signal_id = body.get("decision_signal_id")
        if signal_id and body.get("decision_engine_score") is None:
            for row in get_paper_tracker().list_for_user(user_id, limit=200):
                if str(row.get("id")) == str(signal_id) or str(
                    row.get("signal_id")
                ) == str(signal_id):
                    body = {
                        **body,
                        "decision_engine_score": row.get("trade_score"),
                        "decision": row.get("decision"),
                        "market_context": body.get("market_context")
                        or {
                            "symbol": row.get("symbol"),
                            "mode": row.get("mode"),
                        },
                    }
                    break
        saved = store.upsert_journal(user_id, body, entry_id=body.get("id"))
        return {"status": "available", "entry": saved, **_security()}

    def journal_ingest_paper(self, *, user_id: UUID) -> dict[str, Any]:
        """Create journal stubs from DE paper tracker — no fabricated fills."""
        store = get_ecosystem_store()
        existing_ids = {
            str(e.get("source_id"))
            for e in store.list_journal(user_id, limit=500)
            if e.get("source_id")
        }
        created = 0
        for row in get_paper_tracker().list_for_user(user_id, limit=100):
            sid = str(row.get("id") or row.get("signal_id") or "")
            if not sid or sid in existing_ids:
                continue
            if row.get("decision") != "TRADE_IDEA":
                continue
            store.upsert_journal(
                user_id,
                {
                    "source": "decision_engine_paper",
                    "source_id": sid,
                    "symbol": row.get("symbol"),
                    "decision": row.get("decision"),
                    "decision_engine_score": row.get("trade_score"),
                    "market_context": {
                        "mode": row.get("mode"),
                        "created_at": row.get("created_at"),
                    },
                    "risk": {"note": "Paper mode — advisory sizing only"},
                    "screenshot_ref": None,
                    "ai_review": None,
                    "emotion_notes": "",
                    "emotion": "unspecified",
                    "lessons_learned": "",
                    "tags": ["paper", "auto-ingest"],
                    "pnl": row.get("simulated_pnl"),
                },
            )
            created += 1
        return {
            "status": "available",
            "created": created,
            "note": "Stubs only — attach emotion/lessons manually",
            **_security(),
        }

    def playbooks(self, *, user_id: UUID) -> dict[str, Any]:
        return {
            "status": "available",
            "items": get_ecosystem_store().list_playbooks(user_id),
            **_security(),
        }

    def playbook_save(self, *, user_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        saved = get_ecosystem_store().save_playbook(
            user_id, body, playbook_id=body.get("id")
        )
        return {"status": "available", "playbook": saved, **_security()}

    def coach(self, *, user_id: UUID) -> dict[str, Any]:
        store = get_ecosystem_store()
        journal = store.list_journal(user_id, limit=100)
        # Merge lightweight paper idea rows if journal thin
        if len(journal) < 20:
            for row in get_paper_tracker().list_for_user(user_id, limit=100):
                if row.get("decision") != "TRADE_IDEA":
                    continue
                journal.append(
                    {
                        "pnl": row.get("simulated_pnl"),
                        "emotion": "unspecified",
                        "lessons_learned": "",
                        "decision_engine_score": row.get("trade_score"),
                        "tags": ["paper"],
                    }
                )
        review = coach_from_trades(journal, limit=100)
        return {**review, **_security()}

    def watchlists(self, *, user_id: UUID) -> dict[str, Any]:
        return {
            "status": "available",
            "items": get_ecosystem_store().list_watchlists(user_id),
            **_security(),
        }

    def watchlist_save(self, *, user_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        saved = get_ecosystem_store().save_watchlist(
            user_id, body, watchlist_id=body.get("id")
        )
        return {"status": "available", "watchlist": saved, **_security()}

    def workspaces(self, *, user_id: UUID) -> dict[str, Any]:
        return {
            "status": "available",
            "items": get_ecosystem_store().list_workspaces(user_id),
            **_security(),
            "note": "Saved layouts are independent of Trading Terminal defaults",
        }

    def workspace_save(self, *, user_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        saved = get_ecosystem_store().save_workspace(
            user_id, body, workspace_id=body.get("id")
        )
        return {"status": "available", "workspace": saved, **_security()}

    def alerts(self, *, user_id: UUID) -> dict[str, Any]:
        items = get_ecosystem_store().list_alerts(user_id)
        return {
            "status": "available",
            "items": items,
            "categories": [
                "price",
                "risk",
                "research",
                "paper",
                "decision",
            ],
            "platform_inbox": "/notifications",
            **_security(),
        }

    def alert_create(self, *, user_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        saved = get_ecosystem_store().add_alert(user_id, body)
        return {"status": "available", "alert": saved, **_security()}

    def alert_read(self, *, user_id: UUID, alert_id: str) -> dict[str, Any]:
        row = get_ecosystem_store().mark_alert_read(user_id, alert_id)
        if not row:
            return {"status": "unavailable", "reason": "Alert not found", **_security()}
        return {"status": "available", "alert": row, **_security()}

    def learning(self, *, user_id: UUID) -> dict[str, Any]:
        return {
            "status": "available",
            **get_ecosystem_store().learning_progress(user_id),
            **_security(),
        }

    def learning_complete(self, *, user_id: UUID, lesson_id: str) -> dict[str, Any]:
        prog = get_ecosystem_store().complete_lesson(user_id, lesson_id)
        return {"status": "available", "progress": prog, **_security()}

    def report(self, *, user_id: UUID, period: str = "weekly") -> dict[str, Any]:
        store = get_ecosystem_store()
        paper = get_paper_tracker().reports(user_id)
        coach = self.coach(user_id=user_id)
        report = build_period_report(
            period=period,
            journal_stats=store.journal_stats(user_id),
            paper=paper,
            coach=coach,
            preferences=store.get_preferences(user_id),
        )
        return {**report, **_security()}

    def preferences_get(self, *, user_id: UUID) -> dict[str, Any]:
        return {
            "status": "available",
            "preferences": get_ecosystem_store().get_preferences(user_id),
            "platform_settings": "/settings",
            **_security(),
        }

    def preferences_set(
        self, *, user_id: UUID, updates: dict[str, Any]
    ) -> dict[str, Any]:
        prefs = get_ecosystem_store().set_preferences(user_id, updates)
        return {"status": "available", "preferences": prefs, **_security()}

    def sync_export(self, *, user_id: UUID) -> dict[str, Any]:
        bundle = get_ecosystem_store().export_sync_bundle(user_id)
        return {"status": "available", "bundle": bundle, **_security()}

    def sync_import(self, *, user_id: UUID, bundle: dict[str, Any]) -> dict[str, Any]:
        result = get_ecosystem_store().import_sync_bundle(user_id, bundle)
        return {**result, **_security()}

    def sync_status(self, *, user_id: UUID) -> dict[str, Any]:
        return {**get_ecosystem_store().sync_status(user_id), **_security()}
