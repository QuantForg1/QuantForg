"""Force First Trade — isolated temporary test override."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.force_first_trade import (
    FORCED_REASON,
    ForceFirstTradeConfig,
    force_first_trade_status,
    is_forced_test_decision,
    maybe_override_decision,
    record_forced_trade_success,
    reset_force_first_trade_state_for_tests,
    resolve_force_direction,
)
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

AS_OF = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_force_state(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "QUANTFORG_FORCE_FIRST_TRADE_STATE_PATH",
        str(tmp_path / "force_first_trade_state.json"),
    )
    reset_force_first_trade_state_for_tests()
    yield
    reset_force_first_trade_state_for_tests()


def _structure() -> StructureSnapshot:
    code = SymbolCode(value="XAUUSD")
    return StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=AS_OF,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=TrendDirection.UP,
            as_of=AS_OF,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=4,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )


def _snapshot(*, quality: int = 68) -> MarketAnalysisSnapshot:
    structure = _structure()
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=AS_OF,
        config_version="ite-v1.0.0",
        input_hash="force_test_hash_00112233445566778899aa",
        structure_by_tf={"H1": structure},
        primary_structure=structure,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.DOWN,
            entry=TrendDirection.DOWN,
            execution=TrendDirection.DOWN,
            alignment_score=17,
            aligned=False,
            frames={"H4": "up", "H1": "down"},
            why="not aligned",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON,
            allowed=True,
            reason="ok",
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(
            total=quality,
            passed=quality >= 80,
            band="reject" if quality < 80 else "tradable",
            factors=(TradeQualityFactor(code="trend", weight=20, score=quality),),
        ),
        spread=Decimal("0.40"),
    )


def _account(**kwargs: object) -> AccountRiskState:
    base = dict(  # noqa: C408
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
        mid_price=Decimal("4048"),
        free_margin=Decimal("10000"),
    )
    base.update(kwargs)
    return AccountRiskState(**base)  # type: ignore[arg-type]


def _weak_decision(
    snap: MarketAnalysisSnapshot, account: AccountRiskState
) -> TradeDecision:
    conf = ConfluenceResult(
        confidence=54,
        direction=TradeDirection.NONE,
        reasons=("mtf not aligned",),
        rejected_rules=("mtf",),
        input_hash="weak_conf",
        band="reject",
        passed=False,
        factors={},
    )
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=account,
        risk_allowed=True,
    )
    assert elig.eligible is False
    return TradeDecision(
        action=DecisionAction.NO_TRADE,
        direction=TradeDirection.NONE,
        confidence=54,
        quality=snap.trade_quality.total,
        risk_score=10,
        reasons=("Below institutional confidence/quality gates — NO_TRADE",),
        invalidations=(),
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
        estimated_rr=None,
        expected_duration="",
        confluence=conf,
        eligibility=elig,
        input_hash="weak_decision",
        config_version="ite-v1.0.0",
        symbol="XAUUSD",
        as_of=AS_OF,
        approved_lots=Decimal("0"),
        risk_reasons=(),
    )


def _settings(**kwargs: object) -> SimpleNamespace:
    base = {
        "force_first_trade": True,
        "force_first_trade_max": 1,
        "force_first_trade_lot": "0.01",
        "force_first_trade_direction": "AUTO",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.mark.unit
def test_resolve_direction_auto_follows_h4() -> None:
    snap = _snapshot()
    conf = ConfluenceResult(
        confidence=50,
        direction=TradeDirection.NONE,
        reasons=(),
        rejected_rules=(),
        input_hash="x",
        band="reject",
        passed=False,
    )
    assert (
        resolve_force_direction(
            configured="AUTO", snapshot=snap, confluence=conf
        )
        is TradeDirection.BUY
    )


@pytest.mark.unit
def test_waive_signal_gates_keeps_margin_and_session() -> None:
    snap = _snapshot(quality=40)
    account = _account(free_margin=Decimal("0"))
    conf = ConfluenceResult(
        confidence=10,
        direction=TradeDirection.BUY,
        reasons=(),
        rejected_rules=(),
        input_hash="x",
        band="reject",
        passed=False,
    )
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=account,
        risk_allowed=True,
        waive_signal_gates=True,
    )
    assert elig.checks["quality_ok"] is True
    assert elig.checks["confluence_ok"] is True
    assert elig.checks["margin_available"] is False
    assert elig.eligible is False


@pytest.mark.unit
def test_maybe_override_builds_forced_buy() -> None:
    snap = _snapshot()
    account = _account()
    decision = _weak_decision(snap, account)
    forced, ok = maybe_override_decision(
        decision,
        snapshot=snap,
        account=account,
        ite_config=ITEConfig(),
        settings=_settings(),
        execution_enabled=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
    )
    assert ok is True
    assert forced.action is DecisionAction.BUY
    assert forced.approved_lots == Decimal("0.01")
    assert is_forced_test_decision(forced)
    assert FORCED_REASON in forced.reasons
    assert forced.entry_zone is not None
    assert forced.stop_zone is not None
    assert forced.target_zone is not None


@pytest.mark.unit
def test_force_skips_when_open_position() -> None:
    snap = _snapshot()
    account = _account(open_positions=1, already_in_trade=True)
    decision = _weak_decision(snap, account)
    _, ok = maybe_override_decision(
        decision,
        snapshot=snap,
        account=account,
        ite_config=ITEConfig(),
        settings=_settings(),
        execution_enabled=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
    )
    assert ok is False


@pytest.mark.unit
def test_record_success_disarms_and_blocks_second() -> None:
    snap = _snapshot()
    account = _account()
    decision = _weak_decision(snap, account)
    settings = _settings()

    forced, ok = maybe_override_decision(
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
    assert ok is True
    record_forced_trade_success(
        direction=forced.direction.value,
        lot=forced.approved_lots or Decimal("0.01"),
        ticket=99901,
    )
    status = force_first_trade_status(
        settings,
        gateway_connected=True,
        broker_connected=True,
        execution_enabled=True,
    )
    assert status["banner"] is False
    assert status["armed"] is False
    assert status["executed_count"] == 1

    _, ok2 = maybe_override_decision(
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
    assert ok2 is False


@pytest.mark.unit
def test_banner_when_enabled() -> None:
    cfg = ForceFirstTradeConfig.from_settings(_settings(force_first_trade=True))
    assert cfg.enabled is True
    status = force_first_trade_status(
        _settings(),
        gateway_connected=True,
        broker_connected=True,
        execution_enabled=True,
    )
    assert status["banner"] is True
    assert "TEST MODE" in status["message"]
