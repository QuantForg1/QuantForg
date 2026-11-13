"""Portable MT5 initialize — IPC timeout (-10005) retries once then fails closed."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.mt5_worker_agent import mt5_session


def test_ipc_timeout_retries_once_then_succeeds(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"x")
    portable = tmp_path / "portable"
    portable.write_text("1", encoding="utf-8")

    calls = {"n": 0}

    class FakeMt5:
        def initialize(self, path: str = "") -> bool:
            _ = path
            calls["n"] += 1
            return calls["n"] >= 2

        def last_error(self):
            if calls["n"] < 2:
                return (-10005, "IPC timeout")
            return (1, "Success")

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(mt5_session, "_import_mt5", lambda: FakeMt5())
    monkeypatch.setattr(mt5_session, "assert_worker_terminal_path", lambda p: Path(p))
    monkeypatch.setattr(mt5_session.time, "sleep", lambda _s: None)
    assert mt5_session.initialize_portable(exe) is True
    assert calls["n"] == 2


def test_ipc_timeout_persists_fail_closed(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"x")

    class FakeMt5:
        def initialize(self, path: str = "") -> bool:
            _ = path
            return False

        def last_error(self):
            return (-10005, "IPC timeout")

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(mt5_session, "_import_mt5", lambda: FakeMt5())
    monkeypatch.setattr(mt5_session, "assert_worker_terminal_path", lambda p: Path(p))
    monkeypatch.setattr(mt5_session.time, "sleep", lambda _s: None)
    assert mt5_session.initialize_portable(exe) is False


def test_authenticate_records_trade_mode(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"x")
    info = SimpleNamespace(
        login=12345,
        server="XMGlobal-MT5",
        name="Demo",
        balance=1000.0,
        equity=1000.0,
        currency="USD",
        trade_allowed=True,
        trade_expert=True,
        trade_mode=0,
    )
    mt5 = MagicMock()
    mt5.initialize.return_value = True
    mt5.last_error.return_value = (1, "Success")
    mt5.login.return_value = True
    mt5.account_info.return_value = info
    mt5.terminal_info.return_value = SimpleNamespace(tradeapi_disabled=False)
    mt5.symbols_get.return_value = [SimpleNamespace(name="EURUSD")]
    mt5.symbol_select.return_value = True
    mt5.symbol_info_tick.return_value = SimpleNamespace(bid=1.1)

    monkeypatch.setattr(mt5_session, "_import_mt5", lambda: mt5)
    monkeypatch.setattr(mt5_session, "assert_worker_terminal_path", lambda p: Path(p))
    result = mt5_session.authenticate_and_verify(
        terminal_exe=exe,
        login=12345,
        password="demo-pass",
        server="XMGlobal-MT5",
    )
    assert result.ok is True
    assert result.trade_mode == 0
    assert result.server == "XMGlobal-MT5"
    assert "password" not in result.error.lower()
