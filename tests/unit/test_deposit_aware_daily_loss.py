"""Verified MT5 deposit recalibrates UTC daily-loss baseline — never a bypass."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.application.services.ite_cycle_market_context import (
    build_ite_cycle_market_context,
)
from app.application.services.live_account_risk_tracker import (
    LiveAccountRiskTracker,
    reset_live_account_risk_tracker_for_tests,
)
from app.application.services.live_trading_control_service import (
    _overlay_trusted_daily_pnl,
)
from app.domain.entities.mt5 import MT5AccountInfo
from app.domain.entities.mt5_market import MT5Rate
from app.domain.entities.mt5_portfolio import MT5Deal
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.operations.daily_loss_lock import (
    sync_utc_daily_loss_lock,
    utc_daily_loss_exceeded,
)
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.gateway_client import (
    GatewayMT5Client,
    mt5_history_deal_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _deal(
    *,
    profit: str,
    when: datetime,
    volume: str = "0.01",
    ticket: int = 1,
    deal_type: str = "entry_out",
) -> MT5Deal:
    return MT5Deal(
        ticket=ticket,
        order_ticket=ticket,
        symbol="XAUUSD",
        side="buy",
        volume=Decimal(volume),
        price=Decimal("2300"),
        profit=Decimal(profit),
        commission=Decimal("0"),
        swap=Decimal("0"),
        deal_type=deal_type,
        time=when,
    )


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    reset_live_account_risk_tracker_for_tests()
    yield
    reset_live_account_risk_tracker_for_tests()


def _plane(*, exceeded: bool) -> SimpleNamespace:
    plane = SimpleNamespace(daily_loss_exceeded=exceeded)

    def _flag(now: datetime | None = None) -> None:
        plane.daily_loss_exceeded = True

    def _clear(now: datetime | None = None, reason: str = "") -> bool:
        plane.daily_loss_exceeded = False
        return True

    plane.flag_daily_loss = _flag
    plane.clear_daily_loss = _clear
    return plane


def test_max_daily_loss_cap_is_80() -> None:
    assert Decimal("80.0") == MAX_DAILY_LOSS_PCT


def test_verified_deposit_clears_latch_via_existing_lock_not_assignment() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
    deals = [
        _deal(profit="-200", when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC), ticket=1),
        _deal(
            profit="400",
            when=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            ticket=2,
            volume="0",
            deal_type="balance",
        ),
    ]
    daily = LiveAccountRiskTracker.daily_pnl_from_deals(
        deals, now=now, ending_balance=Decimal("400")
    )
    assert daily == Decimal("0")
    plane = _plane(exceeded=True)
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=daily,
        equity=Decimal("400"),
        balance=Decimal("400"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
        now=now,
    )
    assert plane.daily_loss_exceeded is False
    assert out["daily_loss_exceeded"] is False
    assert out["rearm_state"] == "REARMED"


def test_deposit_then_additional_loss_still_blocks_when_over_80() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
    deals = [
        _deal(profit="-100", when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC), ticket=1),
        _deal(
            profit="100",
            when=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            ticket=2,
            volume="0",
            deal_type="balance",
        ),
        _deal(profit="-161", when=datetime(2026, 9, 1, 13, 0, tzinfo=UTC), ticket=3),
    ]
    daily = LiveAccountRiskTracker.daily_pnl_from_deals(
        deals, now=now, ending_balance=Decimal("200")
    )
    assert daily == Decimal("-161")
    assert utc_daily_loss_exceeded(
        daily_pnl=daily,
        equity=Decimal("200"),
        balance=Decimal("200"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    plane = _plane(exceeded=True)
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=daily,
        equity=Decimal("200"),
        balance=Decimal("200"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
        now=now,
    )
    assert plane.daily_loss_exceeded is True
    assert out["daily_loss_exceeded"] is True


def test_untrusted_history_does_not_clear_latch_with_cached_baseline() -> None:
    plane = _plane(exceeded=True)
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("400"),
        balance=Decimal("400"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=False,
    )
    assert plane.daily_loss_exceeded is True
    assert out["daily_loss_exceeded"] is True
    assert out["daily_loss_lock"] == "UNKNOWN"


def _pass_facts(**overrides: object) -> AutoTradeLiveFacts:
    base: dict[str, object] = {
        "gateway_connected": True,
        "broker_connected": True,
        "market_data_live": True,
        "risk_engine_pass": True,
        "account_trading_enabled": True,
        "mt5_autotrading_enabled": True,
        "symbol": "XAUUSD",
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


def test_auto_trade_unverified_deposit_keeps_verification_required_copy() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _pass_facts(
            daily_loss_exceeded=True,
            daily_pnl_verified=True,
            deposit_verification="required",
        ),
    )
    assert result.allowed is False
    assert (
        "Maximum daily loss exceeded — deposit verification required."
        in result.failed_reasons
    )


def test_auto_trade_verified_but_still_over_40_stays_blocked() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _pass_facts(
            daily_loss_exceeded=True,
            daily_pnl_verified=True,
            deposit_verification="verified",
        ),
    )
    assert result.allowed is False
    assert "Maximum daily loss exceeded" in result.failed_reasons
    assert "deposit verification required" not in " ".join(result.failed_reasons)


def test_stale_untrusted_overlay_does_not_advertise_new_capital() -> None:
    runtime = SimpleNamespace(
        _last_cycle=SimpleNamespace(
            market_context_diagnostics={
                "daily_pnl_fail_closed": True,
                "daily_pnl_trusted": False,
                "new_capital_detected": True,
                "capital_baseline": {"deposit_amount": "999"},
                "deposit_verification": "verified",
            }
        )
    )
    with patch(
        "app.application.services.institutional_ite_runtime.get_ite_runtime",
        return_value=runtime,
    ):
        out: dict[str, Any] = {"new_capital_detected": True}
        _overlay_trusted_daily_pnl(out)
    assert out["daily_pnl_status"] == "UNAVAILABLE"
    assert out["new_capital_detected"] is False
    assert out.get("deposit_verification") is None


def test_mt5_history_deal_kind_maps_balance_and_credit() -> None:
    assert mt5_history_deal_kind(typ=2, entry=0) == "balance"
    assert mt5_history_deal_kind(typ=3, entry=0) == "credit"
    assert mt5_history_deal_kind(typ=0, entry=0) == "entry_in"
    assert mt5_history_deal_kind(typ=1, entry=1) == "entry_out"


def test_gateway_history_deals_keeps_volume_zero_balance_credit() -> None:
    client = GatewayMT5Client(base_url="http://gw.test", token="t")
    client._connected = True
    now_ts = int(datetime(2026, 9, 1, 12, 0, tzinfo=UTC).timestamp())

    def _request(method: str, path: str, **_kwargs: Any) -> dict[str, Any]:
        assert method == "GET"
        assert path == "/history/deals"
        return {
            "items": [
                {
                    "ticket": 101,
                    "type": 2,
                    "entry": 0,
                    "symbol": "",
                    "volume": 0,
                    "profit": 500,
                    "commission": 0,
                    "swap": 0,
                    "time": now_ts,
                },
                {
                    "ticket": 102,
                    "type": 0,
                    "entry": 1,
                    "symbol": "",
                    "volume": 0.01,
                    "profit": -12,
                    "time": now_ts,
                },
                {
                    "ticket": 103,
                    "type": 0,
                    "entry": 1,
                    "symbol": "XAUUSD",
                    "volume": 0.01,
                    "profit": -12,
                    "time": now_ts,
                },
            ]
        }

    client._request = _request  # type: ignore[method-assign]
    deals = client.history_deals()
    by_ticket = {int(d.ticket): d for d in deals}
    assert 101 in by_ticket
    assert by_ticket[101].deal_type == "balance"
    assert by_ticket[101].volume == Decimal("0")
    assert 102 not in by_ticket
    assert 103 in by_ticket


def _rate(tf: Timeframe, i: int) -> MT5Rate:
    base = Decimal("2300") + Decimal(i)
    return MT5Rate(
        symbol="XAUUSD",
        timeframe=tf,
        open_time=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        open=base,
        high=base + Decimal("1"),
        low=base - Decimal("1"),
        close=base + Decimal("0.5"),
        tick_volume=10,
        real_volume=Decimal("1"),
    )


def _ready_adapter(history_deals: list[Any]) -> MagicMock:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    ud._CATALOGUE_CACHE = None
    adapter = MagicMock()
    adapter.client = MagicMock()
    adapter.client.is_connected = True
    adapter.client.session_mode = "attached"
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3)
    ]

    def _bars(symbol: Any, tf: Any, start: Any, count: int) -> list[MT5Rate]:
        return [_rate(tf, i) for i in range(count)]

    adapter.copy_rates_from_pos.side_effect = _bars
    adapter.latest_tick.return_value = SimpleNamespace(
        bid=Decimal("2300"),
        ask=Decimal("2300.4"),
        mid=Decimal("2300.2"),
        volume=Decimal("1"),
        timestamp=datetime.now(UTC),
    )
    adapter.account_info.return_value = MT5AccountInfo(
        login=4242,
        name="demo",
        server="Weltrade-Demo",
        equity=Decimal("400"),
        balance=Decimal("400"),
        free_margin=Decimal("400"),
        margin=Decimal("0"),
        leverage=100,
        trade_mode="demo",
    )
    adapter.list_positions.return_value = []
    adapter.history_deals = MagicMock(return_value=history_deals)
    return adapter


@pytest.mark.asyncio
async def test_ite_cycle_verified_deposit_sets_audit_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    deals = [
        _deal(profit="-200", when=now.replace(hour=10, minute=0, second=0), ticket=1),
        _deal(
            profit="400",
            when=now.replace(hour=12, minute=0, second=0),
            ticket=2,
            volume="0",
            deal_type="balance",
        ),
    ]
    adapter = _ready_adapter(deals)

    async def _fake_analyze(*_a: Any, **_k: Any) -> SimpleNamespace:
        return SimpleNamespace(
            symbol="XAUUSD",
            atr=Decimal("1"),
            spread=Decimal("0.4"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"),
                allowed=True,
            ),
        )

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *_a, **_k: SimpleNamespace(
            mt5_positions=0,
            internal_positions=0,
            repaired=False,
            tickets=[],
        ),
    )
    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.diagnostics.get("daily_pnl_trusted") is True
    assert ctx.diagnostics.get("new_capital_detected") is True
    assert ctx.diagnostics.get("deposit_verification") == "verified"
    assert ctx.diagnostics.get("max_daily_loss_limit_pct") == "80.0"
    baseline = ctx.diagnostics.get("capital_baseline")
    assert isinstance(baseline, dict)
    assert baseline.get("broker_deal_ticket") == 2
    assert ctx.account is not None
    assert ctx.account.daily_pnl == Decimal("0")


def test_ui_copy_explains_verified_deposit_without_ignored_loss_language() -> None:
    root = Path(__file__).resolve().parents[2]
    panel = (
        root / "frontend/src/components/ops/live-trading-control-panel.tsx"
    ).read_text(encoding="utf-8")
    desk = (root / "frontend/src/components/ops/auto-trading-workspace.tsx").read_text(
        encoding="utf-8"
    )
    for src in (panel, desk):
        assert "New capital detected" in src
        assert "Risk baseline recalculated from verified deposit" in src
        assert "Maximum daily loss limit:" in src
        assert "Pre-deposit P/L preserved" in src
        assert "Post-deposit risk:" in src
        assert "ignored loss" not in src.lower()
        assert (
            "Maximum daily loss exceeded — deposit verification required." in src
        )
