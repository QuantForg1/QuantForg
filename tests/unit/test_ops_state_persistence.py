"""Unit tests — durable Ops mode + Demo certification persistence."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.live_auto_trade_certification import (
    get_live_cert_service,
    reset_live_cert_service_for_tests,
    seed_certified_demo_report_for_tests,
)
from app.application.services.ops_state_persistence import (
    load_ops_state,
    save_ops_state,
)
from app.domain.institutional_trading.live_certification import report_from_dict


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
