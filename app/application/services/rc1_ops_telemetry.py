"""RC1 ops telemetry — live audits + infrastructure probes. Does not trade."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _pct(numerator: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * numerator / den, 2)


@dataclass(frozen=True, slots=True)
class Rc1OpsTelemetryService:
    """Aggregate RC1 operations metrics from durable audits + live probes."""

    execution_audit_uow_factory: Any
    settings: Any
    health_service: Any | None = None

    async def collect(self) -> dict[str, object]:
        now = datetime.now(UTC)
        day_ago = now - timedelta(hours=24)
        audits = await self._load_audits(limit=2000)
        today = [a for a in audits if a.created_at >= day_ago]

        submits = [a for a in today if str(a.stage.value) == "submit"]
        risks = [a for a in today if str(a.stage.value) == "risk"]
        validations = [a for a in today if str(a.stage.value) == "validation"]

        submit_ok = 0
        for a in submits:
            outcome = str(a.outcome).lower()
            if outcome in {"failed", "reject", "rejected", "error"}:
                continue
            if a.retcode in {0, 10008, 10009} or outcome in {
                "success",
                "allow",
                "filled",
                "ok",
            }:
                submit_ok += 1
        submit_fail = max(0, len(submits) - submit_ok)
        risk_reject = sum(1 for a in risks if "reject" in str(a.outcome).lower())

        broker_lat = [
            float(a.latency_ms)
            for a in submits
            if a.latency_ms is not None and a.latency_ms >= 0
        ]
        gateway_lat = [
            float(a.gateway_latency_ms)
            for a in today
            if a.gateway_latency_ms is not None and a.gateway_latency_ms >= 0
        ]
        validation_lat = [
            float(a.latency_ms)
            for a in validations
            if a.latency_ms is not None and a.latency_ms >= 0
        ]

        daily_volume = 0.0
        for a in submits:
            try:
                daily_volume += float(a.volume or 0)
            except (TypeError, ValueError):
                continue

        infra = await self._probe_infra()
        known = [
            c
            for c in (
                infra.get("gateway"),
                infra.get("railway"),
                infra.get("cloudflare"),
                infra.get("mt5"),
            )
            if c in {"up", "down", "degraded"}
        ]
        up_n = sum(1 for c in known if c == "up")
        health_score = round(100.0 * up_n / len(known), 1) if known else None

        success_pct = _pct(submit_ok, len(submits))
        reject_pct = _pct(submit_fail, len(submits))
        risk_pct = _pct(risk_reject, len(risks))
        alerts = self._build_alerts(
            infra=infra,
            health_score=health_score,
            success_pct=success_pct,
            reject_pct=reject_pct,
            risk_pct=risk_pct,
            avg_broker=_avg(broker_lat),
            avg_gateway=_avg(gateway_lat),
        )

        return {
            "collected_at": now.isoformat(),
            "window": "24h",
            "execution_success_pct": success_pct,
            "execution_reject_pct": reject_pct,
            "risk_reject_pct": risk_pct,
            "avg_broker_latency_ms": _avg(broker_lat),
            "avg_gateway_latency_ms": _avg(gateway_lat),
            "avg_validation_time_ms": _avg(validation_lat),
            "daily_orders": len(submits),
            "daily_volume": round(daily_volume, 4) if submits else None,
            "daily_pnl": None,
            "gateway_availability": infra.get("gateway", "unknown"),
            "railway_availability": infra.get("railway", "unknown"),
            "cloudflare_availability": infra.get("cloudflare", "unknown"),
            "mt5_availability": infra.get("mt5", "unknown"),
            "system_health_score": health_score,
            "alerts": alerts,
            "audit_rows_24h": len(today),
            "unique_request_chains_24h": len({a.request_id for a in today}),
            "notes": {
                "daily_pnl": "Not available from execution_audits — use Journal deals",
                "source": "execution_audits + live infrastructure probes",
                "stage_coverage": (
                    "Recorded: validation, risk, safety, submit, replay. "
                    "manage/cancel reserved; close/history via Journal deals."
                ),
            },
        }

    @staticmethod
    def _build_alerts(
        *,
        infra: dict[str, str],
        health_score: float | None,
        success_pct: float | None,
        reject_pct: float | None,
        risk_pct: float | None,
        avg_broker: float | None,
        avg_gateway: float | None,
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        for name, state in infra.items():
            if state == "down":
                alerts.append(
                    {
                        "severity": "critical",
                        "code": f"{name}_down",
                        "message": f"{name} availability is down",
                    }
                )
            elif state == "degraded":
                alerts.append(
                    {
                        "severity": "warning",
                        "code": f"{name}_degraded",
                        "message": f"{name} availability is degraded",
                    }
                )
        if health_score is not None and health_score < 75:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "health_score_low",
                    "message": f"System health score {health_score}",
                }
            )
        if success_pct is not None and success_pct < 90 and reject_pct is not None:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "execution_success_low",
                    "message": (
                        f"Execution success {success_pct}% "
                        f"(reject {reject_pct}%)"
                    ),
                }
            )
        if risk_pct is not None and risk_pct >= 25:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "risk_reject_elevated",
                    "message": f"Risk reject rate {risk_pct}%",
                }
            )
        if avg_broker is not None and avg_broker >= 1500:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "broker_latency_high",
                    "message": f"Avg broker latency {avg_broker:.0f} ms",
                }
            )
        if avg_gateway is not None and avg_gateway >= 800:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "gateway_latency_high",
                    "message": f"Avg gateway latency {avg_gateway:.0f} ms",
                }
            )
        return alerts

    async def _load_audits(self, *, limit: int) -> list[Any]:
        if self.execution_audit_uow_factory is None:
            return []
        try:
            async with self.execution_audit_uow_factory() as uow:
                return await uow.audits.list_recent(limit=limit)
        except Exception as exc:
            logger.warning("rc1_telemetry_audits_failed", error=str(exc))
            return []

    async def _probe_infra(self) -> dict[str, str]:
        out = {
            "gateway": "unknown",
            "railway": "unknown",
            "cloudflare": "unknown",
            "mt5": "unknown",
        }
        try:
            from app.application.services.institutional_live_probes import (
                LiveProbeCollector,
            )

            collector = LiveProbeCollector(settings=self.settings)
            probes = collector.collect()
            out["gateway"] = "up" if probes.gateway_available else "down"
            out["mt5"] = "up" if probes.mt5_connected else "down"
            out["cloudflare"] = "up" if probes.cloudflare_tunnel_up else "down"
            out["railway"] = "up" if probes.railway_api_up else "down"
        except Exception as exc:
            logger.warning("rc1_telemetry_probe_failed", error=str(exc))
            # Process is answering — Railway at least reachable from this pod.
            out["railway"] = "up"
        if self.health_service is not None:
            try:
                report = await self.health_service.check()
                postgres = next(
                    (d for d in report.dependencies if d.name == "postgres"),
                    None,
                )
                if postgres is not None and postgres.status.value != "healthy":
                    out["railway"] = "degraded"
            except Exception as exc:
                logger.debug("rc1_telemetry_health_check_skipped", error=str(exc))
        return out
