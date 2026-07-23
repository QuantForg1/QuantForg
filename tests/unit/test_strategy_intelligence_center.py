"""Unit tests — Strategy Intelligence Center (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.strategy_intelligence_center import (
    analyze_trades,
    pair_deals_into_closed_trades,
    score_current_market,
)


def _deal(
    *,
    ticket: int,
    position_id: int,
    deal_type: str,
    time: datetime,
    price: float,
    profit: float = 0.0,
    side: str = "buy",
    volume: float = 0.01,
) -> dict:
    return {
        "ticket": ticket,
        "position_id": position_id,
        "symbol": "XAUUSD",
        "side": side,
        "volume": volume,
        "price": price,
        "profit": profit,
        "commission": 0.0,
        "swap": 0.0,
        "deal_type": deal_type,
        "time": time.isoformat(),
    }


def test_pair_deals_into_closed_trades():
    t0 = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)
    deals = [
        _deal(
            ticket=1,
            position_id=10,
            deal_type="entry_in",
            time=t0,
            price=4000,
        ),
        _deal(
            ticket=2,
            position_id=10,
            deal_type="entry_out",
            time=t0 + timedelta(hours=2),
            price=4010,
            profit=12.5,
        ),
    ]
    closed = pair_deals_into_closed_trades(deals)
    assert len(closed) == 1
    assert closed[0]["profit_loss"] == 12.5
    assert closed[0]["holding_time_sec"] == 7200.0


def _enriched_trade(
    i: int,
    *,
    win: bool,
    session: str,
    mtf: int,
    quality: int,
    confluence: int,
    atr: float,
    spread: float,
    ranging: bool = False,
) -> dict:
    t0 = datetime(2026, 7, 20, 13, 0, tzinfo=UTC) + timedelta(days=i)
    pnl = 15.0 if win else -8.0
    return {
        "id": f"t-{i}",
        "symbol": "XAUUSD",
        "side": "buy",
        "volume": 0.01,
        "entry": 4000 + i,
        "exit": 4010 + i if win else 3995 + i,
        "entry_time": t0.isoformat(),
        "exit_time": (t0 + timedelta(hours=1)).isoformat(),
        "holding_time_sec": 3600,
        "profit_loss": pnl,
        "market_session": session,
        "mtf_score": mtf,
        "mtf_aligned": not ranging,
        "quality": quality,
        "confluence": confluence,
        "atr": atr,
        "spread": spread,
        "stop_distance": 10.0,
        "day_of_week": t0.strftime("%A"),
    }


def test_intelligence_and_patterns_and_score():
    trades = []
    # Winning cluster: london_ny_overlap, high MTF/Q/C, mid ATR, tight spread
    for i in range(4):
        trades.append(
            _enriched_trade(
                i,
                win=True,
                session="london_ny_overlap",
                mtf=84 + i,
                quality=85,
                confluence=87,
                atr=11.0 + i * 0.2,
                spread=0.35,
            )
        )
    # Losing cluster: ranging / high ATR / wide spread
    for i in range(4, 8):
        trades.append(
            _enriched_trade(
                i,
                win=False,
                session="tokyo",
                mtf=50,
                quality=55,
                confluence=48,
                atr=19.0 + (i - 4),
                spread=0.75,
                ranging=True,
            )
        )

    current = {
        "recorded_at": datetime(2026, 7, 23, 14, 0, tzinfo=UTC).isoformat(),
        "market_session": "london_ny_overlap",
        "trend": {"score": 86, "aligned": True},
        "quality": {"score": 88},
        "confluence": {"total": 90},
        "atr": 11.5,
        "spread": 0.32,
    }

    payload = analyze_trades(trades, current_cycle=current)
    assert payload["never_auto_optimizes"] is True
    assert payload["mutates_engines"] is False
    intel = payload["intelligence"]
    assert intel["best_trading_session"] == "london_ny_overlap"
    assert intel["worst_trading_session"] == "tokyo"
    assert intel["average_holding_time_sec"] == 3600.0
    assert intel["average_winning_rr"] is not None

    patterns = payload["patterns"]
    win_when = patterns["winning_trades_usually_occur_when"]
    assert any(s.startswith("MTF >=") for s in win_when)
    assert any(s.startswith("Quality >=") for s in win_when)
    lose_when = patterns["losing_trades_usually_occur_when"]
    assert "Range markets" in lose_when or any("ATR above" in s for s in lose_when)

    score = payload["strategy_intelligence_score"]
    assert score["score"] is not None
    assert score["score"] >= 70
    assert score["level"] == "GREEN"
    assert score["label"] == "Historically Favorable"


def test_score_unfavorable_when_far_from_winners():
    trades = [
        _enriched_trade(
            i,
            win=True,
            session="london_ny_overlap",
            mtf=85,
            quality=86,
            confluence=88,
            atr=10.0,
            spread=0.3,
        )
        for i in range(4)
    ]
    payload = analyze_trades(
        trades,
        current_cycle={
            "market_session": "tokyo",
            "trend": {"score": 40, "aligned": False},
            "quality": {"score": 50},
            "confluence": {"total": 45},
            "atr": 22.0,
            "spread": 0.9,
        },
    )
    score = payload["strategy_intelligence_score"]
    assert score["level"] == "RED"
    assert score["label"] == "Historically Unfavorable"


def test_score_neutral_without_history():
    out = score_current_market(
        current={"market_session": "london"},
        intelligence={},
        patterns={"winning_floors": {}},
    )
    assert out["level"] == "YELLOW"
    assert out["insufficient_history"] is True
