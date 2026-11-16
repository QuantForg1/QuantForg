"""Supervisor logs each slot into its own customer's account, honestly."""

from __future__ import annotations

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
