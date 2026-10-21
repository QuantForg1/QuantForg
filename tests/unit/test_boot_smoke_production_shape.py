"""CI boot smoke: production-shaped settings + app + ITE runtime on mock MT5.

Guards the owner-limit validators (ITEConfig, control plane) against crashing
production on boot when env or persisted ops_state still carries old values.
Never sends orders: MT5 is the in-process mock and execution stays disabled.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture
def production_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Stale ops_state as production may still have it (pre owner limits).
    ops_state = tmp_path / "ops_state.json"
    ops_state.write_text(
        json.dumps(
            {
                "ops_mode": "LIVE",
                "auto_trading_enabled": True,
                "auto_trading_run_state": "running",
                "trading_mode": "swing",
                "trading_mode_explicit": True,
                "max_open_positions": 10,
            }
        ),
        encoding="utf-8",
    )
    env = {
        "APP_ENV": "production",
        "DEBUG": "true",
        "RELOAD": "true",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "ALLOWED_HOSTS": "quantforg-production.up.railway.app",
        "EXECUTION_ENABLED": "true",
        "MT5_USE_MOCK": "true",
        "EXECUTION_UNIVERSE_MODE": "GOLD_ONLY",
        "FORCE_FIRST_TRADE": "true",
        "ALLOW_RISK_LOCK_OVERRIDE": "true",
        "TELEGRAM_ENABLED": "false",
        "JIMVIO_ENABLED": "false",
        "QUANTFORG_OPS_STATE_PATH": str(ops_state),
        "QUANTFORG_DATA_DIR": str(tmp_path / "data"),
        "QUANTFORG_STATE_DIR": str(tmp_path / "state"),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("MT5_GATEWAY_BASE_URL", "MT5_GATEWAY_CALLER_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    yield tmp_path
    cp._GLOBAL_PLANE = None


def test_production_settings_coerce_unsafe_toggles(production_env: Path) -> None:
    from core.config.settings import Settings

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.debug is False
    assert settings.reload is False
    assert settings.force_first_trade is False
    assert settings.allow_risk_lock_override is False
    assert settings.execution_universe_mode == "GOLD_ONLY"
    # No live gateway configured -> execution forced off.
    assert settings.execution_enabled is False


def test_app_and_ite_runtime_boot_with_owner_limits(production_env: Path) -> None:
    from app.application.services.execution_gateway import ExecutionGateway
    from app.application.services.execution_safety import ExecutionSafetyService
    from app.application.services.institutional_ite_runtime import build_ite_runtime
    from app.application.services.mt5_order_validation import (
        MT5OrderValidationService,
    )
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.infrastructure.brokers.mt5.adapter import MT5Adapter
    from app.infrastructure.brokers.mt5.client import MockMT5Client
    from app.main import create_app
    from core.config.settings import Settings

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(settings)
    assert app is not None

    client = MockMT5Client()
    client.initialize()
    adapter = MT5Adapter(client=client, execution_enabled=False)
    validation = MT5OrderValidationService(adapter=adapter)
    runtime = build_ite_runtime(
        settings=settings,
        mt5_adapter=adapter,
        execution_gateway=ExecutionGateway(adapter=adapter, order_validation=validation),
        execution_safety=ExecutionSafetyService(
            adapter=adapter, order_validation=validation
        ),
        mt5_order_validation=validation,
        supabase=None,
    )
    assert runtime is not None
    # Persisted max_open_positions=10 is clamped at hydrate, never raised.
    plane = get_control_plane()
    assert plane.max_open_trades == 1
    assert plane.max_daily_loss_pct <= DEFAULT_ITE_CONFIG.max_daily_loss_pct
    assert DEFAULT_ITE_CONFIG.max_open_trades == 1
    assert adapter.execution_enabled is False
