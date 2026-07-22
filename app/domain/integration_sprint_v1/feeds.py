"""Read-only production feeds — never invent; report MISSING DATA when unavailable."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.domain.integration_sprint_v1.config import (
    MISSING,
    IntegrationSprintConfig,
)
from app.domain.integration_sprint_v1.durable_store import DurableResearchStore
from app.domain.integration_sprint_v1.types import FeedHealth, FeedSnapshot
from app.domain.trading.gold_only import GOLD_SYMBOL


def _now() -> datetime:
    return datetime.now(UTC)


def _missing_health(feed: str, message: str) -> FeedHealth:
    return FeedHealth(
        feed=feed,
        status="missing",
        latency_ms=None,
        freshness_seconds=None,
        synchronized=None,
        message=message or MISSING,
        details={"verdict": MISSING},
    )


def _timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    t0 = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - t0) * 1000.0


def _safe_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        out: dict[str, Any] = {}
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            if hasattr(v, "__dict__") and not isinstance(
                v, (str, int, float, bool, type(None))
            ):
                out[k] = str(v)
            else:
                try:
                    out[k] = v if _jsonable(v) else str(v)
                except Exception:
                    out[k] = str(v)
        return out
    return {"value": str(obj)}


def _jsonable(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool, type(None), list, dict))


class IntegrationFeeds:
    """Collects read-only snapshots from MT5 / journal / calendar / warehouse."""

    def __init__(
        self,
        config: IntegrationSprintConfig,
        *,
        mt5_adapter: Any | None = None,
        execution_journal: Any | None = None,
        economic_calendar: Any | None = None,
        durable_store: DurableResearchStore | None = None,
        warehouse_bars: list[dict[str, Any]] | None = None,
    ) -> None:
        self.config = config
        self.mt5 = mt5_adapter
        self.journal = execution_journal
        self.calendar = economic_calendar
        self.store = durable_store or DurableResearchStore(
            max_per_namespace=config.max_durable_per_namespace
        )
        self._warehouse: list[dict[str, Any]] = list(warehouse_bars or [])
        self._last_bus: dict[str, FeedSnapshot] = {}

    # ----- individual feeds -------------------------------------------------

    def mt5_trade_feed(self) -> FeedSnapshot:
        name = "mt5_trade_feed"
        if self.mt5 is None:
            h = _missing_health(name, "MT5 adapter unavailable")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> list[dict[str, Any]]:
                from datetime import timedelta

                date_to = _now()
                date_from = date_to - timedelta(days=30)
                deals = self.mt5.history_deals(
                    date_from=date_from, date_to=date_to
                )
                rows = []
                for d in list(deals or [])[: self.config.max_deals]:
                    rows.append(_safe_dict(d))
                return rows

            rows, latency = _timed(_pull)
            if not rows:
                h = FeedHealth(
                    feed=name,
                    status="missing",
                    latency_ms=round(latency, 2),
                    freshness_seconds=None,
                    synchronized=True,
                    message=MISSING,
                    details={"deal_count": 0},
                )
                return FeedSnapshot(
                    name, False, [], h, missing_reason=MISSING
                )
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message=f"{len(rows)} deal(s)",
                details={"deal_count": len(rows)},
            )
            return FeedSnapshot(name, True, rows, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
                details={"verdict": MISSING},
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def mt5_position_feed(self) -> FeedSnapshot:
        name = "mt5_position_feed"
        if self.mt5 is None:
            h = _missing_health(name, "MT5 adapter unavailable")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> list[dict[str, Any]]:
                return [
                    _safe_dict(p)
                    for p in list(self.mt5.list_positions() or [])
                ]

            rows, latency = _timed(_pull)
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message=f"{len(rows)} position(s)",
                details={"position_count": len(rows)},
            )
            return FeedSnapshot(name, True, rows, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def mt5_market_data_feed(self) -> FeedSnapshot:
        name = "mt5_market_data_feed"
        if self.mt5 is None:
            h = _missing_health(name, "MT5 adapter unavailable")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> dict[str, Any]:
                tick = self.mt5.latest_tick(GOLD_SYMBOL)
                return {
                    "symbol": GOLD_SYMBOL,
                    "tick": _safe_dict(tick),
                    "as_of": _now().isoformat(),
                }

            payload, latency = _timed(_pull)
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message=f"{GOLD_SYMBOL} tick",
            )
            return FeedSnapshot(name, True, payload, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def broker_account_feed(self) -> FeedSnapshot:
        name = "broker_account_feed"
        if self.mt5 is None:
            h = _missing_health(name, "MT5 adapter unavailable")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> dict[str, Any]:
                info = self.mt5.account_info()
                health: dict[str, Any] | None
                try:
                    health = _safe_dict(self.mt5.health())
                except Exception:
                    health = None
                return {
                    "account": _safe_dict(info),
                    "mt5_health": health,
                    "as_of": _now().isoformat(),
                }

            payload, latency = _timed(_pull)
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message="account snapshot",
            )
            return FeedSnapshot(name, True, payload, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def execution_journal_feed(self) -> FeedSnapshot:
        name = "execution_journal_feed"
        if self.journal is None:
            h = _missing_health(name, "Execution journal unavailable")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> list[dict[str, Any]]:
                if hasattr(self.journal, "all_recent"):
                    items = self.journal.all_recent(
                        limit=self.config.max_journal
                    )
                elif hasattr(self.journal, "list_for_user"):
                    items = []
                else:
                    items = []
                rows = []
                for item in list(items or [])[: self.config.max_journal]:
                    if isinstance(item, dict):
                        rows.append(item)
                    else:
                        rows.append(_safe_dict(item))
                return rows

            rows, latency = _timed(_pull)
            if not rows:
                h = FeedHealth(
                    feed=name,
                    status="missing",
                    latency_ms=round(latency, 2),
                    freshness_seconds=None,
                    synchronized=True,
                    message=MISSING,
                )
                return FeedSnapshot(
                    name, False, [], h, missing_reason=MISSING
                )
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message=f"{len(rows)} journal entr(y/ies)",
            )
            return FeedSnapshot(name, True, rows, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def analytics_feed(self) -> FeedSnapshot:
        """Derived analytics from available trade/journal feeds — never invents."""
        name = "analytics_feed"
        trades = self.mt5_trade_feed()
        journal = self.execution_journal_feed()
        if not trades.available and not journal.available:
            h = _missing_health(name, "No trade or journal evidence")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        payload = {
            "trade_count": (
                len(trades.payload)
                if isinstance(trades.payload, list)
                else 0
            ),
            "journal_count": (
                len(journal.payload)
                if isinstance(journal.payload, list)
                else 0
            ),
            "symbol": GOLD_SYMBOL,
            "as_of": _now().isoformat(),
            "source_feeds": [
                n
                for n, snap in (
                    ("mt5_trade_feed", trades),
                    ("execution_journal_feed", journal),
                )
                if snap.available
            ],
        }
        h = FeedHealth(
            feed=name,
            status="healthy",
            latency_ms=0.0,
            freshness_seconds=0.0,
            synchronized=True,
            message="analytics derived from available feeds",
        )
        return FeedSnapshot(name, True, payload, h)

    def historical_data_warehouse(self) -> FeedSnapshot:
        name = "historical_data_warehouse"
        # Prefer in-memory warehouse bars; optionally backfill from MT5 candles
        bars = list(self._warehouse)
        mt5_error: str | None = None
        if not bars and self.mt5 is not None:
            try:
                from app.domain.market_data.timeframe import Timeframe

                rates = self.mt5.copy_rates_from_pos(
                    GOLD_SYMBOL,
                    Timeframe.M5,
                    0,
                    min(100, self.config.max_warehouse_bars),
                )
                for r in list(rates or []):
                    bars.append(_safe_dict(r))
                if bars:
                    self._warehouse = bars[: self.config.max_warehouse_bars]
            except Exception as exc:
                bars = []
                mt5_error = str(exc)[:200]

        if not bars:
            if mt5_error:
                h = FeedHealth(
                    feed=name,
                    status="error",
                    latency_ms=0.0,
                    freshness_seconds=-1.0,
                    synchronized=False,
                    message=f"warehouse MT5 backfill failed: {mt5_error}",
                )
                return FeedSnapshot(
                    name, False, None, h, missing_reason="ERROR"
                )
            h = _missing_health(name, "No historical bars warehoused")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        h = FeedHealth(
            feed=name,
            status="healthy",
            latency_ms=0.0,
            freshness_seconds=0.0,
            synchronized=True,
            message=f"{len(bars)} bar(s)",
            details={"bar_count": len(bars)},
        )
        return FeedSnapshot(
            name, True, bars[: self.config.max_warehouse_bars], h
        )

    def ingest_warehouse_bars(self, bars: list[dict[str, Any]]) -> int:
        """Operator/MT5 ingest — never fabricates OHLC."""
        clean = [b for b in bars if isinstance(b, dict)]
        self._warehouse = (clean + self._warehouse)[
            : self.config.max_warehouse_bars
        ]
        return len(self._warehouse)

    def economic_calendar_provider(self) -> FeedSnapshot:
        name = "economic_calendar_provider"
        if self.calendar is None:
            h = _missing_health(name, "Economic calendar feed not configured")
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )
        try:

            def _pull() -> list[dict[str, Any]]:
                events = self.calendar.list_events(
                    limit=self.config.max_calendar_events
                )
                rows = []
                for e in list(events or []):
                    if hasattr(e, "title"):
                        rows.append(
                            {
                                "name": e.title,
                                "currency": getattr(e, "country", None),
                                "importance": getattr(e, "impact", None),
                                "scheduled_time": getattr(
                                    e, "scheduled_at", None
                                ),
                                "previous": getattr(e, "previous", None)
                                or None,
                                "forecast": getattr(e, "forecast", None)
                                or None,
                                "actual": getattr(e, "actual", None) or None,
                                # empty strings → None (never invent)
                            }
                        )
                        for k in ("previous", "forecast", "actual"):
                            if rows[-1][k] == "":
                                rows[-1][k] = None
                    elif isinstance(e, dict):
                        rows.append(e)
                return rows

            rows, latency = _timed(_pull)
            if not rows:
                h = FeedHealth(
                    feed=name,
                    status="missing",
                    latency_ms=round(latency, 2),
                    freshness_seconds=None,
                    synchronized=True,
                    message=MISSING,
                )
                return FeedSnapshot(
                    name, False, [], h, missing_reason=MISSING
                )
            h = FeedHealth(
                feed=name,
                status="healthy",
                latency_ms=round(latency, 2),
                freshness_seconds=0.0,
                synchronized=True,
                message=f"{len(rows)} event(s)",
            )
            return FeedSnapshot(name, True, rows, h)
        except Exception as exc:
            h = FeedHealth(
                feed=name,
                status="error",
                latency_ms=None,
                freshness_seconds=None,
                synchronized=False,
                message=str(exc) or MISSING,
            )
            return FeedSnapshot(
                name, False, None, h, missing_reason=MISSING
            )

    def durable_storage_feed(self) -> FeedSnapshot:
        name = "durable_storage"
        health = self.store.health()
        h = FeedHealth(
            feed=name,
            status="healthy",
            latency_ms=0.0,
            freshness_seconds=0.0,
            synchronized=True,
            message="append-only research store",
            details=health,
        )
        return FeedSnapshot(name, True, health, h)

    def unified_data_bus(self) -> dict[str, Any]:
        """Snapshot all enabled feeds into one read-only bus view."""
        flags = self.config.feature_flags
        collectors = {
            "mt5_trade_feed": self.mt5_trade_feed,
            "mt5_position_feed": self.mt5_position_feed,
            "mt5_market_data_feed": self.mt5_market_data_feed,
            "broker_account_feed": self.broker_account_feed,
            "execution_journal_feed": self.execution_journal_feed,
            "analytics_feed": self.analytics_feed,
            "historical_data_warehouse": self.historical_data_warehouse,
            "economic_calendar_provider": self.economic_calendar_provider,
            "durable_storage": self.durable_storage_feed,
        }
        snapshots: dict[str, FeedSnapshot] = {}
        for name, fn in collectors.items():
            if flags.get(name, True):
                snapshots[name] = fn()
        self._last_bus = snapshots

        health_rows = [s.health.to_dict() for s in snapshots.values()]
        connected = [n for n, s in snapshots.items() if s.available]
        missing = [
            n
            for n, s in snapshots.items()
            if not s.available
        ]
        return {
            "as_of": _now().isoformat(),
            "symbol": GOLD_SYMBOL,
            "feeds": {k: v.to_dict() for k, v in snapshots.items()},
            "health": health_rows,
            "connected_feeds": connected,
            "missing_feeds": missing,
            "health_summary": {
                "healthy": sum(
                    1 for h in health_rows if h["status"] == "healthy"
                ),
                "missing": sum(
                    1 for h in health_rows if h["status"] == "missing"
                ),
                "error": sum(
                    1 for h in health_rows if h["status"] == "error"
                ),
                "degraded": sum(
                    1 for h in health_rows if h["status"] == "degraded"
                ),
            },
            "read_only": True,
            "never_places_trades": True,
            "never_modifies_engines": True,
        }
