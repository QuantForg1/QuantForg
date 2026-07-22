"""Unit tests — symbols pagination + catalogue cache hardening."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest

from app.application.dto.mt5 import MT5ConnectCommand
from app.application.use_cases.mt5 import ConnectMT5UseCase, ListMT5SymbolsUseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.brokers.mt5.metrics import gateway_metrics
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _wire() -> tuple[Any, MT5Adapter, RecordAuditEventUseCase]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client())
    return mt5_factory, adapter, audit


@pytest.mark.unit
class TestSymbolsPagination:
    @pytest.mark.asyncio
    async def test_paginated_search_without_quotes(self) -> None:
        factory, adapter, audit = _wire()
        user_id = uuid4()
        await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_id,
                login=1001,
                password="secret",
                server="Demo-Server",
            )
        )
        page = await ListMT5SymbolsUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_id, q="XAU", limit=5, offset=0, include_quotes=False)
        assert page.total >= 1
        assert len(page.items) <= 5
        assert all(i.bid is None and i.ask is None for i in page.items)
        assert any(i.code == "XAUUSD" for i in page.items)


@pytest.mark.unit
class TestGatewayCatalogueCache:
    def test_list_symbols_does_not_fan_out_quotes_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = GatewayMT5Client(
            base_url="https://example.trycloudflare.com",
            token="test-token",
        )
        client._connected = True
        calls: list[str] = []

        def fake_request(
            method: str,
            path: str,
            *,
            json_body: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
            auth: bool = True,
        ) -> dict[str, Any]:
            calls.append(path)
            if path == "/symbols":
                return {
                    "items": [
                        {"code": "XAUUSD", "description": "Gold", "digits": 3},
                        {"code": "XAGUSD", "description": "Silver", "digits": 3},
                    ]
                }
            raise AssertionError(f"unexpected path {path}")

        monkeypatch.setattr(client, "_request", fake_request)
        rows = client.list_symbols(include_quotes=False)
        assert len(rows) == 2
        assert calls == ["/symbols"]
        # Second call hits catalogue cache — no extra gateway symbol fetch.
        calls.clear()
        rows2 = client.list_symbols(include_quotes=False)
        assert len(rows2) == 2
        assert calls == []
        snap = gateway_metrics.snapshot()
        assert snap["lifetime"]["cache_hits"] >= 1


@pytest.mark.unit
class TestGatewayTransportMetrics:
    def test_request_records_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = GatewayMT5Client(
            base_url="https://example.trycloudflare.com",
            token="test-token",
        )
        before = gateway_metrics.snapshot()["lifetime"]["requests"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "mt5": {}})

        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(
            client,
            "_build_http_client",
            lambda: httpx.Client(
                transport=transport,
                follow_redirects=True,
                timeout=5.0,
            ),
        )
        data = client._request("GET", "/health", auth=False)
        assert data.get("status") == "ok"
        after = gateway_metrics.snapshot()["lifetime"]["requests"]
        assert after >= before + 1
