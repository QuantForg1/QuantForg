"""Unit tests for MT5 domain entities."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.mt5 import (
    MT5AccountInfo,
    MT5Connection,
    MT5Server,
    MT5Terminal,
)
from app.domain.enums.mt5 import MT5ConnectionStatus


@pytest.mark.unit
class TestMT5Domain:
    def test_connection_lifecycle(self) -> None:
        conn = MT5Connection.create(
            user_id=uuid4(), login=42, server="Demo", terminal_path="/mt5"
        )
        assert conn.status is MT5ConnectionStatus.DISCONNECTED
        conn.mark_initializing()
        conn.mark_logging_in()
        conn.mark_connected(
            session_ref="sess-1",
            terminal_build=3815,
            terminal_version="5.0.3815",
            latency_ms=3.2,
        )
        assert conn.connected is True
        assert conn.login_status == "logged_in"
        conn.mark_heartbeat(latency_ms=4.0)
        assert conn.latency_ms == 4.0
        assert conn.last_heartbeat_at is not None
        conn.mark_reconnecting()
        assert conn.status is MT5ConnectionStatus.RECONNECTING
        conn.mark_disconnected()
        assert conn.connected is False
        assert "encrypted_payload" not in conn.to_dict()

    def test_terminal_server_account_value_objects(self) -> None:
        terminal = MT5Terminal(build=3815, connected=True)
        assert terminal.to_dict()["build"] == 3815
        server = MT5Server(name="Demo-Server", company="Broker")
        assert server.name == "Demo-Server"
        account = MT5AccountInfo(
            login=7,
            name="Demo",
            server="Demo-Server",
            balance=Decimal("1000"),
            equity=Decimal("1000"),
        )
        assert account.to_dict()["login"] == 7

    def test_invalid_login_rejected(self) -> None:
        with pytest.raises(ValueError):
            MT5AccountInfo(login=0, name="x", server="s")
