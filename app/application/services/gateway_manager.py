"""Gateway Manager service — registry, routing, HA, metrics, security."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.cloud.registry import (
    GatewayRegistry,
    generate_gateway_token,
    hash_token,
)
from app.domain.cloud.routing import mark_stale_offline, route_gateway
from app.domain.cloud.types import (
    GatewayCapabilities,
    GatewayMetrics,
    GatewayRecord,
    GatewayStatus,
    new_gateway_id,
    utc_now,
)

CLOUD_VERSION = "1.0.0"
COMPATIBLE_GATEWAY_VERSIONS = frozenset({"1.0.0", "1.0.1", "1.1.0"})


@dataclass
class GatewayManagerService:
    """Cloud-side manager for Windows MT5 gateways (additive)."""

    registry: GatewayRegistry = field(default_factory=GatewayRegistry)
    heartbeat_timeout_seconds: float = 30.0

    def register(
        self,
        *,
        hostname: str,
        broker: str,
        region: str,
        version: str = "1.0.0",
        base_url: str = "",
        capabilities: dict[str, Any] | None = None,
        ip_allowlist: list[str] | None = None,
        gateway_token: str | None = None,
        gateway_id: str | None = None,
    ) -> dict[str, Any]:
        gid = gateway_id or new_gateway_id()
        token = gateway_token or generate_gateway_token()
        now = utc_now()
        compatible = version in COMPATIBLE_GATEWAY_VERSIONS
        record = GatewayRecord(
            gateway_id=gid,
            hostname=hostname.strip(),
            broker=broker.strip().lower(),
            region=region.strip() or "unknown",
            version=version.strip() or "1.0.0",
            status=GatewayStatus.UNKNOWN,
            capabilities=GatewayCapabilities.from_dict(capabilities),
            base_url=base_url.strip(),
            ip_allowlist=tuple(ip_allowlist or ()),
            token_fingerprint=hash_token(token)[:12],
            token_version=1,
            compatible=compatible,
            created_at=now,
            updated_at=now,
        )
        self.registry.upsert(record, token_hash=hash_token(token))
        return {
            "gateway": record.to_dict(),
            "gateway_token": token,
            "note": (
                "Store gateway_token only on the Windows host. "
                "Never put broker credentials in Railway."
            ),
            "cloud_version": CLOUD_VERSION,
        }

    def list_gateways(self) -> dict[str, Any]:
        self.refresh_ha()
        return {
            "items": [g.to_dict() for g in self.registry.all_gateways()],
            "cloud_version": CLOUD_VERSION,
        }

    def get_gateway(self, gateway_id: str) -> dict[str, Any] | None:
        rec = self.registry.get(gateway_id)
        return rec.to_dict() if rec else None

    def deregister(self, gateway_id: str) -> bool:
        return self.registry.remove(gateway_id)

    def rotate_token(self, gateway_id: str) -> dict[str, Any] | None:
        rec = self.registry.get(gateway_id)
        if rec is None:
            return None
        token = generate_gateway_token()
        self.registry.set_token_hash(gateway_id, hash_token(token))
        updated = self.registry.get(gateway_id)
        return {
            "gateway_id": gateway_id,
            "gateway_token": token,
            "token_version": updated.token_version if updated else None,
            "note": "Update MT5_GATEWAY_TOKEN on the Windows host immediately.",
        }

    def ingest_heartbeat(
        self,
        *,
        gateway_id: str,
        token: str,
        client_ip: str,
        nonce: str,
        latency_ms: float | None = None,
        metrics: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if not self.registry.rate_limit(f"hb:{gateway_id}", limit=120):
            return {"ok": False, "error": "rate_limited"}
        if not self.registry.ip_allowed(gateway_id, client_ip):
            self.registry.record_failure(gateway_id, "ip_denied", client_ip)
            return {"ok": False, "error": "ip_not_allowlisted"}
        if not self.registry.verify_token(gateway_id, token):
            self.registry.record_failure(gateway_id, "auth_failed", "bad token")
            return {"ok": False, "error": "invalid_token"}
        if not self.registry.allow_nonce(nonce):
            self.registry.record_failure(gateway_id, "replay_detected", nonce[:16])
            return {"ok": False, "error": "replay_detected"}

        rec = self.registry.get(gateway_id)
        if rec is None:
            return {"ok": False, "error": "unknown_gateway"}

        now = utc_now()
        rec.last_heartbeat_at = now
        rec.last_seen_at = now
        if latency_ms is not None:
            rec.latency_ms = float(latency_ms)
        if metrics:
            rec.metrics = GatewayMetrics.from_dict(metrics)
            if rec.metrics.latency_ms is not None and latency_ms is None:
                rec.latency_ms = rec.metrics.latency_ms
            if rec.metrics.heartbeat_ms is None and latency_ms is not None:
                rec.metrics.heartbeat_ms = float(latency_ms)
        if status:
            try:
                rec.status = GatewayStatus(status.strip().lower())
            except ValueError:
                rec.status = GatewayStatus.ONLINE
        else:
            rec.status = GatewayStatus.ONLINE
        if rec.latency_ms is not None and rec.latency_ms > 1500:
            rec.status = GatewayStatus.DEGRADED
            rec.failure_reason = "degraded_latency"
        else:
            rec.failure_reason = ""
        rec.updated_at = now
        self.registry.upsert(rec)
        return {"ok": True, "gateway": rec.to_dict()}

    def route(
        self,
        *,
        broker: str,
        region: str | None = None,
        capability: str | None = None,
    ) -> dict[str, Any]:
        self.refresh_ha()
        decision = route_gateway(
            self.registry,
            broker=broker,
            region=region,
            require_capability=capability,
        )
        return decision.to_dict()

    def refresh_ha(self) -> dict[str, Any]:
        changed = mark_stale_offline(
            self.registry, timeout_seconds=self.heartbeat_timeout_seconds
        )
        return {
            "marked_offline": changed,
            "timeout_seconds": self.heartbeat_timeout_seconds,
        }

    def replace_gateway(
        self,
        *,
        old_gateway_id: str,
        hostname: str,
        broker: str | None = None,
        region: str | None = None,
        version: str = "1.0.0",
        base_url: str = "",
    ) -> dict[str, Any] | None:
        old = self.registry.get(old_gateway_id)
        if old is None:
            return None
        old.status = GatewayStatus.DRAINING
        old.updated_at = utc_now()
        self.registry.upsert(old)
        created = self.register(
            hostname=hostname,
            broker=broker or old.broker,
            region=region or old.region,
            version=version or old.version,
            base_url=base_url or old.base_url,
            capabilities=old.capabilities.to_dict(),
            ip_allowlist=list(old.ip_allowlist),
        )
        created["replaced"] = old_gateway_id
        created["note"] = (
            "Old gateway set to draining. Point traffic to the new gateway_id "
            "and retire the old Windows host."
        )
        return created

    def dashboard(self) -> dict[str, Any]:
        self.refresh_ha()
        items = [g.to_dict() for g in self.registry.all_gateways()]
        online = [g for g in items if g["status"] == GatewayStatus.ONLINE.value]
        offline = [g for g in items if g["status"] == GatewayStatus.OFFLINE.value]
        degraded = [g for g in items if g["status"] == GatewayStatus.DEGRADED.value]
        broker_map: dict[str, list[str]] = {}
        for g in items:
            broker_map.setdefault(str(g["broker"]), []).append(str(g["gateway_id"]))
        connected_users = sum(
            int((g.get("metrics") or {}).get("connected_users") or 0) for g in items
        )
        return {
            "title": "Cloud Operations",
            "cloud_version": CLOUD_VERSION,
            "registered_gateways": items,
            "broker_mapping": broker_map,
            "health": {
                "online": len(online),
                "offline": len(offline),
                "degraded": len(degraded),
                "unknown": len(items) - len(online) - len(offline) - len(degraded),
            },
            "versions": sorted({str(g["version"]) for g in items}),
            "latency": [
                {
                    "gateway_id": g["gateway_id"],
                    "latency_ms": g.get("latency_ms"),
                    "hostname": g.get("hostname"),
                }
                for g in items
            ],
            "heartbeat": [
                {
                    "gateway_id": g["gateway_id"],
                    "heartbeat": g.get("heartbeat"),
                    "status": g.get("status"),
                }
                for g in items
            ],
            "connected_users": connected_users,
            "recent_failures": self.registry.recent_failures(limit=40),
            "notes": (
                "Gateways report heartbeats with mutual token + nonce. "
                "Broker credentials stay on Windows hosts — never Railway."
            ),
        }
