"""Adaptive per-symbol performance states and loss containment."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.entities.risk_engine import contract_size_for_symbol
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.global_market_intelligence import (
    assess_global_market_intelligence,
)
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    check_portfolio_limits,
    scan_multi_asset_portfolio,
)
from app.domain.institutional_trading.ai_scalping.same_symbol_requalification import (
    SetupFingerprint,
    fresh_setup_evidence,
)
from app.domain.institutional_trading.ai_scalping.symbol_performance import (
    CAUTIOUS_MIN_RR_SOFT,
    STATE_CAUTIOUS,
    STATE_NORMAL,
    STATE_OBSERVE,
    STATE_QUARANTINED,
    STATE_STRONG,
    WAIT_SYMBOL_QUARANTINED,
    WAIT_WEAK_EXPECTANCY,
    ClosedOutcome,
    SymbolPerformanceBook,
    apply_symbol_performance_gate,
    resolve_symbol_performance,
)
from app.domain.institutional_trading.config import (
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
    MIN_REWARD_RISK,
)
from app.domain.institutional_trading.live_trading_control import LiveTradingController

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _loss(symbol: str, *, ago_minutes: int = 0) -> ClosedOutcome:
    stamp = datetime.now(UTC) - timedelta(minutes=ago_minutes)
    return ClosedOutcome(
        symbol=symbol,
        pnl=-6.55,
        won=False,
        closed_at=stamp.isoformat(),
        close_reason="stop_loss",
        planned_risk_usd=6.0,
    )


def _win(symbol: str, *, pnl: float = 9.16) -> ClosedOutcome:
    return ClosedOutcome(
        symbol=symbol,
        pnl=pnl,
        won=True,
        closed_at=datetime.now(UTC).isoformat(),
        close_reason="take_profit",
        planned_risk_usd=6.0,
    )


def _book(tmp_path: Path) -> SymbolPerformanceBook:
    return SymbolPerformanceBook(_path=tmp_path / "symbol_performance.json")


def test_observe_does_not_disable_on_one_or_two_trades(tmp_path: Path) -> None:
    book = _book(tmp_path)
    snap = book.evaluate("EURUSD")
    assert snap.symbol_state == STATE_OBSERVE
    assert snap.allow_live_execution is True
    book.record_closed("EURUSD", pnl=-6.2, persist=True)
    snap = book.evaluate("EURUSD")
    assert snap.symbol_state == STATE_OBSERVE
    assert snap.allow_live_execution is True
    code, _ = apply_symbol_performance_gate(snap, expected_rr=1.5)
    assert code is None


def test_two_consecutive_losses_become_cautious(tmp_path: Path) -> None:
    book = _book(tmp_path)
    book.record_closed("LTCUSD", pnl=-6.79)
    book.record_closed("LTCUSD", pnl=-6.55)
    snap = book.evaluate("LTCUSD")
    assert snap.symbol_state == STATE_CAUTIOUS
    assert snap.allow_live_execution is True
    wait, _ = apply_symbol_performance_gate(snap, expected_rr=1.20, base_min_rr=1.3)
    assert wait == WAIT_WEAK_EXPECTANCY
    ok, _ = apply_symbol_performance_gate(snap, expected_rr=1.50, base_min_rr=1.3)
    assert ok is None


def test_three_consecutive_losses_quarantine_that_symbol_only(tmp_path: Path) -> None:
    book = _book(tmp_path)
    for pnl in (-6.79, -6.55, -6.19):
        book.record_closed("LTCUSD", pnl=pnl)
    ltc = book.evaluate("LTCUSD")
    gold = book.evaluate("XAUUSD")
    eurusd = book.evaluate("EURUSD")
    assert ltc.symbol_state == STATE_QUARANTINED
    assert ltc.allow_live_execution is False
    wait, _ = apply_symbol_performance_gate(ltc, expected_rr=1.8)
    assert wait == WAIT_SYMBOL_QUARANTINED
    assert gold.allow_live_execution is True
    assert gold.symbol_state == STATE_OBSERVE
    assert eurusd.allow_live_execution is True


def test_profitable_symbol_can_become_strong(tmp_path: Path) -> None:
    book = _book(tmp_path)
    book.record_closed("XAUUSD", pnl=9.16)
    book.record_closed("XAUUSD", pnl=8.40)
    book.record_closed("XAUUSD", pnl=7.10)
    gold = book.evaluate("XAUUSD")
    assert gold.symbol_state == STATE_STRONG
    assert gold.allow_live_execution is True
    assert gold.expectancy is not None and gold.expectancy > 0
    wait, _ = apply_symbol_performance_gate(gold, expected_rr=1.4)
    assert wait is None


def test_quarantined_symbol_stays_in_scan_rows() -> None:
    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("LTCUSD", "XAUUSD", "EURUSD"),
    )
    scored = [
        {
            "symbol": "LTCUSD",
            "reject": True,
            "reject_reason": WAIT_SYMBOL_QUARANTINED,
            "direction": "BUY",
            "ai_confidence": 80,
            "trade_quality": 82,
            "expected_rr": 1.5,
            "signal_action": "WAIT",
            "symbol_state": STATE_QUARANTINED,
            "symbol_performance": {"symbol_state": STATE_QUARANTINED},
        },
        {
            "symbol": "XAUUSD",
            "reject": False,
            "direction": "SELL",
            "ai_confidence": 84,
            "trade_quality": 86,
            "expected_rr": 1.6,
            "signal_action": "SELL",
            "symbol_state": STATE_STRONG,
            "symbol_performance": {"symbol_state": STATE_STRONG},
        },
        {
            "symbol": "EURUSD",
            "reject": False,
            "direction": "BUY",
            "ai_confidence": 78,
            "trade_quality": 80,
            "expected_rr": 1.45,
            "signal_action": "BUY",
            "symbol_state": STATE_NORMAL,
            "symbol_performance": {"symbol_state": STATE_NORMAL},
        },
    ]
    result = scan_multi_asset_portfolio(scored, config=cfg)
    symbols = {row.symbol for row in result.rows}
    assert symbols >= {"LTCUSD", "XAUUSD", "EURUSD"}
    ranked_syms = [r["symbol"] for r in result.ranked]
    assert "LTCUSD" not in ranked_syms
    assert "XAUUSD" in ranked_syms
    assert "EURUSD" in ranked_syms
    assert result.best is not None
    assert result.best["symbol"] != "LTCUSD"


def test_one_bad_symbol_does_not_stop_signal_generation() -> None:
    ranked = rank_scalping_opportunities(
        [
            {
                "symbol": "LTCUSD",
                "reject": True,
                "reject_reason": WAIT_SYMBOL_QUARANTINED,
                "direction": "BUY",
                "ai_confidence": 90,
                "expected_rr": 2.0,
                "trade_quality": 90,
            },
            {
                "symbol": "XAUUSD",
                "reject": False,
                "direction": "SELL",
                "ai_confidence": 80,
                "expected_rr": 1.5,
                "trade_quality": 84,
            },
        ],
        config=replace(
            DEFAULT_AI_SCALPING_CONFIG, universe=("LTCUSD", "XAUUSD")
        ),
    )
    assert ranked["eligible_count"] == 1
    assert ranked["best"]["symbol"] == "XAUUSD"
    assert ranked["rejected_count"] == 1


def test_requalification_requires_fresh_structure_after_losses() -> None:
    closed = SetupFingerprint(
        direction="BUY",
        setup_family="bos_continuation",
        opportunity_score=74,
        structure_sig="bos=M15:84.1:2026-09-07T10:00:00+00:00",
        regime="weak_trend",
    )
    same = closed
    ok, why = fresh_setup_evidence(closed, same)
    assert ok is False
    assert why == "same_setup_as_closed_trade"
    fresh = SetupFingerprint(
        direction="SELL",
        setup_family="bos_continuation",
        opportunity_score=80,
        structure_sig="bos=M15:86.4:2026-09-07T12:00:00+00:00",
        regime="weak_trend",
    )
    ok2, why2 = fresh_setup_evidence(closed, fresh)
    assert ok2 is True
    assert "direction_changed" in why2 or "structure_changed" in why2


def test_quarantine_expires_to_cautious_not_permanent() -> None:
    now = datetime.now(UTC)
    outcomes = [_loss("LTCUSD", ago_minutes=90 - i) for i in range(3)]
    expired = resolve_symbol_performance(
        outcomes,
        now=now,
        quarantine_until=now - timedelta(minutes=1),
        symbol="LTCUSD",
    )
    assert expired.symbol_state == STATE_CAUTIOUS
    assert expired.allow_live_execution is True
    active = resolve_symbol_performance(
        outcomes,
        now=now,
        quarantine_until=now + timedelta(minutes=40),
        symbol="LTCUSD",
    )
    assert active.symbol_state == STATE_QUARANTINED
    assert active.allow_live_execution is False


def test_no_martingale_and_no_sl_widen_in_module() -> None:
    src = Path(
        "app/domain/institutional_trading/ai_scalping/symbol_performance.py"
    ).read_text(encoding="utf-8")
    assert "never_martingale" in src
    assert "order_send" not in src
    ctrl = LiveTradingController()
    ctrl.note_closed_trade(loss=True, volume=Decimal("1.74"))
    assert ctrl.last_loss_volume == Decimal("1.74")


def test_risk_limits_and_rr_floor_unchanged() -> None:
    assert Decimal("6.00") == MIN_PLANNED_RISK_USD
    assert Decimal("20.00") == MAX_PLANNED_SL_RISK_USD
    assert Decimal("30.00") == MAX_TOTAL_PLANNED_RISK_USD
    assert Decimal("1.00") == MIN_REWARD_RISK
    assert DEFAULT_AI_SCALPING_CONFIG.min_expected_rr >= Decimal("1")
    assert CAUTIOUS_MIN_RR_SOFT >= 1.0
    assert DEFAULT_AI_SCALPING_CONFIG.min_expected_rr >= Decimal("1")


def test_tp_cannot_be_fabricated_wait_code_still_in_scoring() -> None:
    src = Path("app/domain/institutional_trading/ai_scalping/scoring.py").read_text(
        encoding="utf-8"
    )
    assert "WAIT_NO_VALID_TP_ROOM" in src
    assert "do not manufacture rr" in src.lower()


def test_global_intelligence_unknown_stays_unknown_for_crypto() -> None:
    gmi = assess_global_market_intelligence(
        direction="BUY",
        structure_score=0,
        momentum=0,
        liquidity=0,
        expected_rr=None,
        news_blocked=False,
        mtf_alignment=None,
        symbol="LTCUSD",
    )
    crypto = next(layer for layer in gmi.layers if layer.name == "crypto_regime")
    assert crypto.state == "UNKNOWN"
    assert gmi.intelligence_alignment in {"UNKNOWN", "NEUTRAL"}
    assert gmi.wait_recommended is False
    gold = assess_global_market_intelligence(
        direction="SELL",
        structure_score=0,
        momentum=0,
        liquidity=0,
        expected_rr=None,
        news_blocked=False,
        mtf_alignment=None,
        symbol="XAUUSD",
    )
    assert all(layer.name != "crypto_regime" for layer in gold.layers)


def test_crypto_contract_size_does_not_inherit_gold_or_fx() -> None:
    assert contract_size_for_symbol("LTCUSD", default=Decimal("0")) == Decimal("1")
    assert contract_size_for_symbol("BTCUSD", default=Decimal("0")) == Decimal("1")
    assert contract_size_for_symbol("ETHUSD", default=Decimal("0")) == Decimal("1")
    assert contract_size_for_symbol("XAUUSD", default=Decimal("0")) == Decimal("100")
    assert contract_size_for_symbol("EURUSD", default=Decimal("0")) == Decimal(
        "100000"
    )


def test_portfolio_limits_still_block_at_existing_ceilings() -> None:
    blocked, reason = check_portfolio_limits(
        open_positions=3,
        max_open_positions=3,
        daily_loss_pct=Decimal("0"),
        max_daily_loss_pct=Decimal("80"),
        exposure_pct=Decimal("0"),
        max_exposure_pct=Decimal("50"),
    )
    assert blocked is True
    assert reason is not None and "Max open" in reason


def test_restart_reloads_quarantine(tmp_path: Path) -> None:
    book = _book(tmp_path)
    for pnl in (-6.79, -6.55, -6.19):
        book.record_closed("LTCUSD", pnl=pnl)
    assert book.evaluate("LTCUSD").symbol_state == STATE_QUARANTINED
    restored = SymbolPerformanceBook(_path=tmp_path / "symbol_performance.json")
    again = restored.evaluate("LTCUSD")
    assert again.symbol_state == STATE_QUARANTINED
    assert again.allow_live_execution is False
    gold = restored.evaluate("XAUUSD")
    assert gold.allow_live_execution is True


def test_scoring_does_not_apply_global_loss_streak_cooldown() -> None:
    src = Path("app/domain/institutional_trading/ai_scalping/scoring.py").read_text(
        encoding="utf-8"
    )
    assert "WAIT_SYMBOL_QUARANTINED" in src
    assert "WAIT_WEAK_EXPECTANCY" in src
    assert "cooldown_until=None" in src
    assert 'reject_list.append("WAIT_LOSS_STREAK_COOLDOWN")' not in src


def test_global_controller_streak_still_time_boxed() -> None:
    ctrl = LiveTradingController()
    ctrl.note_closed_trade(loss=True, volume=Decimal("1.74"))
    ctrl.note_closed_trade(loss=True, volume=Decimal("1.77"))
    ctrl.note_closed_trade(loss=True, volume=Decimal("1.63"))
    assert ctrl.consecutive_losses == 3
    assert ctrl.loss_streak_cooldown_active() is True
    ctrl.loss_streak_cooldown_until = datetime.now(UTC) - timedelta(minutes=1)
    assert ctrl.loss_streak_cooldown_active() is False
    ctrl.note_closed_trade(loss=False, volume=Decimal("0.04"))
    assert ctrl.consecutive_losses == 0
