"""Unit tests — Institutional AI Scalping v6 execution optimization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.pa_confluence import (
    assess_ema_stack,
    assess_rsi_confirm,
    evaluate_pa_confluence,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.execution.decision_hash_store import (
    load_executed_hashes,
    persist_executed_hashes,
)
from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import plan_action
from app.domain.institutional_trading.news_protection import NewsProtection
from app.domain.market_structure.enums import TrendDirection


def _snap(*, alignment: int = 70) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = TrendDirection.DOWN
    trend.primary = TrendDirection.DOWN
    trend.alignment_score = alignment
    trend.why = "test"

    structure = MagicMock()
    structure.breaks_of_structure = [MagicMock()]
    structure.changes_of_character = [MagicMock()]
    structure.swings = []
    structure.last_swing_low = Decimal("1900")
    structure.last_swing_high = Decimal("1910")

    liq = MagicMock()
    liq.sweeps = [MagicMock(side="HIGH")]
    liq.pools = []

    quality = MagicMock()
    quality.total = 85
    quality.components = {"momentum": 75, "volume": 70, "liquidity": 70}

    session = MagicMock()
    session.session = MagicMock(value="london")
    session.allowed = True

    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = structure
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=[])
    snap.fair_value_gaps = MagicMock(active_gaps=[MagicMock()])
    snap.trade_quality = quality
    snap.session = session
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD"
    return snap


@pytest.mark.unit
def test_v6_version_and_risk_locks() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version.startswith("ai-scalping-v")
    assert cfg.quality_baseline == "SCALPING_V1"
    assert cfg.risk_per_trade_pct == Decimal("0.50")
    assert cfg.normal_vol.confidence == 71
    assert cfg.risk_per_trade_pct <= Decimal("0.75")
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.absolute_max_hold_minutes >= cfg.typical_hold_max_minutes
    assert cfg.require_pa_confluence is True
    assert cfg.structure_trail_enabled is True
    assert cfg.news_fail_closed_without_feed is False


@pytest.mark.unit
def test_pme_maps_v6_execution_knobs() -> None:
    pme = pme_config_for_scalping()
    assert "SCALPING_V1" in pme.config_version
    assert (
        pme.absolute_max_hold_minutes
        == DEFAULT_AI_SCALPING_CONFIG.absolute_max_hold_minutes
    )
    assert pme.structure_trail_enabled is True
    assert pme.liquidity_trail_enabled is True
    assert pme.atr_trail_enabled is True
    assert pme.momentum_fade_threshold == DEFAULT_AI_SCALPING_CONFIG.momentum_fade_threshold
    assert pme.partial_tp_enabled is True
    assert pme.break_even_at_r == Decimal("0.35")


@pytest.mark.unit
def test_absolute_max_hold_flattens() -> None:
    opened = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    cfg = PositionManagementConfig(absolute_max_hold_minutes=15, time_stop_minutes=60)
    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.10"),
        remaining_volume=Decimal("0.10"),
        initial_stop=Decimal("2290"),
        risk_distance=Decimal("10"),
        opened_at=opened,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("2290"),
    )
    ctx = PositionManageContext(
        now=opened + timedelta(minutes=16),
        current_price=Decimal("2305"),
        atr=Decimal("5"),
    )
    plan = plan_action(pos, ctx, cfg)
    assert plan.kind is ManageActionKind.TIME_STOP
    assert "Absolute max hold" in plan.reason


@pytest.mark.unit
def test_structure_trail_preferred_over_atr() -> None:
    opened = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    cfg = PositionManagementConfig(
        trail_after_r=Decimal("1.0"),
        atr_trail_enabled=True,
        structure_trail_enabled=True,
        liquidity_trail_enabled=False,
    )
    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.20"),
        remaining_volume=Decimal("0.10"),
        initial_stop=Decimal("2290"),
        risk_distance=Decimal("10"),
        opened_at=opened,
        state=PositionLifecycleState.PARTIAL,
        current_stop=Decimal("2302"),
        be_moved=True,
        partial_done=True,
    )
    ctx = PositionManageContext(
        now=opened + timedelta(minutes=3),
        current_price=Decimal("2320"),
        atr=Decimal("5"),
        structure_stop=Decimal("2315"),
    )
    plan = plan_action(pos, ctx, cfg)
    assert plan.kind is ManageActionKind.TRAIL
    assert plan.new_sl == Decimal("2315")
    assert "structure" in plan.reason.lower()


@pytest.mark.unit
def test_momentum_fade_uses_config_threshold() -> None:
    opened = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    cfg = PositionManagementConfig(
        momentum_fade_exit=True,
        momentum_fade_threshold=50,
        absolute_max_hold_minutes=0,
        time_stop_minutes=60,
    )
    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.10"),
        remaining_volume=Decimal("0.10"),
        initial_stop=Decimal("2290"),
        risk_distance=Decimal("10"),
        opened_at=opened,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("2290"),
    )
    ctx = PositionManageContext(
        now=opened + timedelta(minutes=2),
        current_price=Decimal("2305"),
        atr=Decimal("5"),
        ai_momentum=45,
    )
    plan = plan_action(pos, ctx, cfg)
    assert plan.kind is ManageActionKind.EMERGENCY_EXIT
    assert "Momentum faded" in plan.reason


@pytest.mark.unit
def test_ema_rsi_pa_confluence() -> None:
    # Mild uptrend — avoids extreme RSI overbought fade scoring
    closes = [100.0 + (i % 20) * 0.05 + i * 0.02 for i in range(220)]
    score, _, reason = assess_ema_stack(closes, direction=TradeDirection.BUY)
    assert score >= 40
    assert "EMA" in reason

    rsi_score, ind, rsi_reason = assess_rsi_confirm(
        closes, direction=TradeDirection.BUY
    )
    assert ind.get("rsi_ready") is True
    assert rsi_score >= 25
    assert "RSI" in rsi_reason

    pa = evaluate_pa_confluence(
        _snap(),
        direction=TradeDirection.SELL,
        closes=closes,
        opens=[c - 0.1 for c in closes],
        highs=[c + 0.3 for c in closes],
        lows=[c - 0.3 for c in closes],
    )
    assert pa.score >= 0
    assert "ema20" in pa.indicators or "ema_ready" in pa.indicators


@pytest.mark.unit
def test_fixed_tp_r_preference() -> None:
    snap = _snap()
    cfg = AiScalpingConfig(fixed_tp_r=Decimal("1.5"))
    targets = compute_structure_targets(
        snap,
        direction=TradeDirection.SELL,
        entry=Decimal("1910"),
        atr=Decimal("5"),
        config=cfg,
    )
    assert targets.take_profit is not None
    assert targets.stop_loss is not None
    assert "fixed" in targets.reason.lower()


@pytest.mark.unit
def test_structure_sl_uses_nearest_swing_not_farthest() -> None:
    """Farthest swing-high SL deadlocked LIVE micro desks (stop≫ATR → hard_max)."""
    from types import SimpleNamespace

    snap = _snap()
    # Far high + near high above entry — must pick nearest (1912), not 1980.
    snap.primary_structure = SimpleNamespace(
        last_swing_low=Decimal("1850"),
        last_swing_high=Decimal("1980"),
        swings=(
            SimpleNamespace(price=Decimal("1980"), kind="HIGH"),
            SimpleNamespace(price=Decimal("1912"), kind="HIGH"),
            SimpleNamespace(price=Decimal("1900"), kind="LOW"),
        ),
    )
    cfg = AiScalpingConfig(fixed_tp_r=Decimal("1.5"), stop_atr_mult=Decimal("1.10"))
    targets = compute_structure_targets(
        snap,
        direction=TradeDirection.SELL,
        entry=Decimal("1910"),
        atr=Decimal("5"),
        config=cfg,
    )
    assert targets.stop_distance is not None
    # Nearest high 1912 + 0.15*ATR ≈ 2.75; must not be ~70+ from farthest 1980.
    assert targets.stop_distance < Decimal("20")
    assert "nearest" in targets.reason.lower()


@pytest.mark.unit
def test_structure_sl_caps_wide_stop_to_atr() -> None:
    from types import SimpleNamespace

    snap = _snap()
    snap.primary_structure = SimpleNamespace(
        last_swing_low=None,
        last_swing_high=Decimal("2000"),  # 90 pts above 1910
        swings=(),
    )
    cfg = AiScalpingConfig(fixed_tp_r=Decimal("1.5"), stop_atr_mult=Decimal("1.10"))
    targets = compute_structure_targets(
        snap,
        direction=TradeDirection.SELL,
        entry=Decimal("1910"),
        atr=Decimal("5"),
        config=cfg,
    )
    assert targets.stop_distance == Decimal("5") * Decimal("1.10")
    assert "capped" in targets.reason.lower()


@pytest.mark.unit
def test_news_fail_closed_optional(tmp_path: Path) -> None:
    cfg = DEFAULT_ITE_CONFIG
    open_prot = NewsProtection(config=cfg, fail_closed_without_feed=False)
    # news_protection_enabled False on default ITE
    status = open_prot.evaluate(as_of=datetime.now(UTC))
    assert status.blocked is False

    from dataclasses import replace

    enabled = replace(cfg, news_protection_enabled=True)
    closed = NewsProtection(
        config=enabled, calendar=None, fail_closed_without_feed=True
    )
    status2 = closed.evaluate(as_of=datetime.now(UTC))
    assert status2.blocked is True
    assert "fail-closed" in status2.reason


@pytest.mark.unit
def test_decision_hash_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))

    # Point store at tmp via settings mock path helper
    import app.domain.institutional_trading.execution.decision_hash_store as store

    monkeypatch.setattr(
        store, "_path", lambda: tmp_path / "execution_decision_hashes.json"
    )
    persist_executed_hashes(["abc", "def"])
    loaded, order = load_executed_hashes()
    assert loaded == {"abc", "def"}
    assert order == ["abc", "def"]
