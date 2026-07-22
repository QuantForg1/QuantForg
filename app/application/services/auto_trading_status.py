"""Build Auto Trading status from the same live gateway probes as Broker/Monitoring.

Status polls must never invent FAIL for connectivity when the gateway is up,
and must never invent PASS for trade-context gates that were not evaluated.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.services.institutional_ite_runtime import get_ite_runtime
from app.application.services.institutional_live_probes import (
    LiveProbeCollector,
    gateway_available_from_health,
    mt5_connected_from_gateway_health,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradeSafetyResult,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.health import HealthInputs
from app.domain.trading.gold_only import GOLD_SYMBOL
from core.config.settings import Settings, get_settings
from core.logging import get_logger

logger = get_logger(__name__)

# Condition keys → UI reason groups (Risk BLOCK must not absorb operator/mode).
_REASON_GROUPS: dict[str, str] = {
    "auto_trading_toggle": "operator",
    "auto_trading_run_state": "operator",
    "emergency_stop": "safety",
    "ops_mode": "operator",
    "execution_enabled": "configuration",
    "gateway_connected": "connectivity",
    "broker_connected": "connectivity",
    "market_data_live": "connectivity",
    "risk_engine": "risk",
    "account_trading": "broker",
    "mt5_autotrading": "broker",
    "symbol_allowed": "risk",
    "symbol_tradable": "broker",
    "margin_available": "risk",
    "broker_restrictions": "broker",
    "daily_loss": "risk",
    "max_open_positions": "risk",
    "trading_session": "market",
    "max_spread": "market",
    "news_filter": "market",
}


@dataclass(frozen=True, slots=True)
class AutoTradingStatusSnapshot:
    facts: AutoTradeLiveFacts
    safety: AutoTradeSafetyResult
    live: dict[str, Any]
    reason_groups: dict[str, list[str]]


def _probe_collector(settings: Settings) -> LiveProbeCollector:
    runtime = get_ite_runtime()
    if runtime is not None:
        return runtime.probes
    return LiveProbeCollector(settings=settings)


def _sync_ops_health(
    plane: OperationsControlPlane, *, probes: Any
) -> None:
    """Write live probe results into the ops HealthMonitor (no alert spam)."""
    plane.health.observe(
        HealthInputs(
            gateway_latency_ms=float(getattr(probes, "gateway_latency_ms", 0.0) or 0.0),
            gateway_available=bool(getattr(probes, "gateway_available", False)),
            mt5_connected=bool(getattr(probes, "mt5_connected", False)),
            cloudflare_tunnel_up=bool(
                getattr(probes, "cloudflare_tunnel_up", False)
            ),
        )
    )


def _enrich_from_adapter(
    collector: LiveProbeCollector,
) -> dict[str, Any]:
    """Best-effort account/symbol flags from gateway health / adapter."""
    out: dict[str, Any] = {
        "account_trading_enabled": None,
        "mt5_autotrading_enabled": None,
        "symbol_tradable": None,
        "no_broker_restrictions": None,
        "market_data_live": None,
        "margin_available": None,
        "spread": None,
        "session": None,
        "health_payload": None,
    }
    client = (
        getattr(collector.mt5_adapter, "client", None)
        if collector.mt5_adapter is not None
        else None
    )
    health_fn = getattr(client, "gateway_health", None)
    payload: dict[str, Any] | None = None
    if callable(health_fn):
        try:
            raw = health_fn()
            if isinstance(raw, dict):
                payload = raw
                out["health_payload"] = raw
        except Exception as exc:
            logger.info("auto_trading_status_gateway_health_failed", error=str(exc))

    if payload is not None:
        mt5 = payload.get("mt5") if isinstance(payload.get("mt5"), dict) else {}
        account = (
            payload.get("account") if isinstance(payload.get("account"), dict) else {}
        )
        # Explicit flags when gateway exposes them — never invent True.
        for key, dest in (
            ("trade_allowed", "account_trading_enabled"),
            ("account_trade_allowed", "account_trading_enabled"),
            ("trading_allowed", "account_trading_enabled"),
            ("autotrading", "mt5_autotrading_enabled"),
            ("autotrading_enabled", "mt5_autotrading_enabled"),
            ("mt5_autotrading_enabled", "mt5_autotrading_enabled"),
        ):
            if key in payload:
                out[dest] = bool(payload.get(key))
            elif isinstance(mt5, dict) and key in mt5:
                out[dest] = bool(mt5.get(key))
            elif isinstance(account, dict) and key in account:
                out[dest] = bool(account.get(key))

        trade_mode = account.get("trade_mode") or payload.get("trade_mode")
        if trade_mode is not None and out["account_trading_enabled"] is None:
            mode = str(trade_mode).strip().lower()
            if mode in {"disabled", "0"}:
                out["account_trading_enabled"] = False
            elif mode in {"full", "enabled", "2", "4"}:
                out["account_trading_enabled"] = True

        free = account.get("margin_free") or account.get("free_margin")
        if free is not None:
            with contextlib.suppress(Exception):
                out["margin_available"] = Decimal(str(free)) > 0

    # Live tick → market data + spread (same evidence Broker uses for Market Open).
    adapter = collector.mt5_adapter
    if adapter is not None:
        with contextlib.suppress(Exception):
            tick = adapter.latest_tick(GOLD_SYMBOL)
            bid = getattr(tick, "bid", None)
            ask = getattr(tick, "ask", None)
            if bid is not None and ask is not None:
                out["market_data_live"] = True
                out["spread"] = abs(Decimal(str(ask)) - Decimal(str(bid)))
                out["symbol_tradable"] = True
        with contextlib.suppress(Exception):
            info = adapter.account_info()
            free_m = getattr(info, "free_margin", None)
            if free_m is not None and out["margin_available"] is None:
                out["margin_available"] = Decimal(str(free_m)) > 0
            trade_allowed = getattr(info, "trade_allowed", None)
            if trade_allowed is not None and out["account_trading_enabled"] is None:
                out["account_trading_enabled"] = bool(trade_allowed)

    return out


def build_status_facts(
    plane: OperationsControlPlane,
    *,
    settings: Settings | None = None,
) -> tuple[AutoTradeLiveFacts, dict[str, Any]]:
    """Authoritative connectivity facts for Auto Trading status GET."""
    cfg = settings or get_settings()
    collector = _probe_collector(cfg)
    probes = collector.collect()
    _sync_ops_health(plane, probes=probes)
    enriched = _enrich_from_adapter(collector)

    gateway_ok = bool(probes.gateway_available)
    broker_ok = bool(probes.mt5_connected)
    # Prefer probe; if adapter health payload disagrees, probe already used it.
    if enriched.get("health_payload") and isinstance(enriched["health_payload"], dict):
        payload = enriched["health_payload"]
        gateway_ok = gateway_available_from_health(payload, http_ok=gateway_ok)
        broker_ok = mt5_connected_from_gateway_health(payload) or broker_ok

    market_live = enriched.get("market_data_live")
    if market_live is None:
        # Connected MT5 with gateway up is enough to clear "not live" for status;
        # still fail-closed for trade submit when tick cannot be sampled.
        market_live = gateway_ok and broker_ok

    def _opt_bool(value: Any, *, when_unknown: bool) -> bool:
        return when_unknown if value is None else bool(value)

    facts = AutoTradeLiveFacts(
        gateway_connected=gateway_ok,
        broker_connected=broker_ok,
        market_data_live=bool(market_live),
        # Status poll: no pending trade decision — do not invent Risk FAIL.
        risk_engine_pass=True,
        risk_engine_reasons=(
            "Risk Engine not evaluated — no pending auto-trade decision",
        ),
        risk_engine_evaluated=False,
        account_trading_enabled=_opt_bool(
            enriched.get("account_trading_enabled"), when_unknown=True
        ),
        mt5_autotrading_enabled=_opt_bool(
            enriched.get("mt5_autotrading_enabled"), when_unknown=True
        ),
        account_flags_evaluated=enriched.get("account_trading_enabled") is not None
        or enriched.get("mt5_autotrading_enabled") is not None,
        symbol=GOLD_SYMBOL,
        symbol_tradable=_opt_bool(
            enriched.get("symbol_tradable"), when_unknown=broker_ok
        ),
        margin_available=_opt_bool(
            enriched.get("margin_available"), when_unknown=True
        ),
        margin_evaluated=enriched.get("margin_available") is not None,
        no_broker_restrictions=_opt_bool(
            enriched.get("no_broker_restrictions"), when_unknown=True
        ),
        open_positions=0,
        session="",
        session_evaluated=False,
        spread=enriched.get("spread")
        if isinstance(enriched.get("spread"), Decimal)
        else None,
        spread_evaluated=isinstance(enriched.get("spread"), Decimal),
        news_blocked=False,
        daily_loss_exceeded=plane.daily_loss_exceeded,
        emergency_stop=plane.kill_switch_armed,
        ops_mode=plane.mode.value,
        execution_enabled=bool(getattr(cfg, "execution_enabled", False)),
        status_snapshot=True,
    )
    live = {
        "gateway_connected": gateway_ok,
        "broker_connected": broker_ok,
        "market_data_live": bool(market_live),
        "gateway_latency_ms": float(probes.gateway_latency_ms or 0.0),
        "cloudflare_tunnel_up": bool(probes.cloudflare_tunnel_up),
        "source": "live_probe",
        "ops_health_synced": True,
    }
    return facts, live


def group_failed_reasons(safety: AutoTradeSafetyResult) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "operator": [],
        "configuration": [],
        "connectivity": [],
        "broker": [],
        "risk": [],
        "market": [],
        "safety": [],
        "other": [],
    }
    for cond in safety.conditions:
        if cond.passed:
            continue
        detail = cond.detail or f"{cond.label} failed"
        bucket = _REASON_GROUPS.get(cond.key, "other")
        if detail not in groups[bucket]:
            groups[bucket].append(detail)
    return {k: v for k, v in groups.items() if v}


def build_auto_trading_status(
    plane: OperationsControlPlane,
    *,
    settings: Settings | None = None,
) -> AutoTradingStatusSnapshot:
    facts, live = build_status_facts(plane, settings=settings)
    safety = plane.evaluate_auto_trading(facts)
    return AutoTradingStatusSnapshot(
        facts=facts,
        safety=safety,
        live=live,
        reason_groups=group_failed_reasons(safety),
    )
