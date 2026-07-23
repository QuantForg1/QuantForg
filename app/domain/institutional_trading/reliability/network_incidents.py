"""Network / DNS incident detection — observe only; never mutates execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from app.domain.institutional_trading.reliability.models import IncidentSeverity

logger = logging.getLogger(__name__)

# Repeated failures in this window escalate severity.
ESCALATION_WINDOW = timedelta(minutes=15)
WARNING_THRESHOLD = 2  # failures in window (including current)
CRITICAL_THRESHOLD = 4

DNS_MARKERS = (
    "getaddrinfo",
    "name or service not known",
    "nodename nor servname",
    "name resolution",
    "nameresolutionerror",
    "temporary failure in name resolution",
    "dns failure",
    "dnserror",
    "gaierror",
)
NETWORK_MARKERS = (
    "connecterror",
    "connecttimeout",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "networkunreachable",
    "gateway unreachable",
    "timed out",
    "timeout",
    "ssl",
    "tls",
    "probefailure",
    "probe unavailable",
    "probe disconnected",
    *DNS_MARKERS,
)


class RecoveryStatus:
    ONGOING = "ONGOING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NetworkIncident:
    """One network/DNS incident with full operator evidence."""

    timestamp: datetime
    error: str
    retry_count: int
    recovery_status: str
    severity: IncidentSeverity
    kind: str  # dns | timeout | connect | reconnect | network
    component: str  # gateway | mt5 | railway | other
    duration_ms: float = 0.0
    id: UUID = field(default_factory=uuid4)
    resolved_at: datetime | None = None
    reconnect_attempts_logged: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": round(self.duration_ms, 3),
            "error": self.error,
            "retry_count": self.retry_count,
            "recovery_status": self.recovery_status,
            "severity": self.severity.value,
            "kind": self.kind,
            "component": self.component,
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at else None
            ),
            "reconnect_attempts_logged": self.reconnect_attempts_logged,
        }


@dataclass(frozen=True, slots=True)
class ReconnectLogEntry:
    """Every reconnect attempt must be logged — no silent retries."""

    at: datetime
    component: str
    attempt: int
    success: bool | None
    detail: str
    duration_ms: float = 0.0
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "at": self.at.isoformat(),
            "component": self.component,
            "attempt": self.attempt,
            "success": self.success,
            "detail": self.detail,
            "duration_ms": round(self.duration_ms, 3),
        }


def is_dns_error(error: str, error_type: str = "") -> bool:
    blob = f"{error} {error_type}".lower()
    return any(m in blob for m in DNS_MARKERS)


def is_network_error(error: str, error_type: str = "") -> bool:
    blob = f"{error} {error_type}".lower()
    return any(m in blob for m in NETWORK_MARKERS)


def classify_network_kind(error: str, error_type: str = "") -> str:
    blob = f"{error} {error_type}".lower()
    if is_dns_error(error, error_type):
        return "dns"
    if "timeout" in blob or "timed out" in blob:
        return "timeout"
    if "connect" in blob or "refused" in blob or "reset" in blob:
        return "connect"
    if "reconnect" in blob:
        return "reconnect"
    return "network"


@dataclass
class NetworkIncidentTracker:
    """Detect transient DNS/network failures and keep an auditable ledger."""

    escalation_window: timedelta = ESCALATION_WINDOW
    max_incidents: int = 5_000
    max_reconnect_logs: int = 10_000
    _incidents: list[NetworkIncident] = field(default_factory=list, repr=False)
    _reconnect_logs: list[ReconnectLogEntry] = field(default_factory=list, repr=False)
    _open_by_component: dict[str, UUID] = field(default_factory=dict, repr=False)
    _open_started: dict[str, datetime] = field(default_factory=dict, repr=False)
    _open_retries: dict[str, int] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Uptime accounting (probe-driven)
    _gateway_up: bool = True
    _mt5_up: bool = True
    _gateway_up_seconds: float = 0.0
    _gateway_down_seconds: float = 0.0
    _mt5_up_seconds: float = 0.0
    _mt5_down_seconds: float = 0.0
    _last_probe_at: datetime | None = None
    _reconnect_durations_ms: list[float] = field(default_factory=list, repr=False)
    _reconnect_count: int = 0

    def classify_severity(
        self,
        *,
        recovered: bool,
        failures_in_window: int,
        kind: str,
        now: datetime | None = None,
    ) -> IncidentSeverity:
        """Single recovered DNS timeout → INFO; repeats escalate."""
        _ = now
        if failures_in_window >= CRITICAL_THRESHOLD or (
            not recovered and failures_in_window >= WARNING_THRESHOLD
        ):
            return IncidentSeverity.CRITICAL
        if failures_in_window >= WARNING_THRESHOLD or (
            not recovered and kind in ("dns", "timeout", "connect", "network")
        ):
            return IncidentSeverity.WARNING
        # Single incident that recovered (incl. DNS timeout) → INFO
        return IncidentSeverity.INFO

    def _count_recent_failures(self, *, component: str, now: datetime) -> int:
        cutoff = now - self.escalation_window
        return sum(
            1
            for i in self._incidents
            if i.component == component and i.timestamp >= cutoff
        )

    def observe_transport_failure(
        self,
        *,
        error: str,
        error_type: str = "",
        component: str = "gateway",
        retry_count: int = 0,
        latency_ms: float = 0.0,
        now: datetime | None = None,
    ) -> NetworkIncident | None:
        """Record a transport/DNS failure. Returns None if not network-like."""
        if not is_network_error(error, error_type):
            return None
        moment = now or datetime.now(UTC)
        kind = classify_network_kind(error, error_type)
        with self._lock:
            recent = self._count_recent_failures(component=component, now=moment) + 1
            open_id = self._open_by_component.get(component)
            if open_id is not None:
                # Fold into open incident — bump retries, keep ONGOING
                for i, inc in enumerate(self._incidents):
                    if inc.id == open_id:
                        retries = max(inc.retry_count, retry_count) + 1
                        self._open_retries[component] = retries
                        started = self._open_started.get(component, inc.timestamp)
                        duration = (moment - started).total_seconds() * 1000.0
                        severity = self.classify_severity(
                            recovered=False,
                            failures_in_window=recent,
                            kind=kind,
                            now=moment,
                        )
                        updated = NetworkIncident(
                            timestamp=inc.timestamp,
                            error=error or inc.error,
                            retry_count=retries,
                            recovery_status=RecoveryStatus.ONGOING,
                            severity=severity,
                            kind=kind,
                            component=component,
                            duration_ms=duration,
                            id=inc.id,
                            resolved_at=None,
                            reconnect_attempts_logged=inc.reconnect_attempts_logged,
                        )
                        self._incidents[i] = updated
                        logger.warning(
                            "network_incident_ongoing component=%s severity=%s "
                            "retries=%s error=%s",
                            component,
                            severity.value,
                            retries,
                            error[:200],
                        )
                        return updated
            severity = self.classify_severity(
                recovered=False,
                failures_in_window=recent,
                kind=kind,
                now=moment,
            )
            inc = NetworkIncident(
                timestamp=moment,
                error=error,
                retry_count=max(0, retry_count),
                recovery_status=RecoveryStatus.ONGOING,
                severity=severity,
                kind=kind,
                component=component,
                duration_ms=max(0.0, latency_ms),
            )
            self._incidents.append(inc)
            self._open_by_component[component] = inc.id
            self._open_started[component] = moment
            self._open_retries[component] = inc.retry_count
            if len(self._incidents) > self.max_incidents:
                self._incidents = self._incidents[-self.max_incidents :]
            logger.warning(
                "network_incident_opened id=%s component=%s severity=%s kind=%s "
                "error=%s",
                inc.id,
                component,
                severity.value,
                kind,
                error[:200],
            )
            return inc

    def mark_recovered(
        self,
        *,
        component: str,
        now: datetime | None = None,
        detail: str = "recovered",
    ) -> NetworkIncident | None:
        moment = now or datetime.now(UTC)
        with self._lock:
            open_id = self._open_by_component.pop(component, None)
            started = self._open_started.pop(component, None)
            retries = self._open_retries.pop(component, 0)
            if open_id is None:
                return None
            for i, inc in enumerate(self._incidents):
                if inc.id != open_id:
                    continue
                duration = (
                    (moment - (started or inc.timestamp)).total_seconds() * 1000.0
                )
                recent = self._count_recent_failures(component=component, now=moment)
                # recovered single → INFO even if kind is dns
                severity = self.classify_severity(
                    recovered=True,
                    failures_in_window=max(1, recent),
                    kind=inc.kind,
                    now=moment,
                )
                # Force INFO when this was the only failure in window and recovered
                if recent <= 1:
                    severity = IncidentSeverity.INFO
                updated = NetworkIncident(
                    timestamp=inc.timestamp,
                    error=inc.error if not detail else f"{inc.error} | {detail}",
                    retry_count=max(inc.retry_count, retries),
                    recovery_status=RecoveryStatus.RECOVERED,
                    severity=severity,
                    kind=inc.kind,
                    component=inc.component,
                    duration_ms=duration,
                    id=inc.id,
                    resolved_at=moment,
                    reconnect_attempts_logged=inc.reconnect_attempts_logged,
                )
                self._incidents[i] = updated
                logger.info(
                    "network_incident_recovered id=%s component=%s severity=%s "
                    "duration_ms=%.1f retries=%s",
                    updated.id,
                    component,
                    severity.value,
                    duration,
                    updated.retry_count,
                )
                return updated
        return None

    def log_reconnect_attempt(
        self,
        *,
        component: str,
        attempt: int,
        detail: str,
        success: bool | None = None,
        duration_ms: float = 0.0,
        now: datetime | None = None,
    ) -> ReconnectLogEntry:
        """Mandatory audit of every reconnect attempt — never silent."""
        moment = now or datetime.now(UTC)
        entry = ReconnectLogEntry(
            at=moment,
            component=component,
            attempt=attempt,
            success=success,
            detail=detail,
            duration_ms=duration_ms,
        )
        with self._lock:
            self._reconnect_logs.append(entry)
            if len(self._reconnect_logs) > self.max_reconnect_logs:
                self._reconnect_logs = self._reconnect_logs[-self.max_reconnect_logs :]
            self._reconnect_count += 1
            if success is True and duration_ms > 0:
                self._reconnect_durations_ms.append(duration_ms)
                if len(self._reconnect_durations_ms) > 500:
                    self._reconnect_durations_ms = self._reconnect_durations_ms[-500:]
            # Attach to open incident if any
            open_id = self._open_by_component.get(component)
            if open_id is not None:
                for i, inc in enumerate(self._incidents):
                    if inc.id == open_id:
                        self._incidents[i] = NetworkIncident(
                            timestamp=inc.timestamp,
                            error=inc.error,
                            retry_count=max(inc.retry_count, attempt),
                            recovery_status=inc.recovery_status,
                            severity=inc.severity,
                            kind=inc.kind,
                            component=inc.component,
                            duration_ms=inc.duration_ms,
                            id=inc.id,
                            resolved_at=inc.resolved_at,
                            reconnect_attempts_logged=inc.reconnect_attempts_logged
                            + 1,
                        )
                        break
        logger.info(
            "network_reconnect_attempt component=%s attempt=%s success=%s detail=%s",
            component,
            attempt,
            success,
            detail[:200],
        )
        return entry

    def observe_health(
        self,
        *,
        gateway_available: bool,
        mt5_connected: bool,
        now: datetime | None = None,
    ) -> None:
        """Accumulate gateway/MT5 uptime from health probes."""
        moment = now or datetime.now(UTC)
        with self._lock:
            if self._last_probe_at is not None:
                delta = max(0.0, (moment - self._last_probe_at).total_seconds())
                if self._gateway_up:
                    self._gateway_up_seconds += delta
                else:
                    self._gateway_down_seconds += delta
                if self._mt5_up:
                    self._mt5_up_seconds += delta
                else:
                    self._mt5_down_seconds += delta
            prev_gw, prev_mt5 = self._gateway_up, self._mt5_up
            self._gateway_up = bool(gateway_available)
            self._mt5_up = bool(mt5_connected)
            self._last_probe_at = moment

        if prev_gw and not gateway_available:
            self.observe_transport_failure(
                error="Gateway unreachable (probe unavailable)",
                error_type="ProbeFailure",
                component="gateway",
                now=moment,
            )
        elif not prev_gw and gateway_available:
            self.mark_recovered(component="gateway", now=moment, detail="probe ok")

        if prev_mt5 and not mt5_connected:
            self.observe_transport_failure(
                error="MT5 unreachable (probe disconnected)",
                error_type="ProbeFailure",
                component="mt5",
                now=moment,
            )
        elif not prev_mt5 and mt5_connected:
            self.mark_recovered(component="mt5", now=moment, detail="probe ok")

    def has_open(self, component: str) -> bool:
        with self._lock:
            return component in self._open_by_component

    def observe_upstream(self, payload: dict[str, Any]) -> NetworkIncident | None:
        """Hook for gateway_client._record_upstream — never raises into trading."""
        try:
            if payload.get("ok", True):
                if self.has_open("gateway"):
                    return self.mark_recovered(
                        component="gateway",
                        detail="upstream ok",
                    )
                return None
            error = str(payload.get("error") or payload.get("diagnostic") or "unknown")
            error_type = str(payload.get("error_type") or "")
            retries = int(payload.get("retry_count") or payload.get("attempts") or 0)
            latency = float(payload.get("latency_ms") or 0.0)
            return self.observe_transport_failure(
                error=error,
                error_type=error_type,
                component="gateway",
                retry_count=retries,
                latency_ms=latency,
            )
        except Exception as exc:  # noqa: BLE001 — observability must not break path
            logger.debug("network_observe_upstream_failed: %s", exc)
            return None

    def list_incidents(self, *, limit: int = 100) -> list[NetworkIncident]:
        with self._lock:
            return list(self._incidents[-limit:])

    def list_reconnect_logs(self, *, limit: int = 100) -> list[ReconnectLogEntry]:
        with self._lock:
            return list(self._reconnect_logs[-limit:])

    def last_incident(self) -> NetworkIncident | None:
        with self._lock:
            return self._incidents[-1] if self._incidents else None

    def dashboard(self) -> dict[str, Any]:
        with self._lock:
            now = datetime.now(UTC)
            cutoff = now - timedelta(hours=24)
            dns_24h = sum(
                1
                for i in self._incidents
                if i.kind == "dns" and i.timestamp >= cutoff
            )
            network_24h = sum(1 for i in self._incidents if i.timestamp >= cutoff)
            gw_total = self._gateway_up_seconds + self._gateway_down_seconds
            mt5_total = self._mt5_up_seconds + self._mt5_down_seconds
            # Include time since last probe in current state
            if self._last_probe_at is not None:
                delta = max(0.0, (now - self._last_probe_at).total_seconds())
                if self._gateway_up:
                    gw_up = self._gateway_up_seconds + delta
                    gw_down = self._gateway_down_seconds
                else:
                    gw_up = self._gateway_up_seconds
                    gw_down = self._gateway_down_seconds + delta
                if self._mt5_up:
                    mt5_up = self._mt5_up_seconds + delta
                    mt5_down = self._mt5_down_seconds
                else:
                    mt5_up = self._mt5_up_seconds
                    mt5_down = self._mt5_down_seconds + delta
                gw_total = gw_up + gw_down
                mt5_total = mt5_up + mt5_down
            else:
                gw_up, gw_down = self._gateway_up_seconds, self._gateway_down_seconds
                mt5_up, mt5_down = self._mt5_up_seconds, self._mt5_down_seconds

            avg_reconnect = (
                sum(self._reconnect_durations_ms) / len(self._reconnect_durations_ms)
                if self._reconnect_durations_ms
                else 0.0
            )
            last = self._incidents[-1] if self._incidents else None
            open_count = sum(
                1
                for i in self._incidents
                if i.recovery_status == RecoveryStatus.ONGOING
            )
            return {
                "gateway_uptime_pct": round(
                    (gw_up / gw_total * 100.0) if gw_total > 0 else 100.0, 3
                ),
                "mt5_connection_uptime_pct": round(
                    (mt5_up / mt5_total * 100.0) if mt5_total > 0 else 100.0, 3
                ),
                "gateway_up_seconds": round(gw_up, 1),
                "gateway_down_seconds": round(gw_down, 1),
                "mt5_up_seconds": round(mt5_up, 1),
                "mt5_down_seconds": round(mt5_down, 1),
                "dns_failures_24h": dns_24h,
                "network_incidents_24h": network_24h,
                "reconnect_count": self._reconnect_count,
                "average_reconnect_time_ms": round(avg_reconnect, 3),
                "open_network_incidents": open_count,
                "last_network_incident": last.to_dict() if last else None,
                "tracker_started_at": self._started_at.isoformat(),
                "gateway_currently_up": self._gateway_up,
                "mt5_currently_up": self._mt5_up,
            }
