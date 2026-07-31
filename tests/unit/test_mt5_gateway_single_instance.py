"""Unit tests — MT5 Gateway single-instance protection (pre-uvicorn gate)."""

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
    port_can_bind_exclusively,
)


def _health_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "status": "ok",
        "service": "mt5-gateway",
        "gateway_version": "1.1.8",
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
        gateway_version="1.1.8",
        mt5_status="connected",
        broker="Weltrade-Demo",
        session="attached",
    )
    msg = format_already_running_message(pid=4242, health=health)
    assert "QuantForg MT5 Gateway is already running." in msg
    assert "PID: 4242" in msg
    assert "Gateway Version: 1.1.8" in msg
    assert "MT5 Status: connected" in msg
    assert "Broker: Weltrade-Demo" in msg
    assert "Session: attached" in msg


@pytest.mark.unit
def test_port_can_bind_exclusively_false_on_oserror() -> None:
    sock = MagicMock()
    sock.bind.side_effect = OSError(10048, "Address already in use")
    with patch(
        "services.mt5_gateway.single_instance.socket.socket", return_value=sock
    ):
        assert port_can_bind_exclusively("0.0.0.0", 8765) is False
    sock.close.assert_called()


@pytest.mark.unit
def test_port_can_bind_exclusively_true() -> None:
    sock = MagicMock()
    with patch(
        "services.mt5_gateway.single_instance.socket.socket", return_value=sock
    ):
        assert port_can_bind_exclusively("127.0.0.1", 8765) is True
    sock.bind.assert_called()
    sock.close.assert_called()


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
    assert snap.gateway_version == "1.1.8"
    assert snap.mt5_status == "connected"
    assert snap.broker == "Weltrade-Demo"
    assert snap.session == "attached"


@pytest.mark.unit
def test_ensure_single_instance_exits_when_port_busy_and_healthy() -> None:
    health = GatewayHealthSnapshot(
        ok=True,
        gateway_version="1.1.8",
        mt5_status="connected",
        broker="Weltrade-Demo",
        session="attached",
        raw=_health_payload(),
    )
    with (
        patch(
            "services.mt5_gateway.single_instance.port_can_bind_exclusively",
            return_value=False,
        ),
        patch(
            "services.mt5_gateway.single_instance.fetch_gateway_health",
            return_value=health,
        ),
        patch(
            "services.mt5_gateway.single_instance.find_listening_pid",
            return_value=99,
        ),
    ):
        action = ensure_single_instance(host="0.0.0.0", port=8765, restart=False)
    assert action == "already_running"


@pytest.mark.unit
def test_ensure_single_instance_starts_when_exclusive_bind_ok() -> None:
    with patch(
        "services.mt5_gateway.single_instance.port_can_bind_exclusively",
        return_value=True,
    ):
        action = ensure_single_instance(host="0.0.0.0", port=8765)
    assert action == "start"


@pytest.mark.unit
def test_ensure_single_instance_restarts_unhealthy_occupant() -> None:
    bad = GatewayHealthSnapshot(ok=False, error="boom")
    with (
        patch(
            "services.mt5_gateway.single_instance.port_can_bind_exclusively",
            side_effect=[False, True, True],
        ),
        patch(
            "services.mt5_gateway.single_instance.fetch_gateway_health",
            return_value=bad,
        ),
        patch(
            "services.mt5_gateway.single_instance.find_listening_pid",
            return_value=55,
        ),
        patch(
            "services.mt5_gateway.single_instance.stop_gateway_process"
        ) as stop,
        patch(
            "services.mt5_gateway.single_instance.wait_for_port_release",
            return_value=True,
        ),
    ):
        action = ensure_single_instance(host="0.0.0.0", port=8765)
    assert action == "start"
    stop.assert_called_once_with(55)


@pytest.mark.unit
def test_ensure_single_instance_restart_flag_stops_even_if_healthy() -> None:
    with (
        patch(
            "services.mt5_gateway.single_instance.port_can_bind_exclusively",
            side_effect=[False, True, True],
        ),
        patch(
            "services.mt5_gateway.single_instance.find_listening_pid",
            return_value=77,
        ),
        patch(
            "services.mt5_gateway.single_instance.stop_gateway_process"
        ) as stop,
        patch(
            "services.mt5_gateway.single_instance.wait_for_port_release",
            return_value=True,
        ),
    ):
        action = ensure_single_instance(
            host="0.0.0.0", port=8765, restart=True
        )
    assert action == "start"
    stop.assert_called_once_with(77)


@pytest.mark.unit
def test_main_run_never_calls_uvicorn_when_already_running() -> None:
    from services.mt5_gateway import main as gw_main

    with (
        patch(
            "services.mt5_gateway.single_instance.ensure_single_instance",
            return_value="already_running",
        ),
        patch(
            "services.mt5_gateway.single_instance.read_gateway_bind_settings",
            return_value=("0.0.0.0", 8765),
        ),
        patch.object(gw_main, "_run_uvicorn") as uv,
    ):
        with pytest.raises(SystemExit) as exc:
            gw_main.run([])
        assert exc.value.code == 0
        uv.assert_not_called()


@pytest.mark.unit
def test_main_run_aborts_if_bind_still_blocked_after_gate() -> None:
    """Fail-closed: never reach uvicorn if exclusive bind still fails."""
    from services.mt5_gateway import main as gw_main

    with (
        patch(
            "services.mt5_gateway.single_instance.ensure_single_instance",
            return_value="start",
        ),
        patch(
            "services.mt5_gateway.single_instance.read_gateway_bind_settings",
            return_value=("0.0.0.0", 8765),
        ),
        patch(
            "services.mt5_gateway.single_instance.port_can_bind_exclusively",
            return_value=False,
        ),
        patch.object(gw_main, "_run_uvicorn") as uv,
    ):
        with pytest.raises(SystemExit) as exc:
            gw_main.run([])
        assert exc.value.code == 1
        uv.assert_not_called()


@pytest.mark.unit
def test_main_run_starts_uvicorn_only_after_gate() -> None:
    from services.mt5_gateway import main as gw_main

    with (
        patch(
            "services.mt5_gateway.single_instance.ensure_single_instance",
            return_value="start",
        ),
        patch(
            "services.mt5_gateway.single_instance.read_gateway_bind_settings",
            return_value=("0.0.0.0", 8765),
        ),
        patch(
            "services.mt5_gateway.single_instance.port_can_bind_exclusively",
            return_value=True,
        ),
        patch.object(gw_main, "_run_uvicorn") as uv,
    ):
        gw_main.run([])
        uv.assert_called_once_with(host="0.0.0.0", port=8765)
