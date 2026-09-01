"""Authoritative persisted Auto Trading mode is scalping unless explicitly Swing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services import ops_state_persistence as osp
from app.application.services.ops_state_persistence import (
    load_ops_state,
    resolve_persisted_trading_mode,
    save_ops_state,
)
from app.domain.institutional_trading.auto_trading import AutoTradePolicy
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(osp, "_supabase_rest_config", lambda: None)
    monkeypatch.setattr(osp, "_load_postgres_state", lambda: {})
    monkeypatch.setattr(osp, "_save_postgres_state", lambda _state: False)


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Persisted Mode Tester",
    )


def test_resolve_missing_empty_invalid_default_to_scalping() -> None:
    assert resolve_persisted_trading_mode({}) == ("scalping", "missing_default")
    assert resolve_persisted_trading_mode({"trading_mode": ""}) == (
        "scalping",
        "missing_default",
    )
    assert resolve_persisted_trading_mode({"trading_mode": "nope"}) == (
        "scalping",
        "missing_default",
    )
    assert resolve_persisted_trading_mode(None) == ("scalping", "missing_default")


def test_resolve_persisted_scalping_stays_scalping() -> None:
    assert resolve_persisted_trading_mode({"trading_mode": "scalping"}) == (
        "scalping",
        "persisted",
    )


def test_resolve_unlabeled_legacy_swing_migrates() -> None:
    assert resolve_persisted_trading_mode({"trading_mode": "swing"}) == (
        "scalping",
        "legacy_swing_migrated",
    )


def test_resolve_explicit_swing_is_preserved() -> None:
    assert resolve_persisted_trading_mode(
        {"trading_mode": "swing", "trading_mode_explicit": True}
    ) == ("swing", "explicit")
    assert resolve_persisted_trading_mode(
        {"trading_mode": "swing", "trading_mode_explicit": "true"}
    ) == ("swing", "explicit")


def test_resolve_unlabeled_alpha_is_kept() -> None:
    assert resolve_persisted_trading_mode({"trading_mode": "alpha"}) == (
        "alpha",
        "persisted",
    )


def test_hydrate_missing_mode_is_scalping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.trading_mode == "scalping"
    assert load_ops_state().get("trading_mode") == "scalping"
    cp._GLOBAL_PLANE = None


def test_hydrate_persisted_scalping_stays_scalping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    save_ops_state(
        {
            "ops_mode": "LIVE",
            "auto_trading_enabled": True,
            "auto_trading_run_state": "running",
            "trading_mode": "scalping",
            "max_open_positions": 3,
        }
    )
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.trading_mode == "scalping"
    assert plane.max_open_trades == 10
    cp._GLOBAL_PLANE = None


def test_hydrate_explicit_swing_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    save_ops_state(
        {
            "ops_mode": "LIVE",
            "auto_trading_enabled": True,
            "auto_trading_run_state": "running",
            "trading_mode": "swing",
            "trading_mode_explicit": True,
            "max_open_positions": 2,
        }
    )
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.trading_mode == "swing"
    state = load_ops_state()
    assert state.get("trading_mode") == "swing"
    assert state.get("trading_mode_explicit") is True
    assert plane.max_open_trades == 2
    cp._GLOBAL_PLANE = None


def test_hydrate_unlabeled_legacy_swing_migrates_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    save_ops_state(
        {
            "ops_mode": "LIVE",
            "auto_trading_enabled": True,
            "auto_trading_run_state": "running",
            "trading_mode": "swing",
            "max_open_positions": 3,
        }
    )
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.trading_mode == "scalping"
    assert plane.max_open_trades == 10
    assert plane.risk_per_trade_pct == Decimal("1.0")
    assert plane.max_daily_loss_pct == Decimal("80.0")
    state = load_ops_state()
    assert state.get("trading_mode") == "scalping"
    assert state.get("trading_mode_migrated_from") == "swing"
    assert state.get("trading_mode_explicit") is False

    cp._GLOBAL_PLANE = None
    again = cp.get_control_plane()
    assert again.trading_mode == "scalping"
    assert load_ops_state().get("trading_mode") == "scalping"
    cp._GLOBAL_PLANE = None


def test_operator_mode_select_marks_explicit_swing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    plane = OperationsControlPlane()
    plane.update_auto_trade_controls(
        _op(),
        trading_mode="swing",
        reason="operator set trading_mode=swing",
    )
    state = load_ops_state()
    assert state.get("trading_mode") == "swing"
    assert state.get("trading_mode_explicit") is True

    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    hydrated = cp.get_control_plane()
    assert hydrated.trading_mode == "swing"
    cp._GLOBAL_PLANE = None


def test_start_pause_echo_does_not_mark_mode_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    plane = OperationsControlPlane()
    plane.update_auto_trade_controls(
        _op(),
        run_state="running",
        trading_mode="swing",
        reason="operator set run_state=running",
    )
    state = load_ops_state()
    assert state.get("trading_mode") == "swing"
    assert not state.get("trading_mode_explicit")


def test_ui_fallback_and_mode_select_reason_are_scalping() -> None:
    ui = (
        ROOT / "frontend" / "src" / "components" / "ops" / "auto-trading-workspace.tsx"
    ).read_text(encoding="utf-8")
    assert 'str(policy.trading_mode, "scalping")' in ui
    assert "operator set trading_mode=${mode}" in ui
    alpha = (
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "ops"
        / "institutional-alpha-workspace.tsx"
    ).read_text(encoding="utf-8")
    assert 'trading_mode: on ? "alpha" : "scalping"' in alpha
    assert "Alpha disabled — Scalping mode" in alpha


def test_mode_does_not_alter_risk_safety_leverage() -> None:
    assert AutoTradePolicy().trading_mode == "scalping"
    assert OperationsControlPlane().trading_mode == "scalping"
    assert OperationsControlPlane().max_open_trades == 10
    assert OperationsControlPlane().risk_per_trade_pct == Decimal("1.0")
    assert OperationsControlPlane().max_daily_loss_pct == Decimal("80.0")
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert STRONG_CANDIDATE_THRESHOLD == 85
    assert Decimal("2000") == MAX_LEVERAGE
