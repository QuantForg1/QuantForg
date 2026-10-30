"""Terminal AutoTrading vs account trade_allowed — never confuse the two."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.auto_trading_status import (
    _apply_health_payload_flags,
    _empty_enrich,
)
from app.application.services.ite_cycle_market_context import (
    _read_mt5_autotrading_enabled,
)
from app.application.services.live_trading_control_service import (
    _overlay_mt5_open_position_count,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _adapter_with_health(payload: dict) -> MagicMock:
    gw = MagicMock()
    gw.gateway_health.return_value = payload
    adapter = MagicMock()
    adapter.client = gw
    adapter._client = gw
    return adapter


def test_terminal_autotrading_true_ignores_account_trade_allowed_false() -> None:
    adapter = _adapter_with_health(
        {
            "status": "ok",
            "mt5": {
                "connected": True,
                "trade_allowed": False,
                "account_trade_allowed": False,
                "mt5_autotrading_enabled": True,
                "terminal_trade_allowed": True,
            },
        }
    )
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is True
    assert diag["mt5_autotrading_source"] == "mt5.mt5_autotrading_enabled"
    assert diag["mt5_account_trade_allowed"] is False
    assert diag["mt5_autotrading_known"] is True


def test_health_probe_timeout_uses_session_status_flag() -> None:
    """A 500ms /health ceiling leaves the toolbar null. Session status has it."""
    adapter = _adapter_with_health(
        {
            "status": "ok",
            "mt5": {
                "connected": True,
                "degraded": True,
                "probe": "async_ceiling",
                "trade_allowed": None,
                "terminal_trade_allowed": None,
                "mt5_autotrading_enabled": None,
            },
        }
    )
    adapter.client.session_status.side_effect = AttributeError("use _request")
    adapter.client._request.return_value = {
        "connected": True,
        "health": {
            "probe": "live",
            "trade_allowed": True,
            "mt5_autotrading_enabled": True,
            "terminal_trade_allowed": True,
        },
    }
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is True
    assert diag["mt5_autotrading_known"] is True
    assert diag["mt5_autotrading_source"] == "session_status.mt5_autotrading_enabled"
    assert diag["autotrading_health_via"] == "session_status"
    adapter.client._request.assert_called_once_with("GET", "/session/status")


def test_health_probe_timeout_keeps_explicit_session_status_false() -> None:
    adapter = _adapter_with_health(
        {
            "status": "ok",
            "mt5": {
                "probe": "async_ceiling",
                "mt5_autotrading_enabled": None,
                "terminal_trade_allowed": None,
            },
        }
    )
    adapter.client.session_status.return_value = {
        "health": {"mt5_autotrading_enabled": False, "terminal_trade_allowed": False}
    }
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is False
    assert diag["mt5_autotrading_known"] is True
    assert diag["mt5_autotrading_source"] == "session_status.mt5_autotrading_enabled"


def test_explicit_health_false_is_not_replaced_by_session_status() -> None:
    adapter = _adapter_with_health(
        {
            "status": "ok",
            "mt5": {"mt5_autotrading_enabled": False, "terminal_trade_allowed": False},
        }
    )
    adapter.client.session_status.return_value = {
        "health": {"mt5_autotrading_enabled": True}
    }
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is False
    assert diag["mt5_autotrading_source"] == "mt5.mt5_autotrading_enabled"
    adapter.client.session_status.assert_not_called()


def test_session_status_account_trade_allowed_alone_stays_unknown() -> None:
    adapter = _adapter_with_health(
        {"status": "ok", "mt5": {"probe": "async_ceiling", "trade_allowed": True}}
    )
    adapter.client.session_status.return_value = {
        "health": {"trade_allowed": True, "account_trade_allowed": True}
    }
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is None
    assert diag["mt5_autotrading_known"] is False


def test_account_trade_allowed_alone_is_unknown_not_autotrading() -> None:
    adapter = _adapter_with_health(
        {
            "status": "ok",
            "mt5": {"connected": True, "trade_allowed": True},
        }
    )
    diag: dict = {}
    assert _read_mt5_autotrading_enabled(adapter, diag) is None
    assert diag.get("mt5_autotrading_known") is False
    assert diag.get("mt5_account_trade_allowed") is True
    assert diag.get("mt5_autotrading_source") != "mt5.trade_allowed"


def test_status_enrich_does_not_map_account_trade_allowed_to_autotrading() -> None:
    out = _empty_enrich()
    _apply_health_payload_flags(
        out,
        {
            "mt5": {
                "connected": True,
                "trade_allowed": False,
                "mt5_autotrading_enabled": True,
                "terminal_trade_allowed": True,
            }
        },
    )
    assert out["mt5_autotrading_enabled"] is True


def test_overlay_open_positions_counts_live_mt5_rows() -> None:
    adapter = MagicMock()
    adapter.list_positions.return_value = [
        SimpleNamespace(ticket=578387625, volume="0.01", symbol="XAUUSD"),
        SimpleNamespace(ticket=1, volume="0", symbol="EURUSD"),
    ]
    out: dict = {"open_positions": 0}
    _overlay_mt5_open_position_count(out, adapter)
    assert out["open_positions"] == 1
    assert out["open_positions_source"] == "mt5_list_positions"
