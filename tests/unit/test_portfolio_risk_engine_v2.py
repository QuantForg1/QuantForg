"""Institutional Portfolio Risk Engine v2 — unit contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.correlation_book import (
    correlation_group_name,
    normalize_book_symbol,
    same_correlation_group,
    sector_for,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk_engine_v2 import (
    BrokerComplianceSpec,
    build_portfolio_book,
    evaluate_portfolio_allocation,
)
from app.domain.institutional_trading.decision_models import AccountRiskState


def _pos(
    *,
    ticket: int,
    symbol: str,
    side: str,
    volume: Decimal,
    open_price: Decimal,
    current_price: Decimal,
    profit: Decimal,
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=volume,
        open_price=open_price,
        current_price=current_price,
        profit=profit,
    )


@pytest.mark.unit
class TestCorrelationBook:
    def test_gold_aliases_and_metals_group(self) -> None:
        assert normalize_book_symbol("XAUUSDm") == "XAUUSD"
        assert normalize_book_symbol("GOLD") == "XAUUSD"
        assert correlation_group_name("XAUUSD") == "metals_gold"
        assert same_correlation_group("XAUUSD", "XAGUSD") is True
        assert sector_for("XAUUSD") == "metals"

    def test_fx_majors_share_group(self) -> None:
        assert correlation_group_name("EURUSD") == "usd_majors"
        assert same_correlation_group("EURUSD", "GBPUSD") is True
        assert same_correlation_group("EURUSD", "AUDUSD") is True
        assert same_correlation_group("EURUSD", "XAUUSD") is False


@pytest.mark.unit
class TestWinnerOnlyPyramiding:
    def test_blocks_averaging_into_loser(self) -> None:
        d = may_add_scalping_trade(
            open_positions=1,
            max_open=5,
            new_confidence=90,
            best_open_confidence=80,
            new_direction="BUY",
            open_directions=("BUY",),
            open_profits=(Decimal("-12.5"),),
            require_unrealized_profit=True,
            require_improvement=True,
            min_confidence_delta=5,
        )
        assert d.allow is False
        assert "never average" in d.reason.lower() or "unrealized" in d.reason.lower()

    def test_allows_scale_into_winner(self) -> None:
        d = may_add_scalping_trade(
            open_positions=1,
            max_open=5,
            new_confidence=90,
            best_open_confidence=80,
            new_direction="BUY",
            open_directions=("BUY",),
            open_profits=(Decimal("15.0"),),
            same_direction_profits=(Decimal("15.0"),),
            require_unrealized_profit=True,
            require_improvement=True,
            min_confidence_delta=5,
        )
        assert d.allow is True


@pytest.mark.unit
class TestPortfolioBookAndAllocation:
    def test_book_tracks_symbol_sector_correlation(self) -> None:
        account = AccountRiskState(
            equity=Decimal("1000"),
            balance=Decimal("980"),
            free_margin=Decimal("900"),
            used_margin=Decimal("80"),
            floating_pnl=Decimal("20"),
            open_positions=2,
            daily_pnl=Decimal("5"),
        )
        positions = [
            _pos(
                ticket=1,
                symbol="XAUUSD",
                side="buy",
                volume=Decimal("0.01"),
                open_price=Decimal("2400"),
                current_price=Decimal("2405"),
                profit=Decimal("5"),
            ),
            _pos(
                ticket=2,
                symbol="XAGUSD",
                side="buy",
                volume=Decimal("0.01"),
                open_price=Decimal("30"),
                current_price=Decimal("30.2"),
                profit=Decimal("15"),
            ),
        ]
        book = build_portfolio_book(account=account, positions=positions)
        assert book.floating_pnl == Decimal("20")
        assert book.symbol_exposure["XAUUSD"] > 0
        assert book.sector_exposure["metals"] > 0
        assert book.correlated_exposure["metals_gold"] > 0
        assert book.margin_usage_pct is not None

    def test_never_force_min_lot(self) -> None:
        account = AccountRiskState(
            equity=Decimal("181.53"),
            balance=Decimal("181.53"),
            free_margin=Decimal("181.53"),
            open_positions=0,
        )
        broker = BrokerComplianceSpec(
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("50"),
            contract_size=Decimal("100"),
        )
        alloc = evaluate_portfolio_allocation(
            account=account,
            symbol="XAUUSD",
            stop_distance=Decimal("7.26"),
            risk_pct=Decimal("0.50"),
            quality_score=90,
            confidence=88,
            quality_reject=False,
            broker=broker,
            log=False,
        )
        assert alloc.allow is False
        assert alloc.approved_lots == Decimal("0")
        assert alloc.rejection_reason is not None
        assert "below_min_lot" in (alloc.rejection_reason or "")
        evidence = alloc.evidence
        for key in (
            "timestamp",
            "balance",
            "equity",
            "free_margin",
            "floating_pnl",
            "risk_pct",
            "suggested_lot",
            "calculated_lot",
            "final_lot",
            "broker_limits",
            "quality_score",
            "portfolio_exposure",
            "symbol_exposure",
            "correlation_score",
            "rejection_reason",
        ):
            assert key in evidence

    def test_correlated_exposure_blocks(self) -> None:
        cfg = AiScalpingConfig(
            max_correlated_exposure_pct=Decimal("0.50"),
            max_symbol_exposure_pct=Decimal("5.00"),
            max_daily_exposure_pct=Decimal("5.00"),
            risk_per_trade_pct=Decimal("0.50"),
        )
        account = AccountRiskState(
            equity=Decimal("5000"),
            balance=Decimal("5000"),
            free_margin=Decimal("4500"),
            used_margin=Decimal("200"),
            floating_pnl=Decimal("10"),
            open_positions=2,
        )
        positions = [
            _pos(
                ticket=1,
                symbol="XAUUSD",
                side="buy",
                volume=Decimal("0.10"),
                open_price=Decimal("2400"),
                current_price=Decimal("2401"),
                profit=Decimal("10"),
            ),
            _pos(
                ticket=2,
                symbol="XAGUSD",
                side="buy",
                volume=Decimal("0.10"),
                open_price=Decimal("30"),
                current_price=Decimal("30.1"),
                profit=Decimal("5"),
            ),
        ]
        # 2 correlated metals x 0.50% = 1.00% > max_correlated 0.50%
        alloc = evaluate_portfolio_allocation(
            account=account,
            symbol="XAUUSD",
            stop_distance=Decimal("1.50"),
            positions=positions,
            risk_pct=Decimal("0.50"),
            quality_score=90,
            confidence=88,
            broker=BrokerComplianceSpec(
                min_lot=Decimal("0.01"),
                lot_step=Decimal("0.01"),
                max_lot=Decimal("50"),
                contract_size=Decimal("100"),
            ),
            config=cfg,
            log=False,
        )
        assert alloc.allow is False
        assert "portfolio_limit" in (alloc.rejection_reason or "")

    def test_pyramiding_blocked_on_losing_book(self) -> None:
        account = AccountRiskState(
            equity=Decimal("5000"),
            balance=Decimal("5000"),
            free_margin=Decimal("4800"),
            open_positions=1,
            open_directions=("BUY",),
            open_entries=(Decimal("2400"),),
            best_open_confidence=80,
        )
        positions = [
            _pos(
                ticket=1,
                symbol="XAUUSD",
                side="buy",
                volume=Decimal("0.05"),
                open_price=Decimal("2400"),
                current_price=Decimal("2390"),
                profit=Decimal("-50"),
            )
        ]
        alloc = evaluate_portfolio_allocation(
            account=account,
            symbol="XAUUSD",
            stop_distance=Decimal("1.20"),
            positions=positions,
            new_direction="BUY",
            new_confidence=95,
            entry=Decimal("2395"),
            mid_price=Decimal("2395"),
            risk_pct=Decimal("0.50"),
            quality_score=95,
            confidence=95,
            best_open_confidence=80,
            open_directions=("BUY",),
            open_entries=(Decimal("2400"),),
            min_entry_distance=Decimal("0.50"),
            broker=BrokerComplianceSpec(
                min_lot=Decimal("0.01"),
                lot_step=Decimal("0.01"),
                max_lot=Decimal("50"),
                contract_size=Decimal("100"),
            ),
            config=AiScalpingConfig(
                max_symbol_exposure_pct=Decimal("5.00"),
                max_correlated_exposure_pct=Decimal("5.00"),
                max_daily_exposure_pct=Decimal("5.00"),
                max_sector_exposure_pct=Decimal("5.00"),
                max_currency_exposure_pct=Decimal("5.00"),
                pyramid_winners_only=True,
            ),
            log=False,
        )
        assert alloc.allow is False
        assert alloc.rejection_reason is not None
        assert (
            "loser" in alloc.rejection_reason.lower()
            or "unrealized" in alloc.rejection_reason.lower()
            or "pyramid" in alloc.rejection_reason.lower()
        )

    def test_broker_closeonly_blocks(self) -> None:
        account = AccountRiskState(
            equity=Decimal("5000"),
            free_margin=Decimal("5000"),
            open_positions=0,
        )
        alloc = evaluate_portfolio_allocation(
            account=account,
            symbol="XAUUSD",
            stop_distance=Decimal("1.20"),
            quality_score=95,
            confidence=95,
            broker=BrokerComplianceSpec(
                min_lot=Decimal("0.01"),
                lot_step=Decimal("0.01"),
                max_lot=Decimal("50"),
                contract_size=Decimal("100"),
                trade_mode="closeonly",
            ),
            log=False,
        )
        assert alloc.allow is False
        assert "trade_mode" in (alloc.rejection_reason or "")

    def test_config_defaults(self) -> None:
        cfg = AiScalpingConfig()
        assert cfg.portfolio_risk_engine_v2_enabled is True
        assert cfg.pyramid_winners_only is True
        assert cfg.max_positions_per_symbol == 2
