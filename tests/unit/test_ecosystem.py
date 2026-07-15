"""Unit tests for Trading Ecosystem — no invented market data."""

from __future__ import annotations

from uuid import uuid4

from app.domain.ecosystem.coach import coach_from_trades
from app.domain.ecosystem.reports import build_period_report
from app.domain.ecosystem.store import EcosystemStore, get_ecosystem_store


def test_journal_search_and_stats() -> None:
    store = EcosystemStore()
    uid = uuid4()
    store.upsert_journal(
        uid,
        {
            "symbol": "EURUSD",
            "emotion": "focused",
            "lessons_learned": "Wait for pullback",
            "tags": ["london", "paper"],
            "decision_engine_score": 62,
        },
    )
    found = store.search_journal(uid, query="pullback")
    assert len(found) == 1
    stats = store.journal_stats(uid)
    assert stats["status"] == "available"
    assert stats["count"] == 1


def test_playbook_watchlist_workspace() -> None:
    store = EcosystemStore()
    uid = uuid4()
    pb = store.save_playbook(
        uid,
        {
            "name": "NY",
            "rules": ["R1"],
            "checklist": ["C1"],
            "psychology": ["P1"],
            "risk_rules": ["Risk 0.5%"],
            "sessions": ["NY"],
            "markets": ["NAS100"],
        },
    )
    assert pb["id"]
    wl = store.save_watchlist(
        uid, {"name": "Fav", "symbols": ["EURUSD"], "favorites": ["EURUSD"]}
    )
    assert wl["cloud_synced"] is True
    ws = store.save_workspace(
        uid, {"name": "Desk", "panels": ["chart"], "widgets": ["journal"]}
    )
    assert ws["never_modifies_terminal_defaults"] is True


def test_coach_advisory_flags() -> None:
    empty = coach_from_trades([])
    assert empty["status"] == "unavailable"
    assert empty["never_auto_submits"] is True

    review = coach_from_trades(
        [
            {
                "pnl": 10,
                "emotion": "revenge",
                "lessons_learned": "",
                "decision_engine_score": None,
                "tags": ["london"],
            },
            {
                "pnl": -5,
                "emotion": "focused",
                "lessons_learned": "Size smaller",
                "decision_engine_score": 55,
                "tags": ["ny"],
            },
        ]
        * 20
    )
    assert review["status"] == "available"
    assert review["never_bypasses_decision_engine"] is True
    assert review["common_mistakes"]


def test_cloud_sync_roundtrip() -> None:
    store = EcosystemStore()
    uid = uuid4()
    store.upsert_journal(uid, {"symbol": "XAUUSD", "tags": ["gold"]})
    store.save_playbook(uid, {"name": "Gold", "rules": ["ATR stop"]})
    bundle = store.export_sync_bundle(uid)
    uid2 = uuid4()
    result = store.import_sync_bundle(uid2, bundle)
    assert result["never_submits_orders"] is True
    assert store.list_journal(uid2)
    assert store.list_playbooks(uid2)


def test_report_periods() -> None:
    report = build_period_report(
        period="monthly",
        journal_stats={"status": "available", "count": 2},
        paper={"status": "available"},
        coach={"status": "available"},
        preferences={"timezone": "UTC"},
    )
    assert report["period"] == "monthly"
    assert report["advisory_only"] is True


def test_singleton_store() -> None:
    assert get_ecosystem_store() is get_ecosystem_store()


def test_alerts_and_learning() -> None:
    store = EcosystemStore()
    uid = uuid4()
    store.add_alert(
        uid, {"category": "risk", "title": "Heat", "message": "Reduce size"}
    )
    assert store.list_alerts(uid)
    prog = store.complete_lesson(uid, "guide-paper-first")
    assert "guide-paper-first" in prog["completed"]
    learning = store.learning_progress(uid)
    assert learning["catalog"]
