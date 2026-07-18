"""Broker Connectivity Framework service — registry, invoke, diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.broker_connectivity.certification import (
    certification_dashboard,
    run_certification,
)
from app.domain.broker_connectivity.certification_store import CertificationStore
from app.domain.broker_connectivity.compatibility import run_compatibility_suite
from app.domain.broker_connectivity.matrix import matrix_as_dicts, profile_for
from app.domain.broker_connectivity.mt5_ecosystem import (
    ecosystem_as_dicts,
    profile_by_slug,
)
from app.domain.broker_connectivity.port import BrokerConnectivityPort
from app.domain.broker_connectivity.types import (
    ConnectivityCapability,
    ConnectivityResult,
    ConnectivityStatus,
)
from app.infrastructure.brokers.connectivity.mt5 import MT5ConnectivityAdapter
from app.infrastructure.brokers.connectivity.unsupported import (
    default_unsupported_adapters,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class BrokerConnectivityService:
    """Registry of connectivity adapters — MT5 live, others unsupported."""

    _adapters: dict[str, BrokerConnectivityPort] = field(default_factory=dict)
    _health_monitor: Any | None = None
    _reconnect_manager: Any | None = None
    _paper_available: bool = False
    _cert_store: CertificationStore = field(default_factory=CertificationStore)

    @classmethod
    def create(
        cls,
        *,
        mt5: MT5Adapter | None = None,
        health_monitor: Any | None = None,
        reconnect_manager: Any | None = None,
        paper_available: bool = False,
        cert_store: CertificationStore | None = None,
    ) -> BrokerConnectivityService:
        svc = cls(
            _health_monitor=health_monitor,
            _reconnect_manager=reconnect_manager,
            _paper_available=paper_available,
            _cert_store=cert_store or CertificationStore(),
        )
        if mt5 is not None:
            svc.register(MT5ConnectivityAdapter(mt5))
        for stub in default_unsupported_adapters():
            if stub.platform not in svc._adapters:
                svc.register(stub)
        return svc

    def register(self, adapter: BrokerConnectivityPort) -> None:
        self._adapters[adapter.platform.strip().lower()] = adapter

    def get(self, platform: str) -> BrokerConnectivityPort | None:
        return self._adapters.get(platform.strip().lower())

    def catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for platform, adapter in sorted(self._adapters.items()):
            profile = adapter.capability_profile()
            rows.append(
                {
                    "platform": platform,
                    "name": adapter.name,
                    "implemented": profile.implemented,
                    "capabilities": [c.value for c in profile.capabilities],
                    "notes": profile.notes,
                }
            )
        return rows

    def capability_matrix(self) -> list[dict[str, Any]]:
        return matrix_as_dicts()

    def invoke(
        self,
        platform: str,
        capability: str,
        *,
        params: dict[str, Any] | None = None,
        symbol: str = "",
        timeframe: str = "H1",
        count: int = 100,
        limit: int = 100,
        intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adapter = self.get(platform)
        if adapter is None:
            return ConnectivityResult(
                status=ConnectivityStatus.UNSUPPORTED,
                capability=ConnectivityCapability.CAPABILITIES,
                platform=platform.strip().lower(),
                reason=f"Unknown platform '{platform}'",
            ).to_dict()

        try:
            cap = ConnectivityCapability(capability.strip().lower())
        except ValueError:
            return {
                "status": ConnectivityStatus.ERROR.value,
                "capability": capability,
                "platform": adapter.platform,
                "data": None,
                "reason": f"Unknown capability '{capability}'",
                "latency_ms": None,
            }

        params = params or {}
        intent = intent or {}

        if cap is ConnectivityCapability.CONNECT:
            result = adapter.connect(params)
        elif cap is ConnectivityCapability.DISCONNECT:
            result = adapter.disconnect()
        elif cap is ConnectivityCapability.HEALTH:
            result = adapter.health()
        elif cap is ConnectivityCapability.HEARTBEAT:
            result = adapter.heartbeat()
        elif cap is ConnectivityCapability.BALANCES:
            result = adapter.balances()
        elif cap is ConnectivityCapability.POSITIONS:
            result = adapter.positions()
        elif cap is ConnectivityCapability.ORDERS:
            result = adapter.orders()
        elif cap is ConnectivityCapability.HISTORY:
            result = adapter.history(limit=limit)
        elif cap is ConnectivityCapability.SYMBOLS:
            result = adapter.symbols()
        elif cap is ConnectivityCapability.QUOTES:
            if not symbol:
                return ConnectivityResult(
                    status=ConnectivityStatus.ERROR,
                    capability=cap,
                    platform=adapter.platform,
                    reason="symbol is required for quotes",
                ).to_dict()
            result = adapter.quotes(symbol)
        elif cap is ConnectivityCapability.CANDLES:
            if not symbol:
                return ConnectivityResult(
                    status=ConnectivityStatus.ERROR,
                    capability=cap,
                    platform=adapter.platform,
                    reason="symbol is required for candles",
                ).to_dict()
            result = adapter.candles(symbol, timeframe=timeframe, count=count)
        elif cap is ConnectivityCapability.TRADING:
            result = adapter.trading(intent)
        elif cap is ConnectivityCapability.CAPABILITIES:
            result = adapter.capabilities()
        else:
            return ConnectivityResult(
                status=ConnectivityStatus.ERROR,
                capability=cap,
                platform=adapter.platform,
                reason=f"Unhandled capability '{cap.value}'",
            ).to_dict()

        return result.to_dict()

    def diagnostics(self, platform: str | None = None) -> dict[str, Any]:
        """Latency, heartbeat, reconnect, failures, capability checks."""
        platforms = (
            [platform.strip().lower()] if platform else sorted(self._adapters.keys())
        )
        adapters_out: list[dict[str, Any]] = []
        for code in platforms:
            adapter = self.get(code)
            if adapter is None:
                adapters_out.append(
                    {
                        "platform": code,
                        "status": ConnectivityStatus.UNSUPPORTED.value,
                        "reason": "Unknown platform",
                    }
                )
                continue
            diag_fn = getattr(adapter, "diagnostics", None)
            if callable(diag_fn):
                adapters_out.append(diag_fn())
            else:
                health = adapter.health()
                profile = adapter.capability_profile()
                adapters_out.append(
                    {
                        "platform": code,
                        "implemented": profile.implemented,
                        "health": health.to_dict(),
                        "heartbeat": None,
                        "reconnect_history": [],
                        "failures": [],
                        "capability_checks": {
                            c.value: c in profile.capabilities
                            for c in ConnectivityCapability
                        },
                        "latency_ms": health.latency_ms,
                    }
                )

        monitor_rows: list[dict[str, Any]] = []
        if self._health_monitor is not None:
            by_conn = getattr(self._health_monitor, "_by_connection", {}) or {}
            for health in by_conn.values():
                to_dict = getattr(health, "to_dict", None)
                if callable(to_dict):
                    monitor_rows.append(to_dict())

        reconnect_rows: list[dict[str, Any]] = []
        if self._reconnect_manager is not None:
            states = getattr(self._reconnect_manager, "_states", {}) or {}
            for state in states.values():
                reconnect_rows.append(
                    {
                        "connection_id": str(getattr(state, "connection_id", "")),
                        "attempts": getattr(state, "attempts", 0),
                        "last_attempt_at": (
                            state.last_attempt_at.isoformat()
                            if getattr(state, "last_attempt_at", None)
                            else None
                        ),
                        "cooldown_until": (
                            state.cooldown_until.isoformat()
                            if getattr(state, "cooldown_until", None)
                            else None
                        ),
                        "events": list(getattr(state, "events", []) or [])[-20:],
                    }
                )

        matrix_rows: list[dict[str, Any]] = []
        for row in adapters_out:
            code = str(row.get("platform") or "")
            maybe = profile_for(code)
            if maybe is not None:
                matrix_rows.append(maybe.to_dict())

        return {
            "adapters": adapters_out,
            "broker_health_monitor": monitor_rows,
            "reconnect_manager": reconnect_rows,
            "matrix": matrix_rows,
        }

    def ecosystem(self) -> dict[str, Any]:
        """MT5 Broker Ecosystem v1.1 — documented retail brand profiles."""
        return {
            "version": "1.1",
            "platform": "mt5",
            "items": ecosystem_as_dicts(),
            "notes": (
                "Priority brands use the live MT5 adapter. Profiles are "
                "documented onboarding metadata — not simulated connectivity."
            ),
        }

    def onboarding(self, slug: str) -> dict[str, Any] | None:
        profile = profile_by_slug(slug)
        if profile is None:
            return None
        return {
            "slug": profile.slug,
            "name": profile.name,
            "website": profile.website,
            "platform": profile.platform,
            "server_hints": list(profile.server_hints),
            "steps": [s.to_dict() for s in profile.onboarding],
            "notes": profile.notes,
            "connect_path": "/mt5",
            "compatibility_path": "/broker-compatibility",
        }

    def compatibility(
        self,
        *,
        broker_slug: str | None = None,
        quote_symbol: str = "EURUSD",
    ) -> dict[str, Any]:
        return run_compatibility_suite(
            invoke=self.invoke,
            broker_slug=broker_slug,
            quote_symbol=quote_symbol,
            paper_available=self._paper_available,
        )

    def compatibility_dashboard(self) -> dict[str, Any]:
        suite = self.compatibility()
        return {
            "title": "Broker Compatibility Dashboard",
            "version": suite.get("version"),
            "session": suite.get("session"),
            "matrix": suite.get("matrix"),
            "brokers": suite.get("brokers"),
            "checks": suite.get("checks"),
            "operator_actions": suite.get("operator_actions"),
            "ecosystem": self.ecosystem(),
            "notes": (
                "Compatible cells require a live MT5 session for that brand. "
                "pending_session is not a failure — connect via /mt5."
            ),
        }

    def run_certification(
        self,
        *,
        broker_slug: str | None = None,
        quote_symbol: str = "EURUSD",
        tester: str = "operator",
    ) -> dict[str, Any]:
        return run_certification(
            store=self._cert_store,
            invoke=self.invoke,
            broker_slug=broker_slug,
            quote_symbol=quote_symbol,
            paper_available=self._paper_available,
            tester=tester,
            persist=True,
        )

    def certification_status(self, slug: str | None = None) -> dict[str, Any]:
        if slug:
            row = self._cert_store.get_status(slug)
            if row is None:
                return {
                    "slug": slug,
                    "state": "Not Tested",
                    "result": "not_tested",
                }
            return row
        return {"items": self._cert_store.all_status()}

    def certification_history(
        self, *, broker_slug: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        return {"items": self._cert_store.history(broker_slug=broker_slug, limit=limit)}

    def certification_dashboard(self) -> dict[str, Any]:
        return certification_dashboard(self._cert_store)

    def dashboard(self) -> dict[str, Any]:
        return {
            "catalog": self.catalog(),
            "matrix": self.capability_matrix(),
            "diagnostics": self.diagnostics(),
            "ecosystem": self.ecosystem(),
            "compatibility": self.compatibility(),
            "certification": self.certification_dashboard(),
            "notes": (
                "MT5 is the only live connectivity adapter. "
                "Future venues return status=unsupported "
                "without simulated connectivity. "
                "Ecosystem v1.1 brands are MT5 retail profiles."
            ),
        }
