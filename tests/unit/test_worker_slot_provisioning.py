"""Supervisor logs each slot into its own customer's account, honestly."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

pytestmark = [pytest.mark.unit]


class _Railway:
    def __init__(self, *, envelope: str = "ENV", ready_applied: bool = True) -> None:
        self.envelope = envelope
        self.ready_applied = ready_applied
        self.reports: list[dict[str, Any]] = []

    def get_assignment(self, *, worker_id: str) -> dict[str, Any]:
        return {"assignment": {"broker_account_id": "acct-" + worker_id}}

    def claim_sealed_credentials(self, *, worker_id: str) -> dict[str, Any]:
        if not self.envelope:
            return {
                "ok": True,
                "sealed": False,
                "error": "credential_material_unavailable",
            }
        return {"ok": True, "sealed_envelope": f"{self.envelope}:{worker_id}"}

    def report_verification(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.reports.append(payload)
        return {
            "ok": True,
            "worker_ready_applied": self.ready_applied and payload["ok"],
        }


def _sup(railway: _Railway, monkeypatch: pytest.MonkeyPatch) -> LocalWorkerSupervisor:
    monkeypatch.setenv("WORKER_SERVICE_TOKEN", "t" * 32)
    sup = LocalWorkerSupervisor(slot_ids=["a", "b"], railway=railway)  # type: ignore[arg-type]
    sup.states["a"].worker_id = "w-a"
    sup.states["b"].worker_id = "w-b"
    sup.terminal_exe_for = lambda slot: f"C:/slots/{slot}/terminal64.exe"  # type: ignore[method-assign]
    return sup


def _unwrap(
    *, service_token: str, worker_id: str, sealed_envelope: str
) -> dict[str, str]:
    assert sealed_envelope.endswith(worker_id)  # envelope bound to this worker
    login = {"w-a": "1001", "w-b": "2002"}[worker_id]
    return {
        "login": login,
        "server": "Demo-Srv",
        "secret": f"pw-{login}",
        "claim_id": "c",
    }


def _auth(trade_allowed: bool = True):
    calls: list[dict[str, Any]] = []

    def fn(*, terminal_exe: str, login: int, password: str, server: str) -> Any:
        calls.append({"exe": terminal_exe, "login": login, "password": password})
        return SimpleNamespace(
            ok=trade_allowed,
            trade_allowed=trade_allowed,
            login=login,
            server=server,
            balance=100.0,
            equity=100.0,
            currency="USD",
            market_data_ok=True,
            symbols_total=10,
            quote_symbol="XAUUSD",
            trade_mode=0,
            error="" if trade_allowed else "authenticated_trading_not_enabled",
        )

    fn.calls = calls  # type: ignore[attr-defined]
    return fn


def test_each_slot_uses_its_own_account_and_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rw = _Railway()
    sup = _sup(rw, monkeypatch)
    auth = _auth()
    out = sup.provision_assigned_accounts(authenticate=auth, unwrap=_unwrap)
    assert out["slots"]["a"]["ok"] and out["slots"]["b"]["ok"]
    by_exe = {c["exe"]: c["login"] for c in auth.calls}
    assert by_exe == {
        "C:/slots/a/terminal64.exe": 1001,
        "C:/slots/b/terminal64.exe": 2002,
    }
    assert all("pw-" not in str(r) for r in rw.reports)  # password never reported
    assert sup.states["a"].ready and sup.states["b"].ready


def test_trade_disabled_account_stays_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rw = _Railway()
    sup = _sup(rw, monkeypatch)
    sup.provision_assigned_accounts(
        authenticate=_auth(trade_allowed=False), unwrap=_unwrap
    )
    assert not sup.states["a"].ready
    assert sup.states["a"].last_error == "authenticated_trading_not_enabled"
    assert rw.reports[0]["ok"] is False and rw.reports[0]["trade_allowed"] is False


def test_no_vault_material_means_no_login_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rw = _Railway(envelope="")
    sup = _sup(rw, monkeypatch)
    auth = _auth()
    out = sup.provision_assigned_accounts(authenticate=auth, unwrap=_unwrap)
    assert auth.calls == []
    assert out["slots"]["a"]["error"] == "credential_material_unavailable"


def test_backend_refusal_keeps_slot_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    rw = _Railway(ready_applied=False)  # e.g. login mismatch on the backend
    sup = _sup(rw, monkeypatch)
    sup.provision_assigned_accounts(authenticate=_auth(), unwrap=_unwrap)
    assert not sup.states["a"].ready


def test_missing_service_token_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    rw = _Railway()
    sup = _sup(rw, monkeypatch)
    monkeypatch.delenv("WORKER_SERVICE_TOKEN")
    assert sup.provision_assigned_accounts(authenticate=_auth(), unwrap=_unwrap)[
        "error"
    ] == ("worker_service_token_missing")


def test_provision_guarded_does_not_block_on_stuck_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    import time as _time

    sup = _sup(_Railway(), monkeypatch)
    release = threading.Event()

    def _stuck(**_: object) -> dict[str, object]:
        release.wait(5)
        return {"ok": True, "slots": {}}

    monkeypatch.setattr(sup, "provision_assigned_accounts", _stuck)
    start = _time.monotonic()
    sup.provision_guarded(timeout_seconds=0.2)
    assert _time.monotonic() - start < 2.0
    # A second pass must not start while the first is still stuck.
    sup.provision_guarded(timeout_seconds=0.2)
    release.set()


def test_provision_guarded_heartbeats_while_login_is_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    sup = _sup(_Railway(), monkeypatch)
    release = threading.Event()
    beats: list[int] = []
    monkeypatch.setattr(
        sup, "provision_assigned_accounts", lambda **_: release.wait(5) or {"ok": True}
    )
    monkeypatch.setattr(sup, "heartbeat_once", lambda: beats.append(1) or {})
    sup.provision_guarded(timeout_seconds=0.6, heartbeat_every_seconds=0.1)
    release.set()
    assert len(beats) >= 3


def test_window_titles_are_redacted() -> None:
    from services.mt5_worker_agent.mt5_session import redact_window_titles

    out = redact_window_titles(
        ["12345678 - HFMarketsGlobal-Live2: Live Account", "  ", "Authorization failed"]
    )
    assert out == ["*** - HFMarketsGlobal-Live2: Live Account", "Authorization failed"]


def test_heartbeat_once_survives_connection_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom(_Railway):
        def heartbeat(self, **_: object) -> dict:  # type: ignore[override]
            raise ConnectionResetError("forcibly closed")

    sup = _sup(_Boom(), monkeypatch)
    for st in sup.states.values():
        st.worker_id = st.worker_id or "w1"
    report = sup.heartbeat_once()
    assert all(v["ok"] is False for v in report["railway"].values())


def test_init_ladder_falls_back_to_prelaunch_attach(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from services.mt5_worker_agent import mt5_session as ms

    calls: list[dict] = []

    class _Mt5:
        err: tuple[int, str] = (1, "ok")

        def initialize(self, **kw: object) -> bool:
            calls.append(kw)
            if "login" in kw:
                self.err = (-10005, "IPC timeout")
                return False
            self.err = (1, "ok")
            return True

        def last_error(self) -> tuple[int, str]:
            return self.err

        def shutdown(self) -> None:
            return None

    launched: list[int] = []
    killed: list[int] = []
    monkeypatch.setattr(ms, "kill_slot_terminals", lambda _p: killed.append(1))
    monkeypatch.setattr(ms, "disable_internal_mcp", lambda _p: False)
    monkeypatch.setattr(
        ms, "launch_logged_in", lambda *_a, **_k: launched.append(1) or True
    )
    ok, _ = ms.initialize_with_ladder(
        _Mt5(), tmp_path / "terminal64.exe", login=1234567, password="x", server="S"
    )
    assert ok is True
    assert len(calls) == 2 and "login" in calls[0] and "login" not in calls[1]
    assert launched == [1] and len(killed) >= 2


def test_merge_missing_base_dirs_adds_files_without_overwriting(tmp_path: Path) -> None:
    from services.mt5_worker_agent.slot_manager import _merge_missing_base_dirs

    src = tmp_path / "src"
    dest = tmp_path / "dest"
    (src / "Config").mkdir(parents=True)
    (src / "Bases" / "Broker").mkdir(parents=True)
    (src / "Config" / "servers.dat").write_text("src")
    (src / "Config" / "accounts.dat").write_text("secret")
    (src / "Config" / "common.ini").write_text("src-common")
    (src / "Bases" / "Broker" / "a.srv").write_text("x")
    (dest / "Config").mkdir(parents=True)
    (dest / "Config" / "common.ini").write_text("slot-common")

    added = _merge_missing_base_dirs(src, dest)

    assert added == 2
    assert (dest / "Config" / "servers.dat").read_text() == "src"
    assert (dest / "Config" / "common.ini").read_text() == "slot-common"
    assert not (dest / "Config" / "accounts.dat").exists()
    assert (dest / "Bases" / "Broker" / "a.srv").is_file()


def test_wait_for_login_succeeds_when_session_switches() -> None:
    from types import SimpleNamespace

    from services.mt5_worker_agent import mt5_session as ms

    seq = iter([None, SimpleNamespace(login=1), SimpleNamespace(login=777)])

    class _Mt5:
        def account_info(self) -> object:
            return next(seq)

    assert ms._wait_for_login(_Mt5(), 777, wait_seconds=30) is True


def test_repeated_initialize_failures_reset_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    sup = _sup(_Railway(), monkeypatch)
    resets: list[str] = []
    monkeypatch.setattr(sup, "_reset_slot", lambda slot_id, _st: resets.append(slot_id))
    bad = SimpleNamespace(
        ok=False,
        trade_allowed=False,
        trade_mode=None,
        server="",
        login=None,
        market_data_ok=False,
        balance=None,
        equity=None,
        currency="",
        symbols_total=0,
        quote_symbol="",
        error="initialize_failed:(-10005, 'IPC timeout')",
    )
    for _ in range(3):
        for st in sup.states.values():
            st.ready = False
        sup.provision_assigned_accounts(
            authenticate=lambda **_: bad,
            unwrap=lambda **_: {"login": "1", "secret": "x", "server": "S"},
        )
    assert len(resets) >= 1


def test_disable_internal_mcp_sets_enable_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.mt5_worker_agent import mt5_session as ms

    root = tmp_path / "slot"
    (root / "Config").mkdir(parents=True)
    exe = root / "terminal64.exe"
    exe.write_text("x")
    monkeypatch.setattr(ms, "assert_worker_terminal_path", lambda p: Path(p))
    ini = root / "Config" / "assistant.ini"
    ini.write_text(
        "[MCP.MetaTrader]\nEnable=1\nPort=22346\n[Other]\nA=1\n", encoding="utf-16"
    )

    assert ms.disable_internal_mcp(exe) is True
    out = ini.read_text(encoding="utf-16")
    assert "[MCP.MetaTrader]\nEnable=0\nPort=22346" in out.replace("\r\n", "\n")
    assert "[MCP.MetaEditor]" in out and "A=1" in out
    assert ms.disable_internal_mcp(exe) is False


def test_slot_journal_tail_redacts_and_reads_utf16(tmp_path):
    from services.mt5_worker_agent import mt5_session as ms

    slot = tmp_path / "demo-a"
    (slot / "Logs").mkdir(parents=True)
    exe = slot / "terminal64.exe"
    lines = "\n".join(
        [
            "0\t1\t12:00:00.1\tNetwork\t'2002270008': authorization failed",
            "0\t1\t12:00:01.1\tTerminal\tpassword=hunter2 ok",
        ]
    )
    (slot / "Logs" / "20261125.log").write_bytes(lines.encode("utf-16-le"))
    out = ms.slot_journal_tail(exe)
    assert any("***0008" in row for row in out)
    assert not any("2002270008" in row or "hunter2" in row for row in out)
    assert ms.slot_journal_tail(tmp_path / "missing" / "terminal64.exe") == []


def _journal(tmp_path, text, name="20261125.log"):
    slot = tmp_path / "demo-a"
    (slot / "Logs").mkdir(parents=True, exist_ok=True)
    (slot / "Logs" / name).write_bytes(text.encode("utf-16-le"))
    return slot / "terminal64.exe"


def test_journal_auth_state_reads_terminal_verdict(tmp_path):
    from services.mt5_worker_agent import mt5_session as ms

    ok = _journal(tmp_path, "0\t1\t1\tNetwork\t'2002270008': authorized on JM-Demo\n")
    assert ms.journal_auth_state(ok, 2002270008) == "authorized"
    bad = _journal(tmp_path, "0\t1\t1\tNetwork\t'2002270008': authorization failed\n")
    assert ms.journal_auth_state(bad, 2002270008) == "rejected"
    inv = _journal(
        tmp_path,
        "'2002270008': authorized on X\n'2002270008': trading has been disabled - "
        "investor mode\n",
    )
    assert ms.journal_auth_state(inv, 2002270008) == "investor"
    assert ms.journal_auth_state(ok, 999999) == "unknown"
    # lines before the launch mark are ignored
    mark = ms.journal_mark(ok)
    assert ms.journal_auth_state(ok, 2002270008, mark) == "unknown"


def test_self_update_applies_only_when_worker_files_differ(tmp_path):
    from types import SimpleNamespace

    from services.mt5_worker_agent.self_update import check_and_apply

    calls = []

    def runner(cmd, **_kw):
        calls.append(cmd[1])
        code = 1 if cmd[1] == "diff" else 0
        return SimpleNamespace(returncode=code)

    assert check_and_apply(tmp_path, run=runner) is True
    assert calls == ["fetch", "diff", "checkout"]

    def same(cmd, **_kw):
        return SimpleNamespace(returncode=0)

    assert check_and_apply(tmp_path, run=same) is False


def test_wait_for_config_consumed_returns_when_journal_shows_login(tmp_path):
    from services.mt5_worker_agent import mt5_session as ms

    exe = _journal(tmp_path, "0\t1\t1\tNetwork\t'450397410': authorized on XM\n")
    assert (
        ms.wait_for_config_consumed(
            exe, 450397410, ("", 0), timeout_seconds=2.0, poll_seconds=0.1
        )
        == "authorized"
    )
    quiet = _journal(tmp_path, "0\t1\t1\tTerminal\tstarted\n", name="20261126.log")
    assert (
        ms.wait_for_config_consumed(
            quiet, 450397410, ("", 0), timeout_seconds=0.3, poll_seconds=0.1
        )
        == "unknown"
    )
