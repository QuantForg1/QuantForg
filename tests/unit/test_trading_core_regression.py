"""Trading-core regression suite — production lockdown gate.

Does NOT change trading logic. Locks contracts for:
Scheduler/ITE wiring, AI scalping PME knobs, Risk overrides OFF,
OMS/PME lifecycle, recovery, MT5 position truth, multi-symbol scan config.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.application.services.institutional_oms_manage_adapter import (
    RecordingOmsManagePort,
)
from app.application.services.institutional_position_management import (
    InstitutionalPositionManagement,
)
from app.application.services.mt5_position_truth import force_sync_positions
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.force_first_trade import (
    is_force_first_trade_armed,
    maybe_override_decision,
)
from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.production_hardening.position_recovery import (
    recover_positions_from_mt5,
)
from app.domain.institutional_trading.risk_lock_override import (
    risk_lock_override_enabled,
)
from app.domain.institutional_trading.management.engine import PositionManagementEngine

OPENED = datetime(2026, 8, 4, 0, 28, tzinfo=UTC)


pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _pos(
    *,
    ticket: int = 100,
    side: str = "buy",
    entry: Decimal = Decimal("2300"),
    stop: Decimal = Decimal("2290"),
    volume: Decimal = Decimal("0.20"),
    state: PositionLifecycleState = PositionLifecycleState.OPEN,
) -> ManagedPosition:
    risk = abs(entry - stop)
    return ManagedPosition(
        ticket=ticket,
        symbol="XAUUSD",
        side=side,
        entry_price=entry,
        initial_volume=volume,
        remaining_volume=volume,
        initial_stop=stop,
        risk_distance=risk,
        opened_at=OPENED,
        state=state,
        current_stop=stop,
        current_tp=Decimal("2330"),
        be_moved=state != PositionLifecycleState.OPEN,
        partial_done=state
        in {PositionLifecycleState.PARTIAL, PositionLifecycleState.TRAILING},
        trailing_active=state is PositionLifecycleState.TRAILING,
    )


def _ctx(price: Decimal, **kwargs: object) -> PositionManageContext:
    base = dict(  # noqa: C408
        now=OPENED + timedelta(minutes=5),
        current_price=price,
        atr=Decimal("5"),
        mid_price=price,
        spread=Decimal("0.30"),
        market_open=True,
        connection_stable=True,
        position_still_open=True,
        user_id=uuid4(),
    )
    base.update(kwargs)
    return PositionManageContext(**base)  # type: ignore[arg-type]


def _svc() -> tuple[InstitutionalPositionManagement, RecordingOmsManagePort]:
    oms = RecordingOmsManagePort()
    return InstitutionalPositionManagement.create(oms), oms


class _FakeClient:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._rows = rows
        self.invalidated = False

    def invalidate_positions_cache(self) -> None:
        self.invalidated = True

    def list_positions(self) -> list[MT5Position]:
        return list(self._rows)


class _FakeAdapter:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._client = _FakeClient(rows)

    def list_positions(self) -> list[MT5Position]:
        return self._client.list_positions()


def test_test_overrides_permanently_disabled() -> None:
    settings = SimpleNamespace(
        force_first_trade=True,
        force_first_trade_max=1,
        force_first_trade_lot="0.01",
        force_first_trade_direction="AUTO",
        allow_risk_lock_override=True,
    )
    assert is_force_first_trade_armed(settings) is False
    assert risk_lock_override_enabled(settings) is False
    # maybe_override must never rewrite decisions
    from app.domain.institutional_trading.config import ITEConfig
    from app.domain.institutional_trading.decision_models import (
        AccountRiskState,
        ConfluenceResult,
        DecisionAction,
        TradeDecision,
        TradeDirection,
    )
    from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
    from app.domain.institutional_trading.models import (
        MarketAnalysisSnapshot,
        NewsProtectionStatus,
        SessionFilterResult,
        TradeQualityFactor,
        TradeQualityScore,
        TrendSnapshot,
    )
    from app.domain.market_context.enums import MarketSession
    from app.domain.market_data.timeframe import Timeframe
    from app.domain.market_structure.enums import StructureRole, TrendDirection
    from app.domain.market_structure.models import StructureSnapshot, TrendState
    from app.domain.value_objects.identity import SymbolCode

    as_of = OPENED
    code = SymbolCode(value="XAUUSD")
    structure = StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=as_of,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=TrendDirection.UP,
            as_of=as_of,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=2,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )
    snap = MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=as_of,
        config_version="ite-v1.0.0",
        input_hash="regression_hash_00112233445566778899aabb",
        structure_by_tf={"H1": structure},
        primary_structure=structure,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.UP,
            entry=TrendDirection.UP,
            execution=TrendDirection.UP,
            alignment_score=80,
            aligned=True,
            frames={"H4": "up"},
            why="ok",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON, allowed=True, reason="ok"
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(
            total=50,
            passed=False,
            band="reject",
            factors=(TradeQualityFactor(code="t", weight=20, score=50),),
        ),
        spread=Decimal("0.40"),
    )
    account = AccountRiskState(
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=0,
        already_in_trade=False,
        consecutive_losses=0,
        cooldown_active=False,
        market_open=True,
        atr=Decimal("5"),
        mid_price=Decimal("4000"),
        free_margin=Decimal("10000"),
    )
    conf = ConfluenceResult(
        confidence=40,
        direction=TradeDirection.NONE,
        reasons=(),
        rejected_rules=(),
        input_hash="c",
        band="reject",
        passed=False,
        factors={},
    )
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap, confluence=conf, account=account, risk_allowed=True
    )
    decision = TradeDecision(
        action=DecisionAction.NO_TRADE,
        direction=TradeDirection.NONE,
        confidence=40,
        quality=50,
        risk_score=10,
        reasons=("reject",),
        invalidations=(),
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
        estimated_rr=None,
        expected_duration="",
        confluence=conf,
        eligibility=elig,
        input_hash="d",
        config_version="ite-v1.0.0",
        symbol="XAUUSD",
        as_of=as_of,
        approved_lots=Decimal("0"),
        risk_reasons=(),
    )
    out, ok = maybe_override_decision(
        decision,
        snapshot=snap,
        account=account,
        ite_config=ITEConfig(),
        settings=settings,
        execution_enabled=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
    )
    assert ok is False
    assert out is decision


def test_scalping_pme_knobs_locked() -> None:
    pme = pme_config_for_scalping(DEFAULT_AI_SCALPING_CONFIG)
    assert pme.break_even_at_r == DEFAULT_AI_SCALPING_CONFIG.break_even_at_r
    assert pme.partial_at_r == DEFAULT_AI_SCALPING_CONFIG.partial_at_r
    assert pme.trail_after_r == DEFAULT_AI_SCALPING_CONFIG.trail_after_r
    assert DEFAULT_PME_CONFIG.break_even_at_r == Decimal("1.0")
    assert pme.break_even_at_r == Decimal("0.35")
    assert pme.partial_at_r == Decimal("0.70")
    assert pme.trail_after_r == Decimal("0.70")
    assert pme.absolute_max_hold_minutes == 12


def test_pme_break_even_partial_trail_close_loop() -> None:
    svc, oms = _svc()
    # Use scalping PME thresholds
    svc.engine.config = pme_config_for_scalping()
    pos = _pos()
    pos.trade_class = "SCALP"
    svc.register(pos)

    # 0.5R → BE (entry 2300, risk 10 → price 2305)
    r1 = svc.evaluate(100, _ctx(Decimal("2305")))
    assert r1.action is ManageActionKind.BREAK_EVEN
    assert r1.position.state is PositionLifecycleState.BE_MOVED
    assert r1.position.be_moved is True

    # 1.0R → partial (price 2310)
    r2 = svc.evaluate(100, _ctx(Decimal("2310")))
    assert r2.action is ManageActionKind.PARTIAL_CLOSE
    assert r2.position.state is PositionLifecycleState.PARTIAL

    # trail after partial
    r3 = svc.evaluate(100, _ctx(Decimal("2315")))
    assert r3.action is ManageActionKind.TRAIL
    assert r3.position.state is PositionLifecycleState.TRAILING

    # missing from book → local exit
    r4 = svc.evaluate(
        100, _ctx(Decimal("2315"), position_still_open=False)
    )
    assert r4.position.state is PositionLifecycleState.EXITED
    assert len(oms.calls) >= 2  # BE + trail (partial may be local min-lot)


def test_mt5_position_truth_account_count_multi_symbol() -> None:
    rows = [
        MT5Position(
            ticket=1,
            symbol="XAUUSD",
            side="sell",
            volume=Decimal("0.01"),
            open_price=Decimal("4000"),
            current_price=Decimal("3999"),
        ),
        MT5Position(
            ticket=2,
            symbol="EURUSD",
            side="buy",
            volume=Decimal("0.01"),
            open_price=Decimal("1.1"),
            current_price=Decimal("1.1"),
        ),
    ]
    sync = force_sync_positions(
        _FakeAdapter(rows),
        symbol="EURUSD",
        internal_positions=0,
        position_engine=None,
    )
    assert sync.mt5_positions == 2
    assert set(sync.tickets) == {1, 2}


def test_position_recovery_broker_be_reconstruct() -> None:
    class Row:
        ticket = 533737978
        symbol = "XAUUSD"
        side = "sell"
        volume = Decimal("0.01")
        open_price = Decimal("4060.503")
        current_price = Decimal("4055.027")
        stop_loss = Decimal("4059.23")
        take_profit = Decimal("4043.733")
        profit = Decimal("5.48")
        swap = Decimal("0")
        magic = 260720
        comment = "ite"
        opened_at = OPENED

    class Adap:
        def list_positions(self):
            return [Row()]

        def invalidate_positions_cache(self) -> None:
            return None

    eng = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    result = recover_positions_from_mt5(
        mt5_adapter=Adap(), engine=eng, symbol="XAUUSD"
    )
    assert result["registered"] == 1
    pos = eng.get(533737978)
    assert pos is not None
    assert pos.be_moved is True
    assert pos.state is PositionLifecycleState.BE_MOVED
    assert pos.risk_distance > Decimal("5")


def test_multi_asset_scan_config_present() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert hasattr(cfg, "multi_asset_scan_enabled")
    assert cfg.break_even_at_r == Decimal("0.35")
    assert cfg.partial_at_r == Decimal("0.70")
    assert cfg.parallel_scan_enabled is True
    assert cfg.max_entries_per_cycle >= 2
    assert cfg.post_close_rescan_enabled is True
    assert "NAS100" not in cfg.universe
    assert "EURUSD" in cfg.universe
    assert "BTCUSD" in cfg.universe
    assert cfg.max_daily_exposure_pct == Decimal("5.00")
    assert cfg.max_symbol_exposure_pct == Decimal("5.00")
    # SCALPING_V1 professional floors
    assert cfg.quality_baseline == "SCALPING_V1"
    assert cfg.normal_vol.quality == 74
    assert cfg.normal_vol.confidence == 71
    assert cfg.absolute_max_hold_minutes == 12


def test_frozen_module_imports() -> None:
    """Import graph for trading core — fail fast if modules deleted."""
    import app.application.services.institutional_ite_runtime as ite
    import app.application.services.risk_engine as risk
    import app.domain.institutional_trading.execution.bridge as bridge
    import app.infrastructure.brokers.mt5.adapter as adapter
    import app.infrastructure.brokers.mt5.gateway_client as gateway

    assert hasattr(ite, "build_ite_runtime")
    assert hasattr(ite, "InstitutionalIteRuntime")
    assert hasattr(risk, "RiskEngine")
    assert hasattr(bridge, "ExecutionBridge")
    assert hasattr(adapter, "MT5Adapter")
    assert hasattr(gateway, "GatewayMT5Client")
