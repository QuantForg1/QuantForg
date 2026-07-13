"""Unit tests for Gateway Manager / cloud infrastructure."""

from __future__ import annotations

import pytest

from app.application.services.gateway_manager import GatewayManagerService
from app.domain.cloud.registry import GatewayRegistry
from app.domain.cloud.routing import route_gateway
from app.domain.cloud.types import GatewayStatus


@pytest.mark.unit
class TestGatewayManager:
    def setup_method(self) -> None:
        self.svc = GatewayManagerService(
            registry=GatewayRegistry(), heartbeat_timeout_seconds=30.0
        )

    def test_register_list_and_route(self) -> None:
        created = self.svc.register(
            hostname="win1",
            broker="exness",
            region="eu",
            version="1.0.0",
            ip_allowlist=["127.0.0.1"],
        )
        assert "gateway_token" in created
        gid = created["gateway"]["gateway_id"]
        token = created["gateway_token"]

        hb = self.svc.ingest_heartbeat(
            gateway_id=gid,
            token=token,
            client_ip="127.0.0.1",
            nonce="nonce-1-unique",
            latency_ms=12.0,
            metrics={"cpu_percent": 10, "connected_users": 2},
            status="online",
        )
        assert hb["ok"] is True

        decision = self.svc.route(broker="exness", region="eu")
        assert decision["gateway_id"] == gid
        assert decision["reason"] == "broker+region+health"

        dash = self.svc.dashboard()
        assert dash["health"]["online"] == 1
        assert dash["connected_users"] == 2

    def test_replay_and_bad_token(self) -> None:
        created = self.svc.register(hostname="w", broker="xm", region="us")
        gid = created["gateway"]["gateway_id"]
        token = created["gateway_token"]
        assert self.svc.ingest_heartbeat(
            gateway_id=gid,
            token=token,
            client_ip="127.0.0.1",
            nonce="same-nonce",
            latency_ms=1,
        )["ok"]
        replay = self.svc.ingest_heartbeat(
            gateway_id=gid,
            token=token,
            client_ip="127.0.0.1",
            nonce="same-nonce",
            latency_ms=1,
        )
        assert replay["ok"] is False
        assert replay["error"] == "replay_detected"

        bad = self.svc.ingest_heartbeat(
            gateway_id=gid,
            token="wrong-token-value-here",
            client_ip="127.0.0.1",
            nonce="another-nonce",
            latency_ms=1,
        )
        assert bad["ok"] is False

    def test_failover_to_degraded(self) -> None:
        a = self.svc.register(hostname="a", broker="weltrade", region="eu")
        b = self.svc.register(hostname="b", broker="weltrade", region="eu")
        # mark a online high latency degraded, b offline
        ga = self.svc.registry.get(a["gateway"]["gateway_id"])
        gb = self.svc.registry.get(b["gateway"]["gateway_id"])
        assert ga and gb
        ga.status = GatewayStatus.DEGRADED
        ga.latency_ms = 50
        gb.status = GatewayStatus.OFFLINE
        self.svc.registry.upsert(ga)
        self.svc.registry.upsert(gb)
        decision = route_gateway(self.svc.registry, broker="weltrade")
        assert decision.gateway_id == ga.gateway_id
        assert decision.fallback_used is True

    def test_rotate_and_replace(self) -> None:
        created = self.svc.register(hostname="old", broker="pepperstone", region="au")
        gid = created["gateway"]["gateway_id"]
        rotated = self.svc.rotate_token(gid)
        assert rotated is not None
        assert rotated["gateway_token"] != created["gateway_token"]
        replaced = self.svc.replace_gateway(
            old_gateway_id=gid, hostname="new-host"
        )
        assert replaced is not None
        assert replaced["replaced"] == gid
        old = self.svc.get_gateway(gid)
        assert old is not None
        assert old["status"] == GatewayStatus.DRAINING.value
