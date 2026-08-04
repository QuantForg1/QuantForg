"""Continuous scalping cadence — parallel scan + multi-handoff + post-close."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.domain.institutional_trading.ai_scalping.config import (
    BROKER_UNAVAILABLE_SCALP_SYMBOLS,
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
)


@pytest.mark.unit
def test_continuous_scalp_flow_knobs_locked() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.parallel_scan_enabled is True
    assert cfg.parallel_scan_concurrency >= 2
    assert cfg.max_entries_per_cycle >= 2
    assert cfg.post_close_rescan_enabled is True
    assert cfg.post_close_rescan_delay_seconds == 0.0
    assert cfg.max_open_trades >= 2
    # Strategy floors = SCALPING_V1 (profile-owned)
    assert cfg.normal_vol.quality == 74
    assert cfg.min_structure_score == 60
    assert cfg.min_momentum_score == 55
    assert cfg.min_expected_rr == Decimal("1.20")
    assert cfg.fixed_tp_r == Decimal("1.20")
    assert cfg.absolute_max_hold_minutes == 12
    assert cfg.break_even_at_r == Decimal("0.35")


@pytest.mark.unit
def test_broker_dead_indexes_excluded_from_universe() -> None:
    for dead in ("NAS100", "US30", "GER40"):
        assert dead in BROKER_UNAVAILABLE_SCALP_SYMBOLS
        assert dead not in DEFAULT_SCALPING_UNIVERSE


@pytest.mark.unit
def test_handoff_queue_drains_without_rescan() -> None:
    rt = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
    )
    rt._eligible_handoff_queue = ["XAUUSD", "EURUSD", "GBPUSD"]
    rt._eligible_consumed = {"XAUUSD"}
    rt._entries_this_scan = 1
    assert rt._take_next_handoff_symbol() == "EURUSD"
    assert rt._take_next_handoff_symbol() == "GBPUSD"
    assert rt._take_next_handoff_symbol() is None


@pytest.mark.unit
def test_handoff_skips_already_open_symbol() -> None:
    open_pos = {
        "1": SimpleNamespace(symbol="XAUUSD", side="sell", volume=0.01),
    }
    rt = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions=open_pos)),
    )
    rt._eligible_handoff_queue = ["XAUUSD", "EURUSD", "BTCUSD"]
    rt._eligible_consumed = set()
    rt._entries_this_scan = 0
    assert rt._take_next_handoff_symbol() == "EURUSD"
    assert rt._take_next_handoff_symbol() == "BTCUSD"
    assert "XAUUSD" in rt._eligible_consumed


@pytest.mark.unit
def test_scalping_v1_multi_asset_concurrent_caps() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.max_open_trades >= 5
    assert cfg.max_entries_per_cycle >= 5
    assert cfg.require_probability_improvement is False
    assert "MULTI_ASSET_CONCURRENT" in cfg.version or "SCALPING_V1" in cfg.version
