"""Production trading-component health derivation (observe-only).

Derives Gateway / OMS / MT5 / AI statuses from runtime evidence only.
Never fabricates HEALTHY. Never enables execution or changes strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.services.institutional_live_probes import LiveProbeCollector
from app.domain.institutional_trading.reliability.health import ProbeInputs
from core.config.settings import Settings


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    status: str
    detail: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


def derive_oms_status(
    *,
    execution_enabled: bool,
    gateway_available: bool,
    mt5_connected: bool,
    mt5_use_mock: bool,
) -> ComponentHealth:
    """OMS is HEALTHY only when the live submit path is proven ready.

    Evidence required:
    - EXECUTION_ENABLED
    - gateway reachable
    - MT5 connected
    - not mock mode
    """
    evidence = {
        "execution_enabled": execution_enabled,
        "gateway_available": gateway_available,
        "mt5_connected": mt5_connected,
        "mt5_use_mock": mt5_use_mock,
    }
    if not execution_enabled:
        return ComponentHealth(
            name="oms",
            status="DISABLED",
            detail="EXECUTION_ENABLED=false",
            evidence=evidence,
        )
    missing: list[str] = []
    if not gateway_available:
        missing.append("gateway_unavailable")
    if not mt5_connected:
        missing.append("mt5_disconnected")
    if mt5_use_mock:
        missing.append("mt5_use_mock=true")
    if missing:
        return ComponentHealth(
            name="oms",
            status="NOT_READY",
            detail="execution_enabled but dependencies missing: " + ",".join(missing),
            evidence={**evidence, "missing": missing},
        )
    return ComponentHealth(
        name="oms",
        status="HEALTHY",
        detail=(
            "EXECUTION_ENABLED with gateway+MT5 live and mock disabled "
            "(OMS submit path ready)"
        ),
        evidence=evidence,
    )


def derive_ai_status(*, ite_runtime_present: bool) -> ComponentHealth:
    """AI is HEALTHY only when ITE runtime is present in this process.

    ITE runtime is set during API DI bootstrap (build_ite_runtime/set_ite_runtime).
    Off-process probes must not invent HEALTHY — they should report the
    missing dependency explicitly.
    """
    if ite_runtime_present:
        return ComponentHealth(
            name="ai",
            status="HEALTHY",
            detail="ITE runtime present in process (DI bootstrap)",
            evidence={"ite_runtime_present": True},
        )
    return ComponentHealth(
        name="ai",
        status="NOT_READY",
        detail=(
            "missing_dependency:ite_runtime — ITE runtime is only set during "
            "API process DI bootstrap; not present in this process"
        ),
        evidence={
            "ite_runtime_present": False,
            "missing_dependency": "ite_runtime",
        },
    )


def collect_trading_component_health(
    settings: Settings,
    *,
    probes: ProbeInputs | None = None,
    ite_runtime_present: bool | None = None,
) -> dict[str, Any]:
    """Build Gateway/OMS/MT5/AI component health from live probes + runtime."""
    collector = LiveProbeCollector(settings=settings)
    live = probes or collector.collect()

    if ite_runtime_present is None:
        try:
            from app.application.services.institutional_ite_runtime import (
                get_ite_runtime,
            )

            ite_runtime_present = get_ite_runtime() is not None
        except Exception as exc:
            ite_runtime_present = False
            ai_error = f"{type(exc).__name__}"
        else:
            ai_error = None
    else:
        ai_error = None

    execution_enabled = bool(getattr(settings, "execution_enabled", False))
    mt5_use_mock = bool(getattr(settings, "mt5_use_mock", True))
    mt5_enabled = bool(getattr(settings, "mt5_enabled", False))

    gateway = ComponentHealth(
        name="gateway",
        status="HEALTHY" if live.gateway_available else "DOWN",
        detail=(
            f"gateway_available={live.gateway_available} "
            f"latency_ms={live.gateway_latency_ms}"
        ),
        evidence={
            "available": bool(live.gateway_available),
            "latency_ms": float(live.gateway_latency_ms or 0.0),
            "cloudflare_tunnel_up": bool(live.cloudflare_tunnel_up),
        },
    )
    mt5 = ComponentHealth(
        name="mt5",
        status="CONNECTED" if live.mt5_connected else "DISCONNECTED",
        detail=(
            f"mt5_connected={live.mt5_connected} "
            f"enabled={mt5_enabled} mock={mt5_use_mock}"
        ),
        evidence={
            "connected": bool(live.mt5_connected),
            "enabled": mt5_enabled,
            "use_mock": mt5_use_mock,
        },
    )
    oms = derive_oms_status(
        execution_enabled=execution_enabled,
        gateway_available=bool(live.gateway_available),
        mt5_connected=bool(live.mt5_connected),
        mt5_use_mock=mt5_use_mock,
    )
    ai = derive_ai_status(ite_runtime_present=bool(ite_runtime_present))
    if ai_error:
        ai = ComponentHealth(
            name="ai",
            status=f"ERROR:{ai_error}",
            detail=f"ite_runtime_lookup_failed:{ai_error}",
            evidence={"ite_runtime_present": False, "error": ai_error},
        )

    components = [gateway, oms, mt5, ai]
    return {
        "gateway": gateway.to_dict(),
        "oms": oms.to_dict(),
        "mt5": mt5.to_dict(),
        "ai": ai.to_dict(),
        "components": [c.to_dict() for c in components],
        "statuses": {
            "gateway": gateway.status,
            "oms": oms.status,
            "mt5": mt5.status,
            "ai": ai.status,
        },
        "all_ready_for_limited_pilot": (
            gateway.status == "HEALTHY"
            and oms.status == "HEALTHY"
            and mt5.status == "CONNECTED"
            and ai.status == "HEALTHY"
        ),
    }
