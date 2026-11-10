"""Phase 8 — portable slots must never attach to Weltrade LIVE Program Files."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.mt5_worker_agent import paths as mt5_paths

pytestmark = [pytest.mark.unit]


def test_refuse_program_files_live_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    live = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    with pytest.raises(ValueError, match="Refusing to use the LIVE"):
        mt5_paths.assert_worker_terminal_path(live)


def test_allow_portable_slot_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path))
    portable = tmp_path / "demo-a" / "terminal64.exe"
    portable.parent.mkdir(parents=True, exist_ok=True)
    portable.write_bytes(b"mz")
    assert mt5_paths.assert_worker_terminal_path(portable) == portable.resolve()


def test_override_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", raising=False)
    assert mt5_paths.allow_live_terminal_override() is False
