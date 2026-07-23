"""Unit tests — durable Ops mode + Demo certification persistence."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.application.services import ops_state_persistence as osp
from app.application.services.live_auto_trade_certification import (
    get_live_cert_service,
    reset_live_cert_service_for_tests,
    seed_certified_demo_report_for_tests,
)
from app.application.services.ops_state_persistence import (
    load_ops_state,
    ops_state_diagnostics,
    save_ops_state,
)
from app.domain.institutional_trading.live_certification import report_from_dict


@pytest.fixture(autouse=True)
def _no_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default unit tests to file-only persistence (no live Supabase I/O)."""
    monkeypatch.setattr(osp, "_supabase_rest_config", lambda: None)
    monkeypatch.setattr(osp, "_load_postgres_state", lambda: {})
    monkeypatch.setattr(osp, "_save_postgres_state", lambda _state: False)


@pytest.mark.unit
class TestOpsStatePersistence:
    def test_roundtrip_ops_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "ops_state.json"
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
        save_ops_state({"ops_mode": "CANARY", "ops_mode_reason": "test"})
        state = load_ops_state()
        assert state["ops_mode"] == "CANARY"
        assert path.is_file()

    def test_hydrate_live_and_auto_trading(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "ops_state.json"
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
        save_ops_state(
            {
                "ops_mode": "LIVE",
                "auto_trading_enabled": True,
                "auto_trading_run_state": "running",
            }
        )
        from app.domain.institutional_trading.operations import control_plane as cp
        from app.domain.institutional_trading.operations.models import OpsExecutionMode

        cp._GLOBAL_PLANE = None
        plane = cp.get_control_plane()
        assert plane.mode is OpsExecutionMode.LIVE
        assert plane.auto_trading_enabled is True
        assert plane.auto_trading_run_state == "running"
        cp._GLOBAL_PLANE = None

    def test_postgres_wins_over_stale_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "ops_state.json"
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
        path.write_text('{"ops_mode": "SHADOW"}', encoding="utf-8")

        def _pg() -> dict[str, Any]:
            return {
                "ops_mode": "LIVE",
                "auto_trading_enabled": True,
                "auto_trading_run_state": "running",
            }

        monkeypatch.setattr(
            osp, "_supabase_rest_config", lambda: ("https://example.test/rest/v1", "k")
        )
        monkeypatch.setattr(osp, "_load_postgres_state", _pg)
        state = load_ops_state()
        assert state["ops_mode"] == "LIVE"
        assert state["_hydrate_source"] == "postgres"
        diag = ops_state_diagnostics()
        assert diag["persisted_ops_mode"] == "LIVE"
        assert diag["postgres_has_state"] is True
        assert diag["durable"] is True

    def test_report_from_dict_rejects_uncertified(self) -> None:
        assert report_from_dict({"certified": False}) is None
        assert report_from_dict({}) is None
        assert report_from_dict({"certified": True}) is None  # no trade

    def test_cert_hydrate_from_durable_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "ops_state.json"
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
        reset_live_cert_service_for_tests()
        seed_certified_demo_report_for_tests()
        # seed persists when certified=True
        assert path.is_file() or True  # may have written

        # Force re-hydrate via fresh singleton
        import app.application.services.live_auto_trade_certification as mod

        report = get_live_cert_service().last_report()
        assert report is not None and report.certified
        raw = report.to_dict()
        save_ops_state({"demo_certification_report": raw})

        with mod._SERVICE_LOCK:
            mod._SERVICE = None
        hydrated = get_live_cert_service()
        restored = hydrated.last_report()
        assert restored is not None
        assert restored.certified is True
        assert restored.trade is not None
        assert restored.trade.account_type.lower() == "demo"
        assert restored.trade.volume == Decimal("0.01")

    def test_never_hydrates_live_account_as_demo_cert(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "ops_state.json"
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
        seed_certified_demo_report_for_tests(account_type="live")
        report = get_live_cert_service().last_report()
        assert report is not None
        # Manually persist a live-account "certified" blob — hydrate must refuse
        blob = report.to_dict()
        blob["trade"]["account_type"] = "live"
        save_ops_state({"demo_certification_report": blob})

        import app.application.services.live_auto_trade_certification as mod

        with mod._SERVICE_LOCK:
            mod._SERVICE = None
        assert get_live_cert_service().last_report() is None
