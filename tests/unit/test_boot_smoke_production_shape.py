"""CI boot smoke: production-shaped settings + app + ITE runtime on mock MT5.

Guards the owner-limit validators (ITEConfig, control plane) against crashing
production on boot when env or persisted ops_state still carries old values.
Runs in a subprocess so production-shaped singletons never leak into other
tests. Never sends orders: MT5 is the in-process mock and execution is off.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_ROOT = Path(__file__).resolve().parents[2]

_BOOT_SCRIPT = r"""
from core.config.settings import Settings

settings = Settings(_env_file=None)
assert settings.debug is False, "DEBUG not coerced"
assert settings.reload is False, "RELOAD not coerced"
assert settings.force_first_trade is False, "FORCE_FIRST_TRADE not coerced"
assert settings.allow_risk_lock_override is False, "risk override not coerced"
assert settings.execution_universe_mode == "GOLD_ONLY", settings.execution_universe_mode
assert settings.execution_enabled is False, "execution must be off without a gateway"

from app.main import create_app

assert create_app(settings) is not None

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_ite_runtime import build_ite_runtime
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.operations.control_plane import get_control_plane
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.client import MockMT5Client

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
plane = get_control_plane()
assert plane.max_open_trades == 5, plane.max_open_trades
assert plane.max_daily_loss_pct <= DEFAULT_ITE_CONFIG.max_daily_loss_pct
assert DEFAULT_ITE_CONFIG.max_open_trades == 5
assert adapter.execution_enabled is False
print("BOOT_OK")
"""


def test_production_shaped_boot_with_stale_ops_state(tmp_path: Path) -> None:
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
        k: v
        for k, v in os.environ.items()
        if k not in {"MT5_GATEWAY_BASE_URL", "MT5_GATEWAY_CALLER_TOKEN", "DATABASE_URL"}
    }
    env.update(
        {
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
            # Never reach a real Postgres from CI; ops_state stays on the file.
            "DURABLE_PERSISTENCE": "false",
            "QUANTFORG_OPS_STATE_PATH": str(ops_state),
            "QUANTFORG_DATA_DIR": str(tmp_path / "data"),
            "QUANTFORG_STATE_DIR": str(tmp_path / "state"),
            "PYTHONPATH": str(_ROOT),
        }
    )
    proc = subprocess.run(  # noqa: S603  # fixed local boot script, not untrusted input
        [sys.executable, "-c", _BOOT_SCRIPT],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "BOOT_OK" in proc.stdout
