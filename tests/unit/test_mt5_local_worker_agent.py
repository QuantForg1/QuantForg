"""Local Windows MT5 worker agent — isolation and safety (no live credentials)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.mt5_worker_agent import main as agent_main
from services.mt5_worker_agent.paths import (
    assert_worker_terminal_path,
    slot_dir,
    slot_terminal_exe,
)
from services.mt5_worker_agent.railway_client import RailwayClientConfig
from services.mt5_worker_agent.slot_manager import (
    list_configured_slot_ids,
    stop_slot_terminal,
)

pytestmark = [pytest.mark.unit]


def test_default_slots_are_three_demo_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QF_MT5_LOCAL_SLOTS", raising=False)
    assert list_configured_slot_ids() == ["demo-a", "demo-b", "demo-c"]


def test_slot_paths_stay_under_configured_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path))
    assert slot_dir("Demo-A") == tmp_path / "demo-a"
    assert slot_terminal_exe("demo-a") == tmp_path / "demo-a" / "terminal64.exe"


def test_refuse_live_program_files_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    live = tmp_path / "Program Files" / "MetaTrader 5" / "terminal64.exe"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"fake")
    monkeypatch.setenv("QF_LIVE_MT5_TERMINAL_PATH", str(live))
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    with pytest.raises(ValueError, match="LIVE MetaTrader"):
        assert_worker_terminal_path(live)


def test_allow_isolated_slot_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    live = tmp_path / "live" / "terminal64.exe"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"live")
    slot = tmp_path / "slots" / "demo-a" / "terminal64.exe"
    slot.parent.mkdir(parents=True)
    slot.write_bytes(b"slot")
    monkeypatch.setenv("QF_LIVE_MT5_TERMINAL_PATH", str(live))
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path / "slots"))
    assert assert_worker_terminal_path(slot) == slot.resolve()


def test_refuse_installed_terminal_not_at_default_live_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Owner's broker-branded install is refused even if the LIVE path
    setting still points at the stock MetaTrader location."""
    owner = tmp_path / "Program Files" / "Weltrade MT5" / "terminal64.exe"
    owner.parent.mkdir(parents=True)
    owner.write_bytes(b"owner")
    monkeypatch.delenv("QF_LIVE_MT5_TERMINAL_PATH", raising=False)
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path / "slots"))
    with pytest.raises(ValueError, match="Program Files"):
        assert_worker_terminal_path(owner)


def test_refuse_terminal_outside_slot_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    other = tmp_path / "elsewhere" / "terminal64.exe"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"x")
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path / "slots"))
    with pytest.raises(ValueError, match="outside the slot root"):
        assert_worker_terminal_path(other)


def test_slot_link_into_program_files_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "Program Files" / "MT5" / "terminal64.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"installed")
    slot = tmp_path / "slots" / "demo-a"
    slot.mkdir(parents=True)
    (slot / "terminal64.exe").symlink_to(target)
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path / "slots"))
    with pytest.raises(ValueError, match="Program Files"):
        assert_worker_terminal_path(slot / "terminal64.exe")


def test_linked_slot_directory_inside_root_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Production uses a linked slot (mt5_worker_slots_production/demo-a)."""
    real = tmp_path / "portable" / "demo-a"
    real.mkdir(parents=True)
    (real / "terminal64.exe").write_bytes(b"portable")
    root = tmp_path / "slots_production"
    root.mkdir()
    (root / "demo-a").symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "false")
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(root))
    assert assert_worker_terminal_path(root / "demo-a" / "terminal64.exe")


def test_railway_requires_https_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_API_BASE_URL", "http://example.com")
    monkeypatch.setenv("WORKER_SERVICE_TOKEN", "x" * 20)
    with pytest.raises(ValueError, match="https"):
        RailwayClientConfig.from_env()

    monkeypatch.setenv("QUANTFORG_API_BASE_URL", "https://example.com")
    monkeypatch.setenv("WORKER_SERVICE_TOKEN", "short")
    with pytest.raises(ValueError, match="WORKER_SERVICE_TOKEN"):
        RailwayClientConfig.from_env()

    monkeypatch.setenv("WORKER_SERVICE_TOKEN", "x" * 20)
    cfg = RailwayClientConfig.from_env()
    assert cfg.api_base_url == "https://example.com"
    assert "token" not in json.dumps({"api": cfg.api_base_url})


def test_connect_demo_refuses_without_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("QF_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("QF_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("QF_DEMO_SERVER", raising=False)
    code = agent_main.cmd_connect_demo("demo-a")
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["authenticated_demo_accounts"] == 0
    assert payload["error"] == "demo_credentials_not_provided"


def test_idle_requires_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKER_SERVICE_TOKEN", raising=False)
    assert agent_main.cmd_idle() == 2


def test_stop_slot_refuses_when_slot_is_live_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    live = tmp_path / "MetaTrader 5" / "terminal64.exe"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"x")
    monkeypatch.setenv("QF_LIVE_MT5_TERMINAL_PATH", str(live))
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path))
    # Point slot exe at the live path via symlink-like layout by forcing resolve equal.
    # We patch slot_terminal_exe to return live path.
    with (
        patch(
            "services.mt5_worker_agent.slot_manager.slot_terminal_exe",
            return_value=live,
        ),
        pytest.raises(RuntimeError, match="Refusing to stop LIVE"),
    ):
        stop_slot_terminal("demo-a")


def test_cli_status_does_not_require_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("WORKER_SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("QF_MT5_LOCAL_SLOTS", "demo-a")
    with (
        patch(
            "services.mt5_worker_agent.local_supervisor.LocalWorkerSupervisor.refresh_status",
            return_value=[{"slot_id": "demo-a", "ready": False}],
        ),
        patch(
            "services.mt5_worker_agent.resources.sample_terminal_processes",
            return_value=[],
        ),
        patch(
            "services.mt5_worker_agent.resources.host_memory_summary",
            return_value={"total_mb": 1, "free_mb": 1},
        ),
        # Avoid RailwayClientConfig.from_env raising during supervisor init
        patch(
            "services.mt5_worker_agent.local_supervisor.RailwayWorkerClient",
            side_effect=ValueError("no token"),
        ),
    ):
        code = agent_main.cmd_status()
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["note"].startswith("Status only")
    dumped = json.dumps(payload).lower()
    assert "password" not in dumped
    assert payload.get("credentials_exposed") is False


def test_status_redacts_nested_credential_fields() -> None:
    from services.mt5_worker_agent.safe_status import public_status_payload

    dirty = {
        "slots": [
            {
                "slot_id": "demo-a",
                "password": "super-secret",
                "master_password": "x",
                "nested": {"access_token": "tok", "ok": True},
            }
        ],
        "error": "login failed password=leaked",
        "refresh_token": "abc",
        "queue": {"depth": 0, "credentials_exposed": False},
        "note": "Status only",
    }
    clean = public_status_payload(dirty)
    dumped = json.dumps(clean).lower()
    assert "password" not in dumped
    assert "super-secret" not in dumped
    assert "tok" not in dumped
    assert "leaked" not in dumped
    assert "abc" not in dumped
    assert clean["slots"][0]["slot_id"] == "demo-a"
    assert clean["slots"][0]["nested"]["ok"] is True
    assert clean["credentials_exposed"] is False
    assert clean["error"] == "[redacted]"


def test_status_redacts_bearer_and_secret_phrases() -> None:
    from services.mt5_worker_agent.safe_status import redact_secrets

    payload = {
        "detail": "Authorization: Bearer eyJhbGciOi",
        "meta": {"secret=value": "nope", "safe": 1},
        "items": [{"token": "x", "slot": "a"}],
    }
    cleaned = redact_secrets(payload)
    dumped = json.dumps(cleaned).lower()
    assert "password" not in dumped
    assert "bearer" not in dumped or cleaned["detail"] == "[redacted]"
    assert "token" not in dumped
    assert cleaned["items"][0]["slot"] == "a"
    assert cleaned["meta"]["safe"] == 1


def test_main_dispatch_prepare_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.prepare_all.return_value = {"demo-a": {"ok": True}}
    with patch(
        "services.mt5_worker_agent.local_supervisor.LocalWorkerSupervisor",
        return_value=fake,
    ):
        assert agent_main.main(["prepare-slots"]) == 0
    fake.prepare_all.assert_called_once_with(force=False)
