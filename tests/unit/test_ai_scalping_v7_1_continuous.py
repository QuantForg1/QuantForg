"""Unit tests — AI Scalping v7.1 continuous autonomous production hardening."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.broker_profile_store import (
    BrokerProfileStore,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.continuous_operation import (
    ContinuousOperationController,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    aggregate_portfolio_risk,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.execution.decision_hash_store import (
    load_executed_hashes,
    persist_executed_hashes,
)

SECRET = "x" * 32 + "quantforg-test-secret-key!!"


@pytest.mark.unit
def test_v71_config_preserves_quality_risk() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version.startswith("ai-scalping-v8")
    assert cfg.continuous_version.startswith("ai-scalping-v7.1")
    assert cfg.quality_baseline == "ai-scalping-v6.3.0"
    assert cfg.normal_vol.confidence == 82
    assert cfg.normal_vol.quality == 82
    assert cfg.risk_per_trade_pct == Decimal("0.50")
    assert cfg.max_daily_exposure_pct == Decimal("2.00")
    assert cfg.max_open_trades == 5
    assert cfg.allow_martingale is False
    assert cfg.continuous_operation_enabled is True
    assert cfg.post_close_rescan_enabled is True


@pytest.mark.unit
def test_pause_new_entries_never_abandons_positions() -> None:
    ctrl = ContinuousOperationController()
    pause = ctrl.evaluate_new_entry_pause(
        daily_loss_exceeded=True,
        broker_available=False,
        gateway_available=False,
        market_open=False,
        portfolio_risk_exceeded=True,
    )
    assert pause.pause_new_entries is True
    assert pause.manage_open_positions is True
    assert len(pause.reasons) >= 4


@pytest.mark.unit
def test_self_heal_reconnects_without_order_send() -> None:
    hits: list[str] = []

    def gw() -> bool:
        hits.append("gateway")
        return True

    def mt5() -> bool:
        hits.append("mt5")
        return True

    def oms() -> bool:
        hits.append("oms")
        return True

    def feed() -> bool:
        hits.append("feed")
        return True

    ctrl = ContinuousOperationController()
    ctrl.bind_reconnects(gateway=gw, mt5=mt5, oms=oms, feed=feed)
    events = ctrl.heal_dependencies(
        gateway_ok=False, mt5_ok=False, oms_ok=False, feed_ok=False
    )
    assert "gateway" in hits and "mt5" in hits and "oms" in hits and "feed" in hits
    assert events
    # Forbidden path must still raise
    with pytest.raises(RuntimeError):
        ctrl.recovery.retry_order_send()


@pytest.mark.unit
def test_post_close_rescan_flag() -> None:
    ctrl = ContinuousOperationController()
    assert ctrl.consume_rescan() is False
    ctrl.request_rescan_after_close()
    assert ctrl.consume_rescan() is True
    assert ctrl.consume_rescan() is False


@pytest.mark.unit
def test_broker_profile_encrypts_password(tmp_path: Path) -> None:
    store = BrokerProfileStore(path=tmp_path / "profile.json")
    profile = store.save(
        broker="Weltrade",
        server="Weltrade-Demo",
        login=123456,
        terminal_path="C:/MT5/terminal64.exe",
        password_plaintext="s3cret-pass",
        secret_key=SECRET,
    )
    assert profile.password_ciphertext is not None
    assert "s3cret-pass" not in profile.password_ciphertext
    raw = (tmp_path / "profile.json").read_text(encoding="utf-8")
    assert "s3cret-pass" not in raw
    loaded = store.load()
    assert loaded is not None
    assert loaded.login == 123456
    assert loaded.server == "Weltrade-Demo"
    assert store.decrypt_password(loaded, secret_key=SECRET) == "s3cret-pass"
    assert "password_ciphertext" not in loaded.to_public_dict()


@pytest.mark.unit
def test_broker_profile_preserves_password_on_metadata_update(tmp_path: Path) -> None:
    store = BrokerProfileStore(path=tmp_path / "profile.json")
    store.save(
        broker="Weltrade",
        server="Weltrade-Demo",
        login=123456,
        terminal_path="C:/MT5/terminal64.exe",
        password_plaintext="s3cret-pass",
        secret_key=SECRET,
    )
    store.save(
        broker="Weltrade",
        server="Weltrade-MT5",
        login=123456,
        terminal_path="C:/MT5/terminal64.exe",
        password_plaintext=None,
        secret_key=None,
    )
    loaded = store.load()
    assert loaded is not None
    assert loaded.server == "Weltrade-MT5"
    assert store.decrypt_password(loaded, secret_key=SECRET) == "s3cret-pass"


@pytest.mark.unit
def test_max_open_still_gated_by_portfolio_exposure() -> None:
    """Raising max_open to 5 does not raise risk — exposure ceiling still binds."""
    account = AccountRiskState(
        equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        open_positions=4,
    )
    snap = aggregate_portfolio_risk(account, config=DEFAULT_AI_SCALPING_CONFIG)
    assert snap.max_open_positions == 5
    assert snap.exposure_pct == Decimal("2.00")
    assert snap.exposure_pct >= snap.max_exposure_pct


@pytest.mark.unit
def test_restart_hash_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    hashes = ["abc123", "def456"]
    persist_executed_hashes(hashes)
    loaded, _order = load_executed_hashes()
    assert "abc123" in loaded
    assert "def456" in loaded


@pytest.mark.unit
def test_continuous_tick_production_simulation() -> None:
    ctrl = ContinuousOperationController(config=DEFAULT_AI_SCALPING_CONFIG)
    ctrl.bind_reconnects(
        gateway=lambda: True,
        mt5=lambda: True,
        oms=lambda: True,
        feed=lambda: True,
    )
    ctrl.mark_startup_resume()
    snap = ctrl.tick(
        gateway_ok=False,
        mt5_ok=False,
        oms_ok=False,
        feed_ok=False,
        daily_loss_exceeded=False,
        broker_available=False,
        market_open=True,
        portfolio_risk_exceeded=False,
    )
    assert snap.resumed_positions is True
    assert snap.pause["manage_open_positions"] is True
    assert snap.pause["pause_new_entries"] is True
    reasons = snap.pause["reasons"]
    assert "broker unavailable" in reasons or "gateway unavailable" in reasons
    assert any("stale heartbeat" in str(r) for r in reasons)


@pytest.mark.unit
def test_oms_down_pauses_via_missing_heartbeat() -> None:
    """OMS failure alone must pause new entries (no dedicated oms_available flag)."""
    ctrl = ContinuousOperationController(config=DEFAULT_AI_SCALPING_CONFIG)
    snap = ctrl.tick(
        gateway_ok=True,
        mt5_ok=True,
        oms_ok=False,
        feed_ok=True,
        broker_available=True,
        market_open=True,
        portfolio_risk_exceeded=False,
    )
    assert snap.pause["pause_new_entries"] is True
    assert snap.pause["manage_open_positions"] is True
    assert any("stale heartbeat:oms" in str(r) for r in snap.pause["reasons"])
