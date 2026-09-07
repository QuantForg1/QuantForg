"""Zero-cost Supabase egress recovery — auth, fail-closed live, scanner continuity."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.dto.auth import LoginCommand
from app.application.use_cases.auth import LoginUseCase
from app.domain.exceptions.auth import AuthenticationError
from app.domain.institutional_trading.live_trading_control import (
    orders_may_submit,
    recover_after_restart,
)
from tests.unit.fakes import SharedUnitOfWorkFactory
from tests.unit.fakes_auth import FakeAuthProvider


@pytest.mark.unit
@pytest.mark.trading_core
class TestSupabaseEgressRecovery:
    def test_restart_fail_closed_never_auto_enables(self) -> None:
        assert recover_after_restart("ENABLED") == "PAUSED"
        assert recover_after_restart("LIVE_ENABLED") == "PAUSED"
        assert recover_after_restart("ARMED") == "DISABLED"
        assert recover_after_restart(None) == "DISABLED"
        assert orders_may_submit("DISABLED") is False
        assert orders_may_submit("PAUSED") is False
        assert orders_may_submit("ARMED") is False

    def test_enable_route_requires_operator_auth(self) -> None:
        root = Path(__file__).resolve().parents[2]
        src = (root / "app/presentation/routers/live_trading_control.py").read_text(
            encoding="utf-8"
        )
        assert "@router.post(\"/enable\")" in src
        assert "OperatorUser" in src
        assert "require_roles(UserRole.OWNER, UserRole.ADMIN)" in src
        assert "FORCE_LIVE" not in src
        assert "unauthenticated" not in src.lower()

    def test_single_mt5_order_send_path(self) -> None:
        root = Path(__file__).resolve().parents[2]
        text = (
            root / "app/infrastructure/brokers/mt5/gateway_client.py"
        ).read_text(encoding="utf-8")
        assert "POST /trade/order_send → MetaTrader5.order_send" in text
        assert 'def order_send(' in text

    def test_history_queries_are_bounded(self) -> None:
        from app.application.services import signal_intelligence_service as si

        assert si._HISTORY_LIMIT_MAX <= 200
        assert si._FALLBACK_CAP <= 200

    def test_observe_survives_postgrest_402(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.application.services import signal_intelligence_service as si

        monkeypatch.setattr(si, "_upsert_history_direct", lambda _rows: 0)
        monkeypatch.setattr(si, "_upsert_history_postgres", lambda _rows: 0)
        monkeypatch.setattr(si, "_save_history_ops_fallback", lambda _rows: None)
        monkeypatch.setattr(
            si,
            "get_last_multi_asset_scan",
            lambda: {"as_of": "t", "rows": []},
        )
        si._last_observe_mono = 0.0
        out = si.observe_live_scan()
        assert out["ok"] is True
        assert out["fabricated"] is False

    def test_scanner_publish_survives_signal_history_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.application.services import institutional_multi_asset_scanner as sc

        def _boom() -> None:
            raise RuntimeError("exceed_egress_quota")

        monkeypatch.setattr(
            "app.application.services.signal_intelligence_service.observe_live_scan",
            _boom,
        )
        sc._publish_scan_observation({"rows": [{"symbol": "EURUSD", "reject": True}]})

    def test_durable_payload_strips_observation_blobs(self) -> None:
        from app.application.services.ops_state_persistence import _durable_payload

        slim = _durable_payload(
            {
                "live_trading_state": "DISABLED",
                "signal_history": {"items": [{"x": 1}] * 50},
                "symbol_management": {"items": []},
                "_hydrate_source": "postgres",
            }
        )
        assert "signal_history" not in slim
        assert "symbol_management" not in slim
        assert slim["live_trading_state"] == "DISABLED"

    def test_no_supabase_js_realtime_client(self) -> None:
        root = Path(__file__).resolve().parents[2]
        pkg = (root / "frontend/package.json").read_text(encoding="utf-8")
        assert "@supabase/supabase-js" not in pkg
        engine = (root / "frontend/src/lib/realtime/engine.ts").read_text(
            encoding="utf-8"
        )
        assert "refCount" in engine

    @pytest.mark.asyncio
    async def test_login_audit_failure_does_not_mask_auth_error(self) -> None:
        factory = SharedUnitOfWorkFactory()
        provider = FakeAuthProvider()
        audit = MagicMock()
        audit.execute = MagicMock(side_effect=RuntimeError("exceed_egress_quota"))
        # RecordAuditEventUseCase-shaped: LoginUseCase._audit calls audit.execute
        login = LoginUseCase(auth=provider, uow_factory=factory, audit=audit)
        with pytest.raises(AuthenticationError):
            await login.execute(
                LoginCommand(email="nobody@quantforg.com", password="wrong-password")
            )

    def test_identity_factory_not_postgrest_when_postgres_durable(self) -> None:
        from app.infrastructure.persistence.factory import build_persistence_factories
        from app.infrastructure.persistence.postgres_platform import (
            PostgresPlatformUnitOfWorkFactory,
        )
        from app.infrastructure.persistence.supabase_identity import (
            SupabaseIdentityUnitOfWorkFactory,
        )
        from core.config.settings import AppEnvironment, Settings

        settings = Settings(
            app_env=AppEnvironment.DEVELOPMENT,
            durable_persistence=True,
            _env_file=None,
        )
        factories = build_persistence_factories(
            settings, MagicMock(), supabase=MagicMock()
        )
        assert isinstance(factories["uow_factory"], PostgresPlatformUnitOfWorkFactory)
        assert not isinstance(
            factories["uow_factory"], SupabaseIdentityUnitOfWorkFactory
        )
