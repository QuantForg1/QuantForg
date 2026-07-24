"""QEM platform — read-only event mesh backbone."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_event_mesh.analytics import (
    build_timeline,
    correlation_view,
    derive_events,
    ordering_consistency_check,
    replay_consistency_check,
    replay_stream,
    route_subscribers,
    search_events,
)
from app.domain.quantforg_event_mesh.gather import gather_event_sources
from app.domain.quantforg_event_mesh.models import (
    DEFAULT_SUBSCRIBERS,
    EVENT_SOURCES,
    EVENT_TYPES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_event_mesh.store import QemStore


class QuantForgEventMesh:
    def __init__(self, store: QemStore | None = None) -> None:
        self.store = store or QemStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_event_sources()
        derived = derive_events(ctx)
        appended = 0
        if persist:
            if not self.store.list_subscribers():
                self.store.set_subscribers([dict(s) for s in DEFAULT_SUBSCRIBERS])
            for ev in derived:
                if self.store.append_event(ev) is not None:
                    appended += 1
        events = self.store.list_events(limit=500) if persist else list(derived)
        # Prefer store chronology; merge newly derived if not persisting
        if not persist:
            events = sorted(derived, key=lambda e: str(e.get("timestamp") or ""))
        routing = route_subscribers(events, self.store.list_subscribers() or None)
        timeline = build_timeline(events, limit=100)
        correlations = correlation_view(events)
        ordering = ordering_consistency_check(events)
        replay = replay_stream(events, limit=100)
        replay_check = replay_consistency_check(events, replay.get("stream") or [])
        stats = {
            "event_count": len(events),
            "derived_this_run": len(derived),
            "appended_this_run": appended,
            "source_count": ctx.get("source_count"),
            "subscriber_count": len(routing.get("subscribers") or []),
            "event_types": list(EVENT_TYPES),
            "event_sources": list(EVENT_SOURCES),
        }
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_event_mesh",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "stats": stats,
            "events": events[-100:],
            "timeline": timeline,
            "routing": routing,
            "correlations": correlations,
            "ordering_consistency": ordering,
            "replay": replay,
            "replay_consistency": replay_check,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "never_modifies_risk": True,
            "never_approves_releases": True,
            "events_immutable": True,
            "event_distribution_read_only": True,
        }
        if persist:
            self.store.save_snapshot(pack)
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "event_explorer": {
                "events": pack["events"],
                "stats": pack["stats"],
            },
            "live_event_stream": {
                "stream": (pack.get("replay") or {}).get("stream") or [],
                "note": "Live observational stream from immutable store",
            },
            "timeline": pack["timeline"],
            "correlation_viewer": pack["correlations"],
            "subscribers": (pack.get("routing") or {}).get("subscribers") or [],
        }
        return pack

    def search(
        self,
        *,
        strategy_id: str | None = None,
        release_id: str | None = None,
        experiment_id: str | None = None,
        correlation_id: str | None = None,
        category: str | None = None,
        event_type: str | None = None,
        q: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=1000)
        return search_events(
            events,
            strategy_id=strategy_id,
            release_id=release_id,
            experiment_id=experiment_id,
            correlation_id=correlation_id,
            category=category,
            event_type=event_type,
            q=q,
            limit=limit,
        )

    def stream(self, *, limit: int = 100) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=limit)
        ordered = sorted(events, key=lambda e: str(e.get("timestamp") or ""))
        return {
            "stream": ordered[-limit:],
            "count": len(ordered[-limit:]),
            "live": True,
            "immutable": True,
            "read_only": True,
            "never_modifies_production": True,
        }

    def timeline(self, *, limit: int = 100) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=500)
        return {
            "timeline": build_timeline(events, limit=limit),
            "read_only": True,
        }

    def correlation(self, correlation_id: str | None = None) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=1000)
        return correlation_view(events, correlation_id=correlation_id)

    def replay(
        self,
        *,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=1000)
        result = replay_stream(events, from_ts=from_ts, to_ts=to_ts, limit=limit)
        result["replay_consistency"] = replay_consistency_check(
            events, result.get("stream") or []
        )
        return result

    def subscribers(self) -> dict[str, Any]:
        self.run(persist=True)
        events = self.store.list_events(limit=200)
        return route_subscribers(events, self.store.list_subscribers() or None)
