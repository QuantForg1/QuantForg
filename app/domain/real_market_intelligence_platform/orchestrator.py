"""RMIP orchestrator — market context enrichment; never production mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.real_market_intelligence_platform.config import (
    DEFAULT_RMIP_CONFIG,
    RmipConfig,
)
from app.domain.real_market_intelligence_platform.modules import (
    MISSING,
    context_api_payload,
    context_scoring,
    economic_calendar,
    explainability,
    historical_context_archive,
    liquidity_observatory,
    market_context_timeline,
    operator_intelligence_feed,
    session_intelligence,
    volatility_observatory,
)
from app.domain.real_market_intelligence_platform.types import (
    ModuleResult,
    RmipInput,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class RealMarketIntelligencePlatform:
    config: RmipConfig = field(default_factory=lambda: DEFAULT_RMIP_CONFIG)
    archive: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "economic_calendar",
                "session_intelligence",
                "volatility_observatory",
                "liquidity_observatory",
                "market_context_timeline",
                "context_scoring",
                "operator_intelligence_feed",
                "explainability",
                "historical_context_archive",
                "context_api",
            ],
            "capabilities": {
                "xauusd_only": True,
                "read_only": True,
                "context_only": True,
                "never_order_send": True,
                "never_place_trades": True,
                "never_change_trading_rules": True,
                "never_modify_auto_trading": True,
                "never_modify_execution": True,
                "never_modify_decision_engine": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_fabricate_macro_data": True,
                "never_fabricate_market_data": True,
                "append_only_archive": True,
                "promise_profitability": False,
                "symbol": GOLD_SYMBOL,
            },
            "recent_archive": self.archive[:10],
            "recent_timeline": self.timeline[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.archive[: max(1, min(limit, self.config.max_archive))]
        return {
            "status": "available" if rows else "empty",
            "items": rows,
            "append_only": True,
            "read_only_archive": True,
        }

    def evaluate(self, inp: RmipInput) -> dict[str, Any]:
        audit_id = f"rmip_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("economic_calendar", True):
            modules["economic_calendar"] = economic_calendar(inp, self.config)
        if flags.get("session_intelligence", True):
            modules["session_intelligence"] = session_intelligence(
                inp, self.config
            )
        if flags.get("volatility_observatory", True):
            modules["volatility_observatory"] = volatility_observatory(
                inp, self.config
            )
        if flags.get("liquidity_observatory", True):
            modules["liquidity_observatory"] = liquidity_observatory(
                inp, self.config
            )
        if flags.get("market_context_timeline", True):
            modules["market_context_timeline"] = market_context_timeline(
                inp, dict(modules), self.config
            )
            entry = (modules["market_context_timeline"].details or {}).get(
                "entry"
            )
            if isinstance(entry, dict):
                self.timeline.insert(0, entry)
                if len(self.timeline) > self.config.max_timeline:
                    self.timeline = self.timeline[: self.config.max_timeline]
        if flags.get("context_scoring", True):
            modules["context_scoring"] = context_scoring(inp, dict(modules))
        if flags.get("operator_intelligence_feed", True):
            modules["operator_intelligence_feed"] = (
                operator_intelligence_feed(dict(modules))
            )
        if flags.get("explainability", True):
            modules["explainability"] = explainability(dict(modules))

        score = modules.get("context_scoring")
        econ = modules.get("economic_calendar")
        sess = modules.get("session_intelligence")
        vol = modules.get("volatility_observatory")
        liq = modules.get("liquidity_observatory")
        snapshot = {
            "market_context": (
                (score.details or {}).get("market_context")
                if score
                else MISSING
            ),
            "economic_events": (
                (econ.details or {}).get("event_count") if econ else MISSING
            ),
            "economic_risk": (
                (econ.details or {}).get("market_risk_level")
                if econ
                else MISSING
            ),
            "volatility": (
                (vol.details or {}).get("volatility_level")
                if vol
                else MISSING
            ),
            "session": (
                (sess.details or {}).get("primary_session")
                if sess
                else MISSING
            ),
            "liquidity": (
                (liq.details or {}).get("liquidity_quality")
                if liq
                else MISSING
            ),
            "regime": inp.regime or MISSING,
        }

        if flags.get("historical_context_archive", True):
            modules["historical_context_archive"] = historical_context_archive(
                prior=list(self.archive),
                audit_id=audit_id,
                snapshot=snapshot,
                archive_event=inp.archive_event,
                config=self.config,
            )
            arch = (modules["historical_context_archive"].details or {}).get(
                "entry"
            )
            if isinstance(arch, dict):
                self.archive.insert(0, arch)
                if len(self.archive) > self.config.max_archive:
                    self.archive = self.archive[: self.config.max_archive]

        if flags.get("context_api", True):
            modules["context_api"] = context_api_payload(dict(modules))

        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "context_summary": {
                "market_context": snapshot["market_context"],
                "economic_risk": snapshot["economic_risk"],
                "session": snapshot["session"],
                "volatility": snapshot["volatility"],
                "liquidity": snapshot["liquidity"],
                "regime": snapshot["regime"],
                "trend": inp.trend or MISSING,
            },
            "read_only": True,
            "context_only": True,
            "advisory_only": True,
            "never_order_send": True,
            "never_place_trades": True,
            "never_change_trading_rules": True,
            "modifies_auto_trading": False,
            "modifies_execution": False,
            "modifies_decision_engine": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "promise_profitability": False,
            "append_only_archive": True,
            "explainable": True,
            "auditable": True,
        }


def input_from_dict(data: dict[str, Any]) -> RmipInput:
    return RmipInput(
        economic_events=(
            data.get("economic_events")
            if isinstance(data.get("economic_events"), list)
            else None
        ),
        clock_utc=str(data["clock_utc"]) if data.get("clock_utc") else None,
        session_hint=(
            str(data["session_hint"]) if data.get("session_hint") else None
        ),
        volatility_observations=(
            data.get("volatility_observations")
            if isinstance(data.get("volatility_observations"), dict)
            else None
        ),
        liquidity_observations=(
            data.get("liquidity_observations")
            if isinstance(data.get("liquidity_observations"), dict)
            else None
        ),
        regime=str(data["regime"]) if data.get("regime") else None,
        trend=str(data["trend"]) if data.get("trend") else None,
        confidence=str(data["confidence"]) if data.get("confidence") else None,
        archive_event=(
            data.get("archive_event")
            if isinstance(data.get("archive_event"), dict)
            else None
        ),
    )
