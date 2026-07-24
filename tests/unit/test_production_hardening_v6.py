"""Unit tests — Production Hardening v6."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.production_hardening.backtest_live import (
    StrategyPerfSnapshot,
)
from app.domain.institutional_trading.production_hardening.config import (
    ProductionHardeningConfig,
)
from app.domain.institutional_trading.production_hardening.learning import (
    LearningWeightStore,
)
from app.domain.institutional_trading.production_hardening.lifecycle import (
    ExecutionLifecycleStore,
    LIFECYCLE_STAGES,
)
from app.domain.institutional_trading.production_hardening.position_recovery import (
    recover_positions_from_mt5,
)
from app.domain.institutional_trading.production_hardening.retry import (
    RetryingOmsSubmitPort,
    decide_retry,
    is_permanent_reject,
    is_transient_reject,
)
from app.domain.institutional_trading.production_hardening.secrets_audit import (
    audit_secret_exposure,
)


@pytest.mark.unit
def test_lifecycle_stages_cover_full_path() -> None:
    assert LIFECYCLE_STAGES[0] == "SIGNAL"
    assert LIFECYCLE_STAGES[-1] == "EXIT"
    assert "OMS" in LIFECYCLE_STAGES
    assert "MT5_GATEWAY" in LIFECYCLE_STAGES


@pytest.mark.unit
def test_lifecycle_records_timestamped_events(tmp_path) -> None:
    store = ExecutionLifecycleStore(max_events=100)
    store._path = tmp_path / "lifecycle.jsonl"
    ev = store.record(
        stage="SIGNAL",
        status="ok",
        detail="test",
        trace_id="t1",
        symbol="XAUUSD",
    )
    assert ev.at
    assert ev.stage == "SIGNAL"
    recent = store.recent(limit=5)
    assert recent[0]["trace_id"] == "t1"


@pytest.mark.unit
def test_retry_classifies_transient_vs_permanent() -> None:
    assert is_transient_reject(retcode=10004, message="Requote") is True
    assert is_transient_reject(retcode=10012, message="timeout") is True
    assert is_permanent_reject(retcode=10014, message="invalid volume") is True
    assert is_permanent_reject(retcode=10016, message="invalid stops") is True
    assert is_permanent_reject(retcode=10019, message="no money") is True
    assert is_permanent_reject(retcode=10018, message="market closed") is True
    assert is_transient_reject(retcode=10014, message="invalid volume") is False

    d = decide_retry(attempt=1, retcode=10004, message="requote")
    assert d.retryable is True
    assert d.backoff_ms > 0

    d2 = decide_retry(attempt=1, retcode=10016, message="invalid stops")
    assert d2.retryable is False


@pytest.mark.unit
def test_retrying_oms_port_retries_transient_only() -> None:
    calls = {"n": 0}

    class Inner:
        def submit_market(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                return SimpleNamespace(
                    outcome="rejected",
                    retcode=10004,
                    message="Requote",
                )
            return SimpleNamespace(
                outcome="success",
                retcode=10009,
                message="done",
            )

    cfg = ProductionHardeningConfig(
        retry_enabled=True,
        retry_max_attempts=5,
        retry_base_backoff_ms=1,
        retry_max_backoff_ms=2,
        retry_jitter_ratio=0.0,
    )
    port = RetryingOmsSubmitPort(Inner(), config=cfg)
    result = port.submit_market(request_id="req1", user_id="u")
    assert result.outcome == "success"
    assert calls["n"] == 3
    assert port.retry_count == 2


@pytest.mark.unit
def test_retrying_oms_never_retries_permanent() -> None:
    calls = {"n": 0}

    class Inner:
        def submit_market(self, **kwargs):
            calls["n"] += 1
            return SimpleNamespace(
                outcome="rejected",
                retcode=10019,
                message="Insufficient margin",
            )

    cfg = ProductionHardeningConfig(retry_base_backoff_ms=1, retry_max_backoff_ms=2)
    port = RetryingOmsSubmitPort(Inner(), config=cfg)
    result = port.submit_market(request_id="req2")
    assert result.retcode == 10019
    assert calls["n"] == 1
    assert port.retry_count == 0


@pytest.mark.unit
def test_learning_weights_gradual_and_bounded(tmp_path) -> None:
    store = LearningWeightStore()
    store._path = tmp_path / "weights.json"
    store.multipliers = {k: 1.0 for k in store.multipliers}
    store.observe_trade(win=True, factor_scores={"confidence": 80, "trend": 70})
    assert store.multipliers["confidence"] > 1.0
    base = {"confidence": 20, "trend": 15, "momentum": 10}
    out = store.apply_to_weights(base)
    assert out["confidence"] >= base["confidence"]
    assert "momentum" in out


@pytest.mark.unit
def test_backtest_live_material_deviation() -> None:
    snap = StrategyPerfSnapshot(
        strategy_id="prod",
        backtest_win_rate=60.0,
        live_win_rate=40.0,
        backtest_avg_rr=2.0,
        live_avg_rr=1.9,
    )
    d = snap.deviations()
    assert d["material_deviation"] is True
    assert any("win_rate" in f for f in d["flags"])


@pytest.mark.unit
def test_secrets_audit_never_exposes_values(monkeypatch) -> None:
    monkeypatch.setenv("FAKE_API_KEY", "super-secret-value-do-not-leak")
    report = audit_secret_exposure()
    assert report["values_exposed"] is False
    blob = str(report)
    assert "super-secret-value-do-not-leak" not in blob
    assert "FAKE_API_KEY" in report["sensitive_env_names_present"]


@pytest.mark.unit
def test_position_recovery_skips_duplicate_tickets(tmp_path, monkeypatch) -> None:
    from app.domain.institutional_trading.management.models import (
        ManagedPosition,
        PositionLifecycleState,
    )
    from decimal import Decimal
    from datetime import UTC, datetime

    existing = ManagedPosition(
        ticket=42,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.1"),
        remaining_volume=Decimal("0.1"),
        initial_stop=Decimal("2290"),
        risk_distance=Decimal("10"),
        opened_at=datetime.now(UTC),
        state=PositionLifecycleState.OPEN,
        be_moved=True,
        trailing_active=True,
    )
    engine = SimpleNamespace(_positions={42: existing}, get=lambda t: existing)

    class Pos:
        ticket = 42
        symbol = "XAUUSD"
        side = "buy"
        open_price = 2300
        volume = 0.1

    mt5 = SimpleNamespace(list_positions=lambda: [Pos()])

    class Sync:
        mt5_positions = 1
        tickets = (42,)

    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *a, **k: Sync(),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme.json",
    )
    result = recover_positions_from_mt5(mt5_adapter=mt5, engine=engine)
    assert result["ok"] is True
    assert result["registered"] == 0
    assert 42 in engine._positions
    assert len(engine._positions) == 1


@pytest.mark.unit
def test_production_reliability_dashboard_shape() -> None:
    from app.application.services.production_reliability import (
        build_production_reliability_dashboard,
    )

    # Should not raise even without full runtime wiring
    dash = build_production_reliability_dashboard()
    assert "system_health" in dash
    assert "live_performance" in dash
    assert "execution_timeline" in dash
    assert "secrets_audit" in dash
    assert dash["secrets_audit"]["values_exposed"] is False
    for key in (
        "mt5_gateway",
        "broker",
        "oms",
        "auto_trading",
        "ai_engine",
        "market_data",
        "database",
        "railway_service",
    ):
        assert key in dash["system_health"]
        assert dash["system_health"][key] in {"Healthy", "Warning", "Offline"}
