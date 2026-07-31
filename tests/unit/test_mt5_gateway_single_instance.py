"""Unit tests — MT5 Gateway single-instance protection."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.mt5_gateway.single_instance import (
    GatewayHealthSnapshot,
    ensure_single_instance,
    fetch_gateway_health,
    format_already_running_message,
    port_is_listening,
    probe_listener,
)


def _health_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "status": "ok",
        "service": "mt5-gateway",
        "gateway_version": "1.1.7",
        "mt5": {
            "connected": True,
            "session_mode": "attached",
            "server": "Weltrade-Demo",
            "login_status": "connected",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_format_already_running_message() -> None:
    health = GatewayHealthSnapshot(
        ok=True,
        gateway_version="1.1.7",
        mt5_status="connected",
        broker="Weltrade-Demo",
        session="attached",
    )
    msg = format_already_running_message(pid=4242, health=health)
    assert "QuantForg MT5 Gateway is already running." in msg
    assert "PID: 4242" in msg
    assert "Gateway Version: 1.1.7" in msg
    assert "MT5 Status: connected" in msg
    assert "Broker: Weltrade-Demo" in msg
    assert "Session: attached" in msg


@pytest.mark.unit
def test_port_is_listening_false_when_refused() -> None:
    with patch(
        "services.mt5_gateway.single_instance.socket.create_connection",
        side_effect=ConnectionRefusedError(),
    ):
        assert port_is_listening("127.0.0.1", 8765) is False


@pytest.mark.unit
def test_fetch_gateway_health_parses_quantforg_payload() -> None:
    payload = _health_payload()
    body = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    with patch("services.mt5_gateway.single_instance.urlopen", return_value=resp):
        snap = fetch_gateway_health("127.0.0.1", 8765)
    assert snap.ok is True
    assert snap.gateway_version == "1.1.7"
    assert snap.mt5_status == "connected"
    assert snap.broker == "Weltrade-Demo"
    assert snap.session == "attached"


@pytest.mark.unit
def test_fetch_gateway_health_rejects_foreign_service() -> None:
    body = json.dumps({"status": "ok", "service": "other"}).encode()
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    with patch("services.mt5_gateway.single_instance.urlopen", return_value=resp):
        snap = fetch_gateway_health("127.0.0.1", 8765)
    assert snap.ok is False
    assert "not a QuantForg" in (snap.error or "")


@pytest.mark.unit
def test_ensure_single_instance_exits_when_healthy() -> None:
    health = GatewayHealthSnapshot(
        ok=True,
        gateway_version="1.1.7",
        mt5_status="connected",
        broker="Weltrade-Demo",
        session="attached",
        raw=_health_payload(),
    )
    probe = SimpleNamespace(listening=True, pid=99, health=health)
    with (
        patch(
            "services.mt5_gateway.single_instance.probe_listener",
            return_value=probe,
        ),
        patch(
            "services.mt5_gateway.single_instance.fetch_gateway_health",
            return_value=health,
        ),
    ):
        action = ensure_single_instance(host="127.0.0.1", port=8765, restart=False)
    assert action == "already_running"


@pytest.mark.unit
def test_ensure_single_instance_starts_when_free() -> None:
    probe = SimpleNamespace(listening=False, pid=None, health=None)
    with patch(
        "services.mt5_gateway.single_instance.probe_listener", return_value=probe
    ):
        action = ensure_single_instance(host="127.0.0.1", port=8765)
    assert action == "start"


@pytest.mark.unit
def test_ensure_single_instance_restarts_unhealthy() -> None:
    bad = GatewayHealthSnapshot(ok=False, error="connection refused mid-flight")
    probe = SimpleNamespace(listening=True, pid=55, health=bad)
    with (
        patch(
            "services.mt5_gateway.single_instance.probe_listener",
            return_value=probe,
        ),
        patch("services.mt5_gateway.single_instance.stop_gateway_process") as stop,
        patch(
            "services.mt5_gateway.single_instance.wait_for_port_release",
            return_value=True,
        ),
    ):
        action = ensure_single_instance(host="127.0.0.1", port=8765)
    assert action == "start"
    stop.assert_called_once_with(55)


@pytest.mark.unit
def test_ensure_single_instance_restart_flag_stops_healthy() -> None:
    health = GatewayHealthSnapshot(
        ok=True,
        gateway_version="1.1.7",
        mt5_status="connected",
        broker="X",
        session="attached",
    )
    probe = SimpleNamespace(listening=True, pid=77, health=health)
    with (
        patch(
            "services.mt5_gateway.single_instance.probe_listener",
            return_value=probe,
        ),
        patch("services.mt5_gateway.single_instance.stop_gateway_process") as stop,
        patch(
            "services.mt5_gateway.single_instance.wait_for_port_release",
            return_value=True,
        ),
    ):
        action = ensure_single_instance(host="127.0.0.1", port=8765, restart=True)
    assert action == "start"
    stop.assert_called_once_with(77)


@pytest.mark.unit
def test_main_run_exits_zero_when_already_running() -> None:
    from services.mt5_gateway import main as gw_main

    with (
        patch.object(gw_main, "ensure_single_instance", return_value="already_running"),
        patch.object(gw_main, "get_gateway_settings") as gs,
        patch.object(gw_main.uvicorn, "run") as uv,
    ):
        gs.return_value = SimpleNamespace(
            mt5_gateway_host="127.0.0.1", mt5_gateway_port=8765
        )
        with pytest.raises(SystemExit) as exc:
            gw_main.run([])
        assert exc.value.code == 0
        uv.assert_not_called()


@pytest.mark.unit
def test_main_run_starts_uvicorn_when_free() -> None:
    from services.mt5_gateway import main as gw_main

    with (
        patch.object(gw_main, "ensure_single_instance", return_value="start"),
        patch.object(gw_main, "get_gateway_settings") as gs,
        patch.object(gw_main.uvicorn, "run") as uv,
    ):
        gs.return_value = SimpleNamespace(
            mt5_gateway_host="0.0.0.0", mt5_gateway_port=8765
        )
        gw_main.run([])
        uv.assert_called_once()
        kwargs = uv.call_args.kwargs
        assert kwargs["port"] == 8765
        assert kwargs["reload"] is False
