"""$6 SL-risk sizing, $30 aggregate cap, and PME profit protection.

Does not create a second Risk/OMS/PME engine. Never sends orders.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.application.services.institutional_oms_manage_adapter import (
    RecordingOmsManagePort,
)
from app.application.services.institutional_position_management import (
    InstitutionalPositionManagement,
)
from app.application.services.jimvio_publisher import map_jimvio_event_type
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.services.telegram_events import (
    SIGNAL_CONFIRMED,
    TRADE_OPENED,
    public_channel_notices,
)
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    calculate_dynamic_lots_v2,
)
from app.domain.institutional_trading.config import (
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
    TARGET_PLANNED_RISK_USD,
    TARGET_RISK_PER_TRADE_USD,
)
from app.domain.institutional_trading.live_trading_control import (
    BrokerSymbolSpec,
    size_from_broker_specs,
)
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.r_math import is_stop_improvement
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    lot_dollar_risk,
    normalize_lots_against_broker,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

OPENED = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _account(equity: Decimal = Decimal("2000")) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=equity,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=500,
    )


def _fx_spec(**overrides: object) -> BrokerSymbolSpec:
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "contract_size": Decimal("100000"),
        "volume_min": Decimal("0.01"),
        "volume_max": Decimal("100"),
        "volume_step": Decimal("0.01"),
        "tick_size": Decimal("0.00001"),
        "tick_value": Decimal("1"),
    }
    base.update(overrides)
    return BrokerSymbolSpec(**base)  # type: ignore[arg-type]


def _gold_spec(**overrides: object) -> BrokerSymbolSpec:
    base: dict[str, object] = {
        "symbol": "XAUUSD",
        "contract_size": Decimal("100"),
        "volume_min": Decimal("0.01"),
        "volume_max": Decimal("50"),
        "volume_step": Decimal("0.01"),
        "tick_size": Decimal("0.001"),
        "tick_value": Decimal("0.1"),
    }
    base.update(overrides)
    return BrokerSymbolSpec(**base)  # type: ignore[arg-type]


def _pos_mt5(
    *,
    ticket: int,
    symbol: str,
    volume: Decimal,
    entry: Decimal,
    sl: Decimal,
    side: str = "buy",
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=volume,
        open_price=entry,
        current_price=entry,
        stop_loss=sl,
        take_profit=entry + (entry - sl),
        profit=Decimal("0"),
        magic=260720,
    )


class TestPositionSizingUsdTarget:
    def test_target_is_strictly_above_six(self) -> None:
        assert TARGET_PLANNED_RISK_USD == TARGET_RISK_PER_TRADE_USD
        assert TARGET_PLANNED_RISK_USD > MIN_PLANNED_RISK_USD
        assert Decimal("6.00") == MIN_PLANNED_RISK_USD

    def test_eurusd_sizes_above_six_not_universal_min_lot(self) -> None:
        stop = Decimal("0.00200")  # 20 pips
        sized = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=stop,
            spec=_fx_spec(),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        assert sized.accepted is True
        assert sized.volume > Decimal("0.01")
        assert sized.monetary_loss_at_sl > MIN_PLANNED_RISK_USD
        # 0.03 = $6.00 (not > $6) → step to 0.04 = $8.00
        assert sized.volume == Decimal("0.04")
        assert sized.monetary_loss_at_sl == Decimal("8.00")

    def test_usdjpy_uses_tick_value(self) -> None:
        spec = _fx_spec(
            symbol="USDJPY",
            tick_size=Decimal("0.001"),
            tick_value=Decimal("0.67"),
        )
        sized = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=Decimal("0.200"),
            spec=spec,
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        per_lot = lot_dollar_risk(
            Decimal("1"),
            stop_distance=Decimal("0.200"),
            contract_size=Decimal("100000"),
            tick_size=Decimal("0.001"),
            tick_value=Decimal("0.67"),
        )
        assert sized.accepted is True
        actual = sized.volume * per_lot
        assert actual > MIN_PLANNED_RISK_USD
        assert sized.volume != Decimal("0.01")

    def test_xauusd_allows_min_lot_when_it_fits_remaining_portfolio(self) -> None:
        sized = size_from_broker_specs(
            equity=Decimal("500"),
            risk_pct=Decimal("1.0"),
            stop_distance=Decimal("10.00"),
            spec=_gold_spec(),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        min_loss = Decimal("0.01") * Decimal("100") * Decimal("10.00")
        assert min_loss > TARGET_PLANNED_RISK_USD
        assert min_loss <= MAX_TOTAL_PLANNED_RISK_USD
        assert sized.accepted is True
        assert sized.volume == Decimal("0.01")
        assert sized.monetary_loss_at_sl == min_loss

    def test_xauusd_rejects_when_min_lot_exceeds_remaining_portfolio(self) -> None:
        sized = size_from_broker_specs(
            equity=Decimal("500"),
            risk_pct=Decimal("1.0"),
            stop_distance=Decimal("10.00"),
            spec=_gold_spec(),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
            remaining_portfolio_risk=Decimal("8.00"),
        )
        assert sized.accepted is False
        assert sized.volume == Decimal("0")
        assert sized.monetary_loss_at_sl >= Decimal("10.00")

    def test_volume_step_and_max_are_respected(self) -> None:
        spec = _fx_spec(volume_step=Decimal("0.05"), volume_max=Decimal("0.10"))
        sized = size_from_broker_specs(
            equity=Decimal("5000"),
            risk_pct=Decimal("1.0"),
            stop_distance=Decimal("0.00100"),
            spec=spec,
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        assert sized.accepted is True
        assert sized.volume % Decimal("0.05") == Decimal("0")
        assert sized.volume <= Decimal("0.10")
        assert sized.monetary_loss_at_sl > MIN_PLANNED_RISK_USD

    def test_invalid_stop_rejects(self) -> None:
        sized = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=Decimal("0"),
            spec=_fx_spec(),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        assert sized.accepted is False

    def test_different_fx_symbols_produce_different_volumes(self) -> None:
        stop_fx = Decimal("0.00200")
        eurusd = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=stop_fx,
            spec=_fx_spec(symbol="EURUSD"),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        gbpusd = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=stop_fx,
            spec=_fx_spec(symbol="GBPUSD", tick_value=Decimal("1.25")),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        usdjpy = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=Decimal("0.200"),
            spec=_fx_spec(
                symbol="USDJPY",
                tick_size=Decimal("0.001"),
                tick_value=Decimal("0.67"),
            ),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
        )
        assert eurusd.accepted and gbpusd.accepted and usdjpy.accepted
        assert eurusd.volume != gbpusd.volume
        assert Decimal("0.01") not in {
            eurusd.volume,
            gbpusd.volume,
            usdjpy.volume,
        }
        for sized in (eurusd, gbpusd, usdjpy):
            assert sized.monetary_loss_at_sl > MIN_PLANNED_RISK_USD

    def test_volume_min_rejected_when_next_step_exceeds_remaining(self) -> None:
        spec = _fx_spec(volume_min=Decimal("0.10"), volume_step=Decimal("0.01"))
        sized = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=Decimal("0.00200"),
            spec=spec,
            max_risk_amount=TARGET_PLANNED_RISK_USD,
            remaining_portfolio_risk=Decimal("10.00"),
        )
        # 0.10 * $200/lot = $20 > remaining $10
        assert sized.accepted is False
        assert sized.volume == Decimal("0")

    def test_next_step_exceeding_remaining_does_not_force_trade(self) -> None:
        sized = size_from_broker_specs(
            equity=Decimal("2000"),
            risk_pct=Decimal("0.50"),
            stop_distance=Decimal("0.00200"),
            spec=_fx_spec(),
            max_risk_amount=TARGET_PLANNED_RISK_USD,
            remaining_portfolio_risk=Decimal("7.00"),
        )
        # 0.03 = $6 (not > $6); 0.04 = $8 > remaining $7 → no trade
        assert sized.accepted is False
        assert sized.volume == Decimal("0")

    def test_dynamic_v2_fx_not_universal_min_lot(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("2000"),
            stop_distance=Decimal("0.00200"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100000"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("50"),
            tick_size=Decimal("0.00001"),
            tick_value=Decimal("1"),
            quality_score=90,
            confidence=88,
            quality_reject=False,
            log=False,
        )
        assert d.valid is True
        assert d.final_lot > Decimal("0.01")
        extra = d.extras.get("actual_estimated_risk")
        assert extra is not None
        assert Decimal(str(extra)) > MIN_PLANNED_RISK_USD


class TestAggregatePlannedRisk:
    def test_six_plus_six_allowed_thirty_plus_blocked(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(
                max_open_positions=10,
                min_lot=Decimal("0.01"),
                contract_size=Decimal("100"),
                target_risk_per_trade_usd=TARGET_PLANNED_RISK_USD,
                min_planned_risk_usd=MIN_PLANNED_RISK_USD,
                max_total_planned_risk_usd=MAX_TOTAL_PLANNED_RISK_USD,
                max_symbol_exposure_pct=Decimal("200"),
                max_asset_class_exposure_pct=Decimal("200"),
                max_total_exposure_pct=Decimal("500"),
                max_correlated_exposure_pct=Decimal("200"),
            )
        )
        one = _pos_mt5(
            ticket=11,
            symbol="XAUUSD",
            volume=Decimal("0.01"),
            entry=Decimal("2300"),
            sl=Decimal("2294"),
        )
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="agg-12",
            symbol="XAUUSD",
            side="buy",
            stop_loss_distance=Decimal("6.00"),
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=Decimal("2300"),
            contract_size=Decimal("100"),
        )
        two = engine.evaluate(check, account=_account(), positions=[one])
        assert two.decision is not RiskDecision.REJECT

        five = [
            _pos_mt5(
                ticket=20 + i,
                symbol="XAUUSD",
                volume=Decimal("0.01"),
                entry=Decimal("2300"),
                sl=Decimal("2294"),
            )
            for i in range(5)
        ]
        sixth = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="agg-30",
                symbol="XAUUSD",
                side="buy",
                stop_loss_distance=Decimal("6.00"),
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=Decimal("2300"),
                contract_size=Decimal("100"),
            ),
            account=_account(),
            positions=five,
        )
        assert sixth.decision is RiskDecision.REJECT
        joined = " ".join(sixth.reasons)
        assert "aggregate planned SL risk" in joined
        assert Decimal("30.00") == MAX_TOTAL_PLANNED_RISK_USD

    def test_daily_loss_protection_still_rejects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.risk_lock_override."
            "risk_lock_override_enabled",
            lambda: False,
        )
        engine = RiskEngine(
            config=RiskEngineConfig(
                max_open_positions=10,
                min_lot=Decimal("0.01"),
                contract_size=Decimal("100000"),
                target_risk_per_trade_usd=TARGET_PLANNED_RISK_USD,
                min_planned_risk_usd=MIN_PLANNED_RISK_USD,
                max_total_planned_risk_usd=MAX_TOTAL_PLANNED_RISK_USD,
                max_daily_loss_pct=Decimal("5.00"),
                max_symbol_exposure_pct=Decimal("200"),
                max_asset_class_exposure_pct=Decimal("200"),
                max_total_exposure_pct=Decimal("500"),
                max_correlated_exposure_pct=Decimal("200"),
            )
        )
        blocked = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="daily-loss",
                symbol="EURUSD",
                side="buy",
                stop_loss_distance=Decimal("0.00200"),
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=Decimal("1.10000"),
                contract_size=Decimal("100000"),
                tick_size=Decimal("0.00001"),
                tick_value=Decimal("1"),
            ),
            account=_account(),
            positions=[],
            daily_pnl=Decimal("-120"),
        )
        assert blocked.decision is RiskDecision.REJECT
        assert any("daily loss" in r.lower() for r in blocked.reasons)


class TestPmeProfitProtection:
    def _managed(self) -> ManagedPosition:
        return ManagedPosition(
            ticket=501,
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            initial_volume=Decimal("0.20"),
            remaining_volume=Decimal("0.20"),
            initial_stop=Decimal("2290"),
            risk_distance=Decimal("10"),
            opened_at=OPENED,
            state=PositionLifecycleState.OPEN,
            current_stop=Decimal("2290"),
            current_tp=Decimal("2330"),
        )

    def _ctx(self, price: Decimal, **kwargs: object) -> PositionManageContext:
        base: dict[str, object] = {
            "now": OPENED + timedelta(minutes=5),
            "current_price": price,
            "atr": Decimal("5"),
            "mid_price": price,
            "spread": Decimal("0.30"),
            "market_open": True,
            "connection_stable": True,
            "position_still_open": True,
            "user_id": uuid4(),
        }
        base.update(kwargs)
        return PositionManageContext(**base)  # type: ignore[arg-type]

    def test_be_at_point_eight_r_not_tiny_fluctuation(self) -> None:
        svc = InstitutionalPositionManagement.create(RecordingOmsManagePort())
        svc.engine.config = pme_config_for_scalping()
        pos = self._managed()
        pos.trade_class = "SCALP"
        svc.register(pos)
        tiny = svc.evaluate(501, self._ctx(Decimal("2304")))  # 0.4R
        assert tiny.action is not ManageActionKind.BREAK_EVEN
        be = svc.evaluate(501, self._ctx(Decimal("2308")))  # 0.8R
        assert be.action is ManageActionKind.BREAK_EVEN
        assert be.position.be_moved is True

    def test_be_idempotent_on_second_tick(self) -> None:
        svc = InstitutionalPositionManagement.create(RecordingOmsManagePort())
        svc.engine.config = pme_config_for_scalping()
        pos = self._managed()
        pos.trade_class = "SCALP"
        svc.register(pos)
        first = svc.evaluate(501, self._ctx(Decimal("2308")))
        assert first.action is ManageActionKind.BREAK_EVEN
        second = svc.evaluate(501, self._ctx(Decimal("2308")))
        assert second.skipped is True or second.action in {
            ManageActionKind.SKIP,
            ManageActionKind.NOOP,
            ManageActionKind.BREAK_EVEN,
        }

    def test_trail_never_widens_stop(self) -> None:
        pos = self._managed()
        pos.current_stop = Decimal("2302")
        assert is_stop_improvement(pos, Decimal("2305")) is True
        assert is_stop_improvement(pos, Decimal("2295")) is False

    def test_partial_skipped_below_min_volume(self) -> None:
        out = normalize_lots_against_broker(
            calculated_lot=Decimal("0.01"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("10"),
            equity=Decimal("2000"),
            stop_distance=Decimal("2.00"),
            contract_size=Decimal("100"),
            risk_budget=Decimal("6.00"),
        )
        assert out.approved is True
        from app.domain.institutional_trading.management.config import (
            PositionManagementConfig,
        )
        from app.domain.institutional_trading.management.r_math import (
            partial_close_volume,
        )

        pos = self._managed()
        pos.remaining_volume = Decimal("0.01")
        cfg = PositionManagementConfig(
            min_volume=Decimal("0.01"),
            volume_step=Decimal("0.01"),
        )
        assert partial_close_volume(pos, cfg) == Decimal("0")

    def test_failed_pme_action_does_not_claim_success(self) -> None:
        oms = RecordingOmsManagePort(fail_as="failed")
        oms.fail_next = True
        svc = InstitutionalPositionManagement.create(oms)
        svc.engine.config = pme_config_for_scalping()
        pos = self._managed()
        pos.trade_class = "SCALP"
        svc.register(pos)
        result = svc.evaluate(501, self._ctx(Decimal("2308")))
        assert result.action is ManageActionKind.BREAK_EVEN
        assert result.oms_result is not None and not result.oms_result.ok
        assert result.record is not None
        assert result.record.outcome is not ManageOutcome.SUCCESS
        assert pos.be_moved is False
        assert pos.last_manage_fingerprint is None


class TestNoAveragingAndPublicQuiet:
    def test_losing_same_symbol_blocks_pyramid(self) -> None:
        decision = may_add_scalping_trade(
            open_positions=1,
            max_open=10,
            new_confidence=90,
            best_open_confidence=80,
            new_direction="BUY",
            open_directions=("BUY",),
            entry=Decimal("2300"),
            open_entries=(Decimal("2295"),),
            require_improvement=False,
            open_profits=(Decimal("-12.50"),),
            require_unrealized_profit=True,
            same_direction_profits=(Decimal("-12.50"),),
        )
        assert decision.allow is False
        assert "never average" in decision.reason.lower() or "P/L" in decision.reason

    def test_rejected_and_no_ticket_stay_off_public_channel(self) -> None:
        quiet = public_channel_notices(
            [
                {"event": "SIGNAL_GENERATED", "opportunity": "88", "direction": "BUY"},
                {"event": "RISK_BLOCKED", "opportunity": "91", "direction": "BUY"},
            ]
        )
        assert quiet == []

    def _public_fields(
        self, *, opportunity: str, ticket: int | None
    ) -> dict[str, object]:
        fields: dict[str, object] = {
            "symbol": "EURUSD",
            "direction": "BUY",
            "opportunity": opportunity,
            "entry": "1.10000",
            "stop_loss": "1.09800",
            "take_profit": "1.10400",
        }
        if ticket is not None:
            fields["ticket"] = ticket
        return fields

    def test_score_at_or_below_70_stays_private(self) -> None:
        notices = [
            {
                "event": TRADE_OPENED,
                "fields": self._public_fields(opportunity="70", ticket=551001),
            }
        ]
        assert public_channel_notices(notices) == []

    def test_no_ticket_stays_private(self) -> None:
        notices = [
            {
                "event": TRADE_OPENED,
                "fields": self._public_fields(opportunity="88", ticket=None),
            }
        ]
        assert public_channel_notices(notices) == []

    def test_real_ticket_and_score_above_70_is_public(self) -> None:
        notices = [
            {
                "event": TRADE_OPENED,
                "fields": self._public_fields(opportunity="88", ticket=551002),
            }
        ]
        public = public_channel_notices(notices)
        events = [row["event"] for row in public]
        assert SIGNAL_CONFIRMED in events
        assert TRADE_OPENED in events

    def test_telegram_and_jimvio_share_the_same_public_events(self) -> None:
        notices = [
            {
                "event": TRADE_OPENED,
                "fields": self._public_fields(opportunity="91", ticket=551003),
            }
        ]
        public = public_channel_notices(notices)
        assert public
        for row in public:
            assert map_jimvio_event_type(str(row["event"])) is not None


class TestWorkerContinuesAfterIsolate:
    def test_one_rejected_symbol_does_not_drop_the_universe(self) -> None:
        from dataclasses import replace

        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )
        from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
            scan_multi_asset_portfolio,
        )
        from app.domain.institutional_trading.ai_scalping.symbol_state import (
            SymbolStateBook,
        )

        healthy = {
            "symbol": "EURJPY",
            "reject": False,
            "direction": "BUY",
            "ai_confidence": 90,
            "trade_quality": 91,
            "spread_score": 85,
            "liquidity": 80,
            "execution_health_ok": True,
            "atr_pct": "0.12",
        }
        poisoned = {
            "symbol": "GBPUSD",
            "reject": True,
            "reject_reason": "SPREAD_BLOCK",
            "direction": "NONE",
            "spread_score": 0,
        }
        timeout = {
            "symbol": "USDJPY",
            "reject": True,
            "reject_reason": "SYMBOL_TIMEOUT",
            "direction": "NONE",
            "context_status": "SYMBOL_TIMEOUT",
            "failure_class": "SYMBOL_FAILURE",
        }
        out = scan_multi_asset_portfolio(
            [healthy, poisoned, timeout],
            open_positions=0,
            config=replace(
                DEFAULT_AI_SCALPING_CONFIG,
                universe=("EURJPY", "GBPUSD", "USDJPY"),
            ),
            state_book=SymbolStateBook(),
        )
        symbols = {r.symbol for r in out.rows}
        assert "EURJPY" in symbols
        assert "GBPUSD" in symbols
        assert "USDJPY" in symbols

    def test_cycle_timeout_rotates_instead_of_halting(self) -> None:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            classify_candidate_outcome,
        )
        from app.domain.institutional_trading.operations.worker_runtime_state import (
            cycle_hard_timeout_seconds,
        )

        assert cycle_hard_timeout_seconds(60.0) >= 180.0
        cls = classify_candidate_outcome(
            abort_reason="CYCLE_TIMEOUT",
            cycle_outcome="error",
            decision_action="NO_TRADE",
        )
        assert cls["skip_idle_sleep"] is True
        assert cls["release_entry_budget"] is True
        assert cls["candidate_action"] in {"ROTATE_FOCUS", "WAIT_SAME_FOCUS"}
