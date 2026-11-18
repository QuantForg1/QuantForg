"""Shadow Signal Evaluator: sides, costs, ordering, data gaps, dedup, storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.application.services import shadow_signals as service
from app.domain.institutional_trading.performance_lab import shadow_evaluator as ev
from app.domain.institutional_trading.performance_lab.shadow_evaluator import (
    Costs,
    Quote,
    ShadowSignal,
)

pytestmark = pytest.mark.unit
T0 = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
NO_COST = Costs(slippage=0.0, commission_usd=0.0)


def _q(sec: int, bid: float, spread: float = 0.4) -> Quote:
    return Quote(at=T0 + timedelta(seconds=sec), bid=bid, ask=bid + spread)


def _path(*points: tuple[int, float]) -> list[Quote]:
    return [_q(s, b) for s, b in points]


def _steady(bid: float, *, until: int = 1900, step: int = 20) -> list[Quote]:
    return [_q(s, bid) for s in range(step, until, step)]


def _sig(
    side: str,
    *,
    sid: str = "a",
    sec: int = 0,
    bid: float = 100.0,
    stop: float | None = 2.0,
    accepted: bool = False,
    gate: str | None = "OWNER_MIN_RR: rr 0.8 < 1.5",
) -> ShadowSignal:
    return ShadowSignal(
        signal_id=sid,
        at=T0 + timedelta(seconds=sec),
        side=side,
        bid=bid,
        ask=bid + 0.4,
        stop_atr=stop,
        accepted=accepted,
        blocking_gate=gate,
        quality=89,
        confidence=75,
        strategy="scalping",
        session="london_ny_overlap",
        factors={"trend_strength": 100, "volatility": 70},
    )


def test_buy_enters_at_ask_and_exits_at_bid() -> None:
    out = ev.evaluate_signal(_sig("BUY"), _steady(100.0), NO_COST)
    assert out["entry_price"] == 100.4
    assert out["move_m1"] == pytest.approx(-0.4)  # pays the spread only
    assert out["bracket"] == "timeout"


def test_sell_enters_at_bid_and_exits_at_ask() -> None:
    out = ev.evaluate_signal(_sig("SELL"), _steady(99.0), NO_COST)
    assert out["entry_price"] == 100.0
    assert out["move_m5"] == pytest.approx(100.0 - 99.4)


def test_slippage_and_commission_are_deducted() -> None:
    costs = Costs(slippage=0.05, commission_usd=0.25)
    out = ev.evaluate_signal(_sig("SELL"), _steady(99.0), costs)
    assert out["entry_price"] == pytest.approx(99.95)
    assert out["move_m30"] == pytest.approx(99.95 - 99.45)
    assert out["net_usd_min_lot"] == pytest.approx(0.5 - 0.25)


def test_unknown_commission_leaves_net_unknown() -> None:
    out = ev.evaluate_signal(_sig("SELL"), _steady(99.0), Costs(commission_usd=None))
    assert out["net_usd_min_lot"] is None
    assert "commission_unknown" in out["status_reasons"]


def test_target_then_stop_resolves_in_order() -> None:
    # SELL target 3.0: exit ask <= 97 -> bid <= 96.6 at 40s; stop later ignored.
    later = _path((20, 98.0), (40, 96.5), (60, 103.0)) + _steady(103.0)
    out = ev.evaluate_signal(_sig("SELL"), later, NO_COST)
    assert (out["bracket"], out["r_multiple"], out["status"]) == (
        "target",
        1.5,
        "complete",
    )
    assert out["net_usd_min_lot"] == pytest.approx(3.0)


def test_stop_first_for_buy() -> None:
    later = _path((20, 99.0), (40, 98.0)) + _steady(110.0)
    out = ev.evaluate_signal(_sig("BUY"), later, NO_COST)
    assert (out["bracket"], out["r_multiple"]) == ("stop", -1.0)


def test_level_after_long_gap_is_ambiguous() -> None:
    later = _path((20, 99.8), (80, 96.0)) + _steady(96.0)
    out = ev.evaluate_signal(_sig("SELL"), later, NO_COST)
    assert out["status"] == "ambiguous"
    assert out["bracket"] == "target"


def test_stale_quotes_make_observation_incomplete() -> None:
    later = _path((20, 100.0), (200, 100.0)) + _steady(100.0)
    out = ev.evaluate_signal(_sig("SELL"), later, NO_COST)
    assert out["status"] == "incomplete"
    assert out["status_reasons"][0].startswith("stale_quotes_")
    assert out["net_usd_min_lot"] is None


def test_missing_data_is_incomplete_not_invented() -> None:
    out = ev.evaluate_signal(_sig("SELL"), [], NO_COST)
    assert out["move_m1"] is None and out["status"] == "incomplete"
    out = ev.evaluate_signal(_sig("SELL", stop=None), _steady(99.0), NO_COST)
    assert out["status_reasons"] == ["stop_atr_missing"]


def test_pending_evaluates_once_and_waits_for_window() -> None:
    quotes = _steady(99.0, until=3000)
    signals = [
        _sig("SELL", sid="a"),
        _sig("SELL", sid="a"),
        _sig("SELL", sid="b"),
        _sig("SELL", sid="late", sec=2500),
    ]
    now = T0 + timedelta(minutes=45)
    out = ev.evaluate_pending(signals, quotes, already={"b"}, now=now, costs=NO_COST)
    assert [r["signal_id"] for r in out] == ["a"]


def test_original_gate_kept_and_context_recorded() -> None:
    out = ev.evaluate_signal(_sig("SELL"), _steady(99.0), NO_COST)
    assert out["blocking_gate"] == "OWNER_MIN_RR: rr 0.8 < 1.5"
    assert out["gate_family"] == "OWNER_MIN_RR"
    assert (out["regime_proxy"], out["quality"]) == ("trending", 89)
    assert out["news_condition"] == "clear"
    assert ev.news_condition("High-impact news blackout: FOMC") == "news_blackout"


def test_aggregate_breakdowns_are_labelled_hypothetical() -> None:
    rows = [
        ev.evaluate_signal(_sig("SELL", sid=str(i)), _steady(99.0), NO_COST)
        for i in range(3)
    ]
    rows.append(
        ev.evaluate_signal(
            _sig("BUY", sid="x", accepted=True, gate=None), _steady(99.0), NO_COST
        )
    )
    report = ev.aggregate(rows)
    assert report["label"] == "HYPOTHETICAL"
    assert report["overall"]["evaluated"] == 4
    assert report["by_side"]["SELL"]["positive"] == 3
    assert (
        report["by_rejection_reason"]["OWNER_MIN_RR"]["opportunity_cost_usd_min_lot"]
        > 0
    )
    assert (
        report["by_rejection_reason"]["ACCEPTED"]["opportunity_cost_usd_min_lot"] == 0
    )
    for key in (
        "by_strategy",
        "by_regime_proxy",
        "by_quality_band",
        "by_spread_band",
        "by_hour_utc",
        "by_news_condition",
    ):
        assert report[key]
    assert report["overall"]["evidence"] == "insufficient_data"


def test_persistence_inserts_once_with_conflict_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posts: list[dict[str, Any]] = []
    sig_row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "observed_at": "2026-11-18T15:00:00+00:00",
        "reject": True,
        "blocking_gate": "OWNER_MIN_RR: x",
        "quality": 89,
        "confidence": 75,
        "strategy_id": "scalping",
        "session": "london_ny_overlap",
        "factors": {"trend_strength": 100},
        "shadow": {
            "bid": 100.0,
            "ask": 100.4,
            "stop_atr": 2.0,
            "intended_direction": "SELL",
        },
    }
    quote_rows = [
        {
            "id": f"q{s}",
            "observed_at": (T0 + timedelta(seconds=s)).isoformat(),
            "shadow": {"bid": 99.0, "ask": 99.4},
        }
        for s in range(20, 1900, 20)
    ]

    class _Resp:
        def __init__(self, data: Any) -> None:
            self._data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._data

    class _Client:
        def __init__(self, *a: Any, **k: Any) -> None:
            _ = a, k

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

        def get(self, url: str, *, headers: Any, params: dict[str, str]) -> _Resp:
            _ = headers, params
            if url.endswith("shadow_signal_outcomes"):
                return _Resp([])
            return _Resp([sig_row, *quote_rows])

        def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            params: dict[str, str],
            json: Any,
        ) -> _Resp:
            posts.append(
                {"url": url, "headers": headers, "params": params, "json": json}
            )
            return _Resp(None)

    monkeypatch.setattr(service, "_rest", lambda: ("https://db.example/rest/v1", "k"))
    monkeypatch.setattr(service, "commission_usd", lambda _symbol: 0.0)
    monkeypatch.setattr(httpx, "Client", _Client)
    inserted = service.evaluate_and_store(
        days=1, symbol="XAUUSD", now=T0 + timedelta(hours=1)
    )
    assert inserted == 1
    call = posts[0]
    assert call["params"] == {"on_conflict": "signal_id"}
    assert "ignore-duplicates" in call["headers"]["Prefer"]
    row = call["json"][0]
    assert row["signal_id"] == sig_row["id"]
    assert row["blocking_gate"] == "OWNER_MIN_RR: x"
    assert row["status"] == "complete"


def test_report_unavailable_without_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_rest", lambda: None)
    report = service.build_shadow_signal_report(days=1)
    assert report["available"] is False
    assert report["label"] == "HYPOTHETICAL"
