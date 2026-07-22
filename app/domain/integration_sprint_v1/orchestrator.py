"""Integration Sprint V1 orchestrator — read-only data bus + durable store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.integration_sprint_v1.config import (
    DEFAULT_INTEGRATION_CONFIG,
    FEED_NAMES,
    IntegrationSprintConfig,
)
from app.domain.integration_sprint_v1.durable_store import (
    NAMESPACES,
    DurableResearchStore,
)
from app.domain.integration_sprint_v1.feeds import IntegrationFeeds
from app.domain.integration_sprint_v1.hydrators import (
    hydrate_ivp,
    hydrate_llp,
    hydrate_prc,
    hydrate_rmip,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class IntegrationSprintV1:
    config: IntegrationSprintConfig = field(
        default_factory=lambda: DEFAULT_INTEGRATION_CONFIG
    )
    feeds: IntegrationFeeds | None = None

    def __post_init__(self) -> None:
        if self.feeds is None:
            self.feeds = IntegrationFeeds(self.config)

    def status(self) -> dict[str, object]:
        assert self.feeds is not None
        return {
            **self.config.to_dict(),
            "modules": list(FEED_NAMES),
            "durable_namespaces": list(NAMESPACES),
            "capabilities": {
                "xauusd_only": True,
                "read_only": True,
                "never_order_send": True,
                "never_modify_auto_trading": True,
                "never_modify_execution_pipeline": True,
                "never_modify_decision_engine": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_fabricate_feeds": True,
                "preserves_existing_apis": True,
                "symbol": GOLD_SYMBOL,
            },
            "store_health": self.feeds.store.health(),
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        assert self.feeds is not None
        self.feeds.config = self.config
        return self.config.to_dict()

    def bus_snapshot(self) -> dict[str, Any]:
        assert self.feeds is not None
        return self.feeds.unified_data_bus()

    def feed(self, name: str) -> dict[str, Any]:
        assert self.feeds is not None
        mapping = {
            "mt5_trade_feed": self.feeds.mt5_trade_feed,
            "mt5_position_feed": self.feeds.mt5_position_feed,
            "mt5_market_data_feed": self.feeds.mt5_market_data_feed,
            "broker_account_feed": self.feeds.broker_account_feed,
            "execution_journal_feed": self.feeds.execution_journal_feed,
            "analytics_feed": self.feeds.analytics_feed,
            "historical_data_warehouse": self.feeds.historical_data_warehouse,
            "economic_calendar_provider": self.feeds.economic_calendar_provider,
            "durable_storage": self.feeds.durable_storage_feed,
        }
        fn = mapping.get(name)
        if fn is None:
            return {
                "feed": name,
                "available": False,
                "missing_reason": "MISSING DATA",
                "health": {"status": "missing", "message": "Unknown feed"},
            }
        return fn().to_dict()

    def hydrate(
        self, target: str, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self.feeds is not None
        target = target.strip().lower()
        if target == "ivp":
            body = hydrate_ivp(self.feeds, overrides)
        elif target == "llp":
            body = hydrate_llp(self.feeds, overrides)
        elif target == "rmip":
            body = hydrate_rmip(self.feeds, overrides)
        elif target == "prc":
            body = hydrate_prc(self.feeds, overrides)
        else:
            return {
                "status": "error",
                "message": f"Unknown target {target}",
                "allowed": ["ivp", "llp", "rmip", "prc"],
            }
        return {
            "status": "available",
            "target": target,
            "evaluate_body": body,
            "read_only": True,
            "preserves_existing_api": True,
            "note": "POST this body to the existing /evaluate endpoint",
        }

    def storage_append(
        self, namespace: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.feeds is not None
        return self.feeds.store.append(namespace, record)

    def storage_list(
        self, namespace: str, *, limit: int = 50
    ) -> dict[str, Any]:
        assert self.feeds is not None
        return self.feeds.store.list(namespace, limit=limit)

    def ingest_warehouse(
        self, bars: list[dict[str, Any]]
    ) -> dict[str, Any]:
        assert self.feeds is not None
        count = self.feeds.ingest_warehouse_bars(bars)
        return {
            "status": "available" if count else "MISSING DATA",
            "bar_count": count,
            "invented": False,
        }


def build_feeds_from_runtime(
    config: IntegrationSprintConfig | None = None,
) -> IntegrationFeeds:
    """Best-effort wiring to container — never fails hard; reports MISSING."""
    cfg = config or DEFAULT_INTEGRATION_CONFIG
    mt5 = None
    journal = None
    calendar = None
    try:
        from core.di.container import get_container

        container = get_container()
        mt5 = getattr(container, "mt5_adapter", None)
    except Exception:
        mt5 = None
    try:
        from app.domain.execution_engine.journal import ExecutionJournalStore

        journal = ExecutionJournalStore()
    except Exception:
        journal = None
    try:
        from app.infrastructure.news.configured_feed import (
            ConfiguredHttpEconomicCalendar,
            NullEconomicCalendar,
        )
        from core.config.settings import get_settings

        settings = get_settings()
        url = str(
            getattr(settings, "economic_calendar_feed_url", "") or ""
        )
        calendar = (
            ConfiguredHttpEconomicCalendar(url=url)
            if url.strip()
            else NullEconomicCalendar()
        )
    except Exception:
        calendar = None

    return IntegrationFeeds(
        cfg,
        mt5_adapter=mt5,
        execution_journal=journal,
        economic_calendar=calendar,
        durable_store=DurableResearchStore(
            max_per_namespace=cfg.max_durable_per_namespace
        ),
    )
