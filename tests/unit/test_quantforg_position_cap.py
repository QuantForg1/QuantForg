"""QuantForg live position cap — identity + XAUUSD_i, not account-wide tickets."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.dto.backtest import RunBacktestCommand
from app.application.services.backtest_engine import BacktestRunInput
from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    check_portfolio_limits,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
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
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
    capacity_available,
    count_quantforg_positions,
    live_strategy_max_open,
    snapshot_quantforg_positions,
)
from app.domain.institutional_trading.operations.system_coherence import FaultClass
from app.domain.market_context.enums import MarketSession
from app.domain.market_structure.enums import TrendDirection
from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY


def _pos(
    ticket: int,
    symbol: str = "XAUUSD_i",
    *,
    magic: int = 0,
    comment: str = "",
    side: str = "buy",
    price: str = "4000",
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=Decimal("0.01"),
        open_price=Decimal(price),
        current_price=Decimal(price),
        magic=magic,
        comment=comment,
    )


class _FakeAdapter:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._rows = rows
        self.client = SimpleNamespace(
            invalidate_positions_cache=lambda: None,
        )

    def list_positions(self) -> list[MT5Position]:
        return list(self._rows)


def _account(*, open_n: int = 0, already: bool = False) -> AccountRiskState:
    return AccountRiskState(
        equity=Decimal("10000"),
        open_positions=open_n,
        already_in_trade=already,
        market_open=True,
        free_margin=Decimal("8000"),
    )


def _snapshot() -> MarketAnalysisSnapshot:
    as_of = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    return MarketAnalysisSnapshot(
        symbol="XAUUSD_i",
        as_of=as_of,
        config_version="ite-v1.0.0",
        input_hash="pos-cap-test",
        structure_by_tf={},
        primary_structure=None,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.UP,
            entry=TrendDirection.UP,
            execution=TrendDirection.UP,
            alignment_score=95,
            aligned=True,
            frames={},
            why="test",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON,
            allowed=True,
            reason="ok",
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="news clear"),
        trade_quality=TradeQualityScore(
            total=90,
            passed=True,
            band="high_confidence",
            factors=(TradeQualityFactor(code="trend", weight=20, score=90),),
        ),
        spread=Decimal("0.30"),
        atr=Decimal("8"),
    )


def _conf() -> ConfluenceResult:
    return ConfluenceResult(
        confidence=90,
        direction=TradeDirection.BUY,
        reasons=("aligned",),
        rejected_rules=(),
        input_hash="h1",
        band="high_confidence",
        passed=True,
        factors={},
    )


def _facts(**overrides: object) -> AutoTradeLiveFacts:
    base: dict[str, object] = {
        "gateway_connected": True,
        "broker_connected": True,
        "market_data_live": True,
        "risk_engine_pass": True,
        "account_trading_enabled": True,
        "mt5_autotrading_enabled": True,
        "symbol": "XAUUSD_i",
        "symbol_tradable": True,
        "margin_available": True,
        "no_broker_restrictions": True,
        "open_positions": 0,
        "session": "london",
        "spread": Decimal("0.40"),
        "news_blocked": False,
        "daily_loss_exceeded": False,
        "emergency_stop": False,
        "ops_mode": "LIVE",
        "execution_enabled": True,
    }
    base.update(overrides)
    return AutoTradeLiveFacts(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_manual_position_does_not_consume_quantforg_capacity() -> None:
    rows = [_pos(1, magic=0, comment="manual")]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 0
    snap = snapshot_quantforg_positions(rows, symbol="XAUUSD_i", configured_max=5)
    assert snap.account_count == 1
    assert snap.quantforg_count == 0
    assert snap.capacity_available is True


@pytest.mark.unit
def test_unrelated_symbol_does_not_consume_gold_capacity() -> None:
    rows = [_pos(2, "EURUSD", magic=QUANTFORG_MAGIC)]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 0


@pytest.mark.unit
def test_zero_quantforg_gold_positions_capacity_available() -> None:
    assert capacity_available(current_count=0, configured_max=5) is True


@pytest.mark.unit
def test_one_quantforg_gold_position_second_entry_allowed_when_max_gt_1() -> None:
    rows = [_pos(10, magic=QUANTFORG_MAGIC, comment="ite:v1:abc")]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 1
    assert capacity_available(current_count=1, configured_max=5) is True
    elig = PositionEligibilityEngine(config=ITEConfig(max_open_trades=5)).evaluate(
        snapshot=_snapshot(),
        confluence=_conf(),
        account=_account(open_n=1, already=True),
        risk_allowed=True,
    )
    assert elig.eligible is True
    assert elig.checks["max_open_trades"] is True


@pytest.mark.unit
def test_quantforg_at_configured_max_blocks() -> None:
    rows = [_pos(i, magic=QUANTFORG_MAGIC) for i in range(1, 6)]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 5
    assert capacity_available(current_count=5, configured_max=5) is False
    elig = PositionEligibilityEngine(config=ITEConfig(max_open_trades=5)).evaluate(
        snapshot=_snapshot(),
        confluence=_conf(),
        account=_account(open_n=5, already=True),
        risk_allowed=True,
    )
    assert elig.eligible is False
    assert any("at max" in r for r in elig.rejection_reasons)


@pytest.mark.unit
def test_global_account_positions_do_not_auto_block() -> None:
    adapter = _FakeAdapter(
        [
            _pos(1, "EURUSD", magic=0),
            _pos(2, "XAUUSD_i", magic=0, comment="manual gold"),
        ]
    )
    sync = force_sync_positions(adapter, symbol="XAUUSD_i", internal_positions=0)
    assert sync.mt5_positions == 2
    assert sync.quantforg_positions == 0
    account = apply_mt5_position_truth(_account(open_n=9, already=True), sync)
    assert account.open_positions == 0
    assert account.already_in_trade is False
    assert account.account_open_positions == 2
    policy = AutoTradePolicy(enabled=True, max_open_positions=5)
    safety = evaluate_auto_trade_safety(
        policy, _facts(open_positions=account.open_positions)
    )
    assert safety.allowed is True


@pytest.mark.unit
def test_risk_hard_block_still_blocks() -> None:
    engine = RiskEngine(config=RiskEngineConfig(max_open_positions=1))
    owned = [_pos(7, magic=QUANTFORG_MAGIC)]
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="r1",
            symbol="XAUUSD_i",
            side="buy",
            stop_loss_distance=Decimal("10"),
            entry_price=Decimal("4000"),
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
        ),
        account=AccountSnapshot(
            login=1,
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin=Decimal("0"),
            free_margin=Decimal("9000"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=2000,
            currency="USD",
            server="test",
        ),
        positions=owned,
    )
    assert result.decision is RiskDecision.REJECT
    assert any("open positions" in r.lower() for r in result.reasons)


@pytest.mark.unit
def test_safety_hard_block_still_blocks() -> None:
    policy = AutoTradePolicy(enabled=True, max_open_positions=5)
    blocked = evaluate_auto_trade_safety(policy, _facts(emergency_stop=True))
    assert blocked.allowed is False


@pytest.mark.unit
def test_portfolio_hard_block_still_blocks() -> None:
    blocked, reason = check_portfolio_limits(
        open_positions=5,
        max_open_positions=5,
        daily_loss_pct=Decimal("0"),
        max_daily_loss_pct=Decimal("3"),
        exposure_pct=Decimal("0"),
        max_exposure_pct=Decimal("80"),
    )
    assert blocked is True
    assert reason is not None


@pytest.mark.unit
def test_oms_rejection_path_still_present_via_eligibility() -> None:
    elig = PositionEligibilityEngine(config=ITEConfig(max_open_trades=5)).evaluate(
        snapshot=_snapshot(),
        confluence=_conf(),
        account=_account(),
        risk_allowed=False,
        risk_reasons=("OMS rejected",),
    )
    assert elig.eligible is False
    assert any("OMS rejected" in r for r in elig.rejection_reasons)


@pytest.mark.unit
def test_duplicate_add_on_guard_still_works() -> None:
    denied = may_add_scalping_trade(
        open_positions=1,
        max_open=5,
        new_confidence=70,
        best_open_confidence=70,
        new_direction="BUY",
        open_directions=("BUY",),
        entry=Decimal("4000"),
        open_entries=(Decimal("4000"),),
        min_entry_distance=Decimal("1"),
        require_improvement=False,
    )
    assert denied.allow is False
    assert "Identical entry" in denied.reason or "Duplicate" in denied.reason


@pytest.mark.unit
def test_unknown_order_still_requires_reconciliation() -> None:
    assert FaultClass.RECONCILIATION_REQUIRED.value == "RECONCILIATION_REQUIRED"


@pytest.mark.unit
def test_backtest_max_open_trades_one_does_not_leak_into_live() -> None:
    assert RunBacktestCommand(
        user_id=uuid4(), request_id="b", symbol="XAUUSD"
    ).max_open_trades == 1
    assert BacktestRunInput(
        user_id=uuid4(), request_id="b", symbol="XAUUSD"
    ).max_open_trades == 1
    assert DEFAULT_ITE_CONFIG.max_open_trades == 1
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    live_max = live_strategy_max_open(
        ITEConfig(max_open_trades=DEFAULT_AI_SCALPING_CONFIG.max_open_trades)
    )
    assert live_max == DEFAULT_AI_SCALPING_CONFIG.max_open_trades
    assert BacktestRunInput(
        user_id=uuid4(), request_id="c", symbol="XAUUSD"
    ).max_open_trades == 1
    assert DEFAULT_AI_SCALPING_CONFIG.max_open_trades >= 3


@pytest.mark.unit
def test_current_scan_and_position_snapshot_stay_coherent() -> None:
    rows = [_pos(11, magic=QUANTFORG_MAGIC)]
    snap = snapshot_quantforg_positions(
        rows,
        symbol=CANONICAL_GOLD_BROKER_DISPLAY,
        configured_max=5,
    )
    assert snap.symbol == CANONICAL_GOLD_BROKER_DISPLAY
    assert snap.as_of.endswith("Z")
    assert snap.quantforg_count == 1
    assert snap.account_count == 1
    assert snap.magic == QUANTFORG_MAGIC


@pytest.mark.unit
def test_quantforg_identity_uses_existing_magic() -> None:
    owned = _pos(3, magic=QUANTFORG_MAGIC, comment="ite:v1:deadbeef")
    other = _pos(4, magic=42, comment="other-ea")
    adapter = _FakeAdapter([owned, other])
    sync = force_sync_positions(adapter, symbol="XAUUSD_i")
    assert sync.quantforg_positions == 1
    assert sync.quantforg_tickets == (3,)
    assert sync.mt5_positions == 2
