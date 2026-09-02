"""Phase 2: execution truth, private no-fill reasons, initial planned risk.

Does not create a second Risk/OMS/PME path. Never sends orders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.jimvio_publisher import map_jimvio_event_type
from app.application.services.live_execution_explain import build_execution_explain
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.services.strategy_diagnostics import (
    extract_cycle_diagnostics,
    hourly_scan_rates,
)
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
from app.domain.institutional_trading.config import (
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
    TARGET_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.management.models import ManagedPosition
from app.domain.institutional_trading.management.r_math import is_stop_improvement
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    classify_private_no_fill_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _now() -> datetime:
    return datetime(2026, 9, 2, 14, 0, tzinfo=UTC)


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


def _engine() -> RiskEngine:
    return RiskEngine(
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


def _pos(
    *,
    ticket: int,
    sl: Decimal,
    magic: int = 260720,
    initial_stop: Decimal | None = None,
    volume: Decimal = Decimal("0.01"),
) -> MT5Position:
    entry = Decimal("2300")
    return MT5Position(
        ticket=ticket,
        symbol="XAUUSD",
        side="buy",
        volume=volume,
        open_price=entry,
        current_price=entry,
        stop_loss=sl,
        take_profit=entry + Decimal("10"),
        profit=Decimal("0"),
        magic=magic,
        initial_stop=initial_stop if initial_stop is not None else Decimal("0"),
        initial_volume=volume,
    )


def _public_fields(*, opportunity: str, ticket: int | None) -> dict[str, object]:
    fields: dict[str, object] = {
        "symbol": "XAUUSD",
        "direction": "BUY",
        "opportunity": opportunity,
        "entry": "2300",
        "stop_loss": "2293",
        "take_profit": "2314",
    }
    if ticket is not None:
        fields["ticket"] = ticket
    return fields


class TestExecutionTruth:
    def test_a_oms_forward_without_ticket_is_not_executed(self) -> None:
        row = extract_cycle_diagnostics(
            snapshot=None,
            decision=None,
            cycle_outcome="forwarded",
            decision_action="BUY",
            forwarded_to_oms=True,
            mt5_ticket=None,
            market_context_diagnostics={"opportunity_score": 88},
        )
        assert row["forwarded_to_oms"] is True
        assert row["executed"] is False

    def test_b_real_ticket_is_executed(self) -> None:
        row = extract_cycle_diagnostics(
            snapshot=None,
            decision=None,
            cycle_outcome="forwarded",
            decision_action="SELL",
            forwarded_to_oms=True,
            mt5_ticket=881001,
            market_context_diagnostics={"opportunity_score": 88},
        )
        assert row["executed"] is True
        assert row["mt5_ticket"] == 881001

    def test_c_oms_forward_without_ticket_does_not_increment_fill(self) -> None:
        rates = hourly_scan_rates(
            [
                {
                    "recorded_at": _now().isoformat(),
                    "decision_action": "BUY",
                    "forwarded_to_oms": True,
                    "executed": True,
                    "mt5_ticket": None,
                }
            ],
            now=_now(),
        )
        assert rates["oms_forward"] == 1
        assert rates["executed_count"] == 0
        assert rates["mt5_fills"] == 0
        assert rates["MT5_ticket_count"] == 0

    def test_d_real_ticket_increments_fill(self) -> None:
        rates = hourly_scan_rates(
            [
                {
                    "recorded_at": _now().isoformat(),
                    "decision_action": "SELL",
                    "forwarded_to_oms": True,
                    "mt5_ticket": 881002,
                }
            ],
            now=_now(),
        )
        assert rates["executed_count"] == 1
        assert rates["mt5_fills"] == 1
        assert rates["MT5_ticket_count"] == 1


class TestPrivateReasonsAndPublicFilter:
    def test_e_p_above_70_no_ticket_private_reason_only(self) -> None:
        row = extract_cycle_diagnostics(
            snapshot=None,
            decision=None,
            cycle_outcome="forwarded",
            decision_action="BUY",
            abort_reason="SAFETY_BLOCKED",
            forwarded_to_oms=False,
            mt5_ticket=None,
            market_context_diagnostics={"opportunity_score": 88},
        )
        assert row["private_no_fill_reason"] == "SAFETY_BLOCKED"
        notices = [
            {
                "event": TRADE_OPENED,
                "fields": _public_fields(opportunity="88", ticket=None),
            }
        ]
        assert public_channel_notices(notices) == []

    def test_f_p_above_70_real_ticket_public_notice_allowed(self) -> None:
        row = extract_cycle_diagnostics(
            snapshot=None,
            decision=None,
            cycle_outcome="forwarded",
            decision_action="BUY",
            forwarded_to_oms=True,
            mt5_ticket=881003,
            market_context_diagnostics={"opportunity_score": 91},
        )
        assert row["executed"] is True
        assert row["private_no_fill_reason"] is None
        public = public_channel_notices(
            [
                {
                    "event": TRADE_OPENED,
                    "fields": _public_fields(opportunity="91", ticket=881003),
                }
            ]
        )
        events = [item["event"] for item in public]
        assert SIGNAL_CONFIRMED in events
        assert TRADE_OPENED in events
        for item in public:
            assert map_jimvio_event_type(str(item["event"])) is not None

    def test_g_p_at_or_below_70_no_public_notice(self) -> None:
        row = extract_cycle_diagnostics(
            snapshot=None,
            decision=None,
            cycle_outcome="no_trade",
            decision_action="WAIT",
            forwarded_to_oms=False,
            market_context_diagnostics={"opportunity_score": 70},
        )
        assert row["private_no_fill_reason"] is None
        assert public_channel_notices(
            [
                {
                    "event": TRADE_OPENED,
                    "fields": _public_fields(opportunity="70", ticket=881004),
                }
            ]
        ) == []

    def test_private_reason_codes_cover_approved_set(self) -> None:
        assert (
            classify_private_no_fill_reason(abort_reason="MIN_LOT_EXCEEDS_RISK_BUDGET")
            == "MIN_LOT_EXCEEDS_RISK"
        )
        assert classify_private_no_fill_reason(forwarded_to_oms=True) == "NO_FILL"
        assert (
            classify_private_no_fill_reason(abort_reason="OMS_DUPLICATE")
            == "OMS_REJECTED"
        )


class TestExplainTruth:
    def test_buy_without_ticket_never_says_execute_trade(self) -> None:
        card = build_execution_explain(
            {
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "executed": True,
                "mt5_ticket": None,
                "session_allowed": True,
                "trend": {"aligned": True, "score": 90},
                "quality": {"score": 80, "required": 75, "passed": True},
                "confluence": {"total": 80, "required": 75, "passed": True},
                "sizing": {"approved_lots": "0.01"},
                "rejection": {},
            }
        )
        assert card["execute_trade"] is False
        assert card["verdict"] != "EXECUTE_TRADE"
        assert "EXECUTE TRADE" not in str(card["headline"])
        assert card["verdict"] == "EXECUTION_FAILED"

    def test_buy_with_ticket_is_executed(self) -> None:
        card = build_execution_explain(
            {
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "mt5_ticket": 881005,
                "session_allowed": True,
                "trend": {"aligned": True, "score": 90},
                "quality": {"score": 80, "required": 75, "passed": True},
                "confluence": {"total": 80, "required": 75, "passed": True},
                "sizing": {"approved_lots": "0.01"},
                "rejection": {},
            }
        )
        assert card["execute_trade"] is True
        assert card["verdict"] == "EXECUTED"
        assert "TRADE EXECUTED" in card["headline"]


class TestInitialRiskAndProtection:
    def test_h_initial_risk_counted_after_be(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        legs = [
            _pos(ticket=10 + i, sl=Decimal("2300"), initial_stop=Decimal("2293"))
            for i in range(4)
        ]
        assert _engine().aggregate_planned_sl_risk(legs) == Decimal("28.00")

    def test_i_initial_risk_counted_after_trailing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        trailed = _pos(ticket=20, sl=Decimal("2298"), initial_stop=Decimal("2293"))
        assert _engine().aggregate_planned_sl_risk([trailed]) == Decimal("7.00")

    def test_j_closed_positions_leave_open_aggregate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        engine = _engine()
        open_leg = _pos(ticket=21, sl=Decimal("2293"), initial_stop=Decimal("2293"))
        assert engine.aggregate_planned_sl_risk([open_leg]) == Decimal("7.00")
        assert engine.aggregate_planned_sl_risk([]) == Decimal("0.00")

    def test_k_rejected_and_unlabeled_do_not_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        unlabeled = _pos(
            ticket=22,
            sl=Decimal("2290"),
            magic=0,
            initial_stop=Decimal("2290"),
            volume=Decimal("0.10"),
        )
        assert _engine().aggregate_planned_sl_risk([unlabeled]) == Decimal("0.00")

    def test_l_twenty_eight_plus_seven_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        legs = [
            _pos(ticket=30 + i, sl=Decimal("2300"), initial_stop=Decimal("2293"))
            for i in range(4)
        ]
        result = _engine().evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="phase2-28-7",
                symbol="XAUUSD",
                side="buy",
                stop_loss_distance=Decimal("7.00"),
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=Decimal("2300"),
                contract_size=Decimal("100"),
            ),
            account=_account(),
            positions=legs,
        )
        assert result.decision is RiskDecision.REJECT

    def test_m_twenty_one_plus_seven_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.min_lot_feasibility"
            ".load_initial_leg_facts_fail_open",
            lambda: {},
        )
        legs = [
            _pos(ticket=40 + i, sl=Decimal("2300"), initial_stop=Decimal("2293"))
            for i in range(3)
        ]
        engine = _engine()
        result = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="phase2-21-7",
                symbol="XAUUSD",
                side="buy",
                stop_loss_distance=Decimal("7.00"),
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=Decimal("2300"),
                contract_size=Decimal("100"),
            ),
            account=_account(),
            positions=legs,
        )
        assert result.decision is not RiskDecision.REJECT
        assert engine.aggregate_planned_sl_risk(legs) == Decimal("21.00")
        proposed = (result.approved_lots * Decimal("700")).quantize(Decimal("0.01"))
        assert Decimal("21.00") + proposed <= MAX_TOTAL_PLANNED_RISK_USD

    def test_n_no_averaging_into_losing_positions(self) -> None:
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

    def test_o_stop_cannot_widen(self) -> None:
        pos = ManagedPosition(
            ticket=501,
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("2293"),
            risk_distance=Decimal("7"),
            opened_at=_now(),
            current_stop=Decimal("2302"),
        )
        assert is_stop_improvement(pos, Decimal("2305")) is True
        assert is_stop_improvement(pos, Decimal("2295")) is False


class TestNotificationFailOpen:
    def test_p_public_filter_unchanged_and_empty_is_safe(self) -> None:
        assert public_channel_notices([]) == []
        assert public_channel_notices(
            [
                {"event": "RISK_BLOCKED", "opportunity": "91", "direction": "BUY"},
                {"event": "OMS_REJECTED", "opportunity": "88"},
            ]
        ) == []
