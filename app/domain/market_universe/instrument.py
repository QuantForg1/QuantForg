"""Canonical instrument record for the market-universe registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.market_universe.classification import ClassificationResult
from app.domain.market_universe.constants import UNKNOWN
from app.domain.market_universe.data_quality import DataQuality
from app.domain.market_universe.identity import CanonicalIdentity


def _u(value: Any) -> Any:
    if value in (None, ""):
        return UNKNOWN
    return value


@dataclass(slots=True)
class InstrumentRecord:
    identity: CanonicalIdentity
    classification: ClassificationResult
    data_quality: DataQuality
    quote_currency: str = UNKNOWN
    base_currency: str = UNKNOWN
    contract_size: str = UNKNOWN
    point: str = UNKNOWN
    digits: int | str = UNKNOWN
    tick_size: str = UNKNOWN
    tick_value: str = UNKNOWN
    min_volume: str = UNKNOWN
    max_volume: str = UNKNOWN
    volume_step: str = UNKNOWN
    trading_sessions: str = UNKNOWN
    timezone: str = UNKNOWN
    exchange: str = UNKNOWN
    broker: str = UNKNOWN
    margin_requirements: str = UNKNOWN
    leverage_constraints: str = UNKNOWN
    contract_type: str = UNKNOWN
    market_status: str = UNKNOWN
    trade_mode: str = UNKNOWN
    data_availability: str = UNKNOWN
    last_quote_timestamp: str = UNKNOWN
    spread: str | float = UNKNOWN
    liquidity_metadata: str = UNKNOWN
    tradable: bool = False
    research_eligible: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ident = self.identity.to_dict()
        cls = self.classification.to_dict()
        dq = self.data_quality.to_dict()
        return {
            "canonical_symbol": ident["canonical_symbol"],
            "broker_symbol": ident["broker_symbol"],
            "display_name": ident["display_name"],
            "display_symbol": ident.get("display_name") or ident["broker_symbol"],
            "status": _u(self.data_availability or dq.get("state")),
            "asset_class": cls["asset_class"],
            "classification_source": cls["classification_source"],
            "classification_reason": cls["classification_reason"],
            "classification_confidence": cls.get("classification_confidence")
            or UNKNOWN,
            "filling_mode": _u(self.extra.get("filling_mode")),
            "execution_mode": _u(self.extra.get("execution_mode")),
            "swap": _u(self.extra.get("swap")),
            "visible": self.extra.get("visible", UNKNOWN),
            "trade_allowed": self.extra.get("trade_allowed", UNKNOWN),
            "timeframe_quality": self.extra.get("timeframe_quality") or {},
            "quote_currency": _u(self.quote_currency),
            "base_currency": _u(self.base_currency),
            "contract_size": _u(self.contract_size),
            "point": _u(self.point),
            "digits": _u(self.digits),
            "tick_size": _u(self.tick_size),
            "tick_value": _u(self.tick_value),
            "min_volume": _u(self.min_volume),
            "max_volume": _u(self.max_volume),
            "volume_step": _u(self.volume_step),
            "trading_sessions": _u(self.trading_sessions),
            "timezone": _u(self.timezone),
            "exchange": _u(self.exchange or ident.get("exchange")),
            "broker": _u(self.broker or ident.get("broker")),
            "margin_requirements": _u(self.margin_requirements),
            "leverage_constraints": _u(self.leverage_constraints),
            "contract_type": _u(self.contract_type),
            "market_status": _u(self.market_status or dq.get("session_status")),
            "trade_mode": _u(self.trade_mode),
            "data_availability": _u(self.data_availability or dq.get("state")),
            "last_quote_timestamp": _u(self.last_quote_timestamp),
            "spread": _u(self.spread if self.spread != "" else UNKNOWN),
            "liquidity_metadata": _u(self.liquidity_metadata),
            "broker_forms": ident["broker_forms"],
            "aliases": ident["aliases"],
            "tradable": self.tradable,
            "research_eligible": self.research_eligible,
            "research_enabled": self.research_eligible,
            "live_execution_enabled": bool(self.extra.get("live_execution_enabled")),
            "live_execution_eligible": False,
            "data_age_seconds": dq.get("quote_age_seconds")
            if dq.get("quote_age_seconds") not in (None, "")
            else UNKNOWN,
            "bid": _u(self.extra.get("bid")),
            "ask": _u(self.extra.get("ask")),
            "quote_timestamp": _u(self.last_quote_timestamp),
            "session_state": _u(self.trading_sessions or self.market_status),
            "available_timeframes": self.extra.get("timeframe_quality") or {},
            "history_status": dq.get("bar_freshness") or UNKNOWN,
            "last_error": _u(self.extra.get("last_error")),
            "data_quality": dq,
            "authorizes_trade": False,
        }
