"""M1 micro-scalping decisions. No broker, no live order."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.m1_micro.config import (
    m1_live_submit_enabled,
    m1_micro_enabled,
)
from app.domain.institutional_trading.m1_micro.engine import evaluate_m1
from app.domain.institutional_trading.m1_micro.exits import exit_reason, reentry_allowed
from app.domain.institutional_trading.m1_micro.signals import Bar

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _trend_bars() -> list[Bar]:
    bars: list[Bar] = []
    for index in range(20):
        base = Decimal("2300") + Decimal(index) * Decimal("0.30")
        bars.append(
            Bar(
                open=base,
                high=base + Decimal("0.80"),
                low=base - Decimal("0.20"),
                close=base + Decimal("0.40"),
            )
        )
    return bars


def test_module_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
    assert m1_micro_enabled() is False
    assert m1_live_submit_enabled() is False
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2310"),
        ask=Decimal("2310.20"),
        higher_timeframe_bias="up",
    )
    assert decision.action == "disabled"
    assert decision.reason == "M1_MICRO_DISABLED"
    assert decision.stop is None


def test_enabled_module_can_propose_a_cost_cleared_buy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
    assert m1_live_submit_enabled() is False
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("0.01"),
    )
    assert decision.action == "buy"
    assert decision.setup == "momentum_continuation"
    assert decision.stop is not None and decision.target is not None
    assert decision.stop < decision.target
    assert decision.reason == "setup_cleared_cost"


def test_opposing_higher_timeframe_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="down",
        slippage_points=Decimal("0.01"),
    )
    assert decision.action == "none"


def test_cost_blocks_a_setup_that_does_not_clear_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("20"),
    )
    assert decision.action == "none"
    assert decision.reason == "cost_not_cleared"


def test_open_position_blocks_a_new_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        open_positions=1,
    )
    assert decision.reason == "shared_book_position_open"


def test_same_signal_is_not_reentered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    first = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("0.01"),
    )
    second = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("0.01"),
        last_signal_id=first.signal_id,
    )
    assert second.reason == "duplicate_or_open_signal"
    assert (
        reentry_allowed(
            last_signal_id=first.signal_id,
            signal_id=first.signal_id,
            thesis_open=False,
        )
        is False
    )


def test_exit_when_the_thesis_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2290"),
        ask=Decimal("2290.20"),
        higher_timeframe_bias="up",
        thesis_open=True,
        side_open="BUY",
        invalidation=Decimal("2295"),
        target_open=Decimal("2320"),
    )
    assert decision.action == "exit"
    assert decision.reason == "thesis_invalidated"
    assert (
        exit_reason(
            side="BUY",
            bid=Decimal("2290"),
            ask=Decimal("2290.20"),
            invalidation=Decimal("2295"),
            target=Decimal("2320"),
        )
        == "thesis_invalidated"
    )


def test_spike_regime_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    bars = _trend_bars()
    last = bars[-1]
    bars[-1] = Bar(
        open=last.open,
        high=last.open + Decimal("30"),
        low=last.open - Decimal("5"),
        close=last.close,
    )
    decision = evaluate_m1(
        bars,
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("0.01"),
    )
    assert decision.action == "none"
    assert decision.reason == "no_setup"


def test_flag_off_ignores_open_risk_and_does_not_change_the_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2310"),
        ask=Decimal("2310.20"),
        higher_timeframe_bias="up",
        open_positions=3,
        planned_risk_pct=Decimal("9"),
        open_planned_risk_pct=Decimal("9"),
        open_risk_known=False,
    )
    assert decision.action == "disabled"
    assert decision.reason == "M1_MICRO_DISABLED"


def test_combined_open_risk_above_nine_percent_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        slippage_points=Decimal("0.01"),
        planned_risk_pct=Decimal("5"),
        open_planned_risk_pct=Decimal("5"),
    )
    assert decision.action == "none"
    assert decision.reason == "combined_planned_risk_above_9_percent"


def test_unknown_open_risk_blocks_a_new_m1_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    decision = evaluate_m1(
        _trend_bars(),
        bid=Decimal("2306.10"),
        ask=Decimal("2306.30"),
        higher_timeframe_bias="up",
        open_risk_known=False,
    )
    assert decision.reason == "open_planned_risk_unmeasured"


def test_flag_off_does_not_read_the_market_or_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.m1_micro.live_bridge import (
        consider_m1_complement,
    )

    monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)

    class _Boom:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(name)

    note = consider_m1_complement(
        adapter=_Boom(),
        account=_Boom(),
        snapshot=_Boom(),
        execution_enabled=True,
        primary_forwarded=False,
        submit_market=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("submit")),
    )
    assert note is None


def test_live_submit_flag_off_records_a_setup_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.domain.institutional_trading.m1_micro.live_bridge import (
        consider_m1_complement,
    )

    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
    sent: list[object] = []
    note = consider_m1_complement(
        adapter=_m1_adapter(),
        account=SimpleNamespace(equity=Decimal("1000"), login=1),
        snapshot=_m1_snapshot(),
        execution_enabled=True,
        primary_forwarded=False,
        submit_market=lambda **kwargs: sent.append(kwargs),
        user_id=uuid4(),
    )
    assert note is not None
    assert note["action"] == "buy"
    assert note["submitted"] is False
    assert note["submit_withheld"] == "live_submit_not_authorized"
    assert sent == []


def test_authorized_m1_submit_uses_the_setup_stop_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.domain.institutional_trading.m1_micro.live_bridge import (
        consider_m1_complement,
    )

    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    monkeypatch.setenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", "true")
    sent: list[dict] = []

    def _submit(**kwargs: object) -> SimpleNamespace:
        sent.append(kwargs)
        return SimpleNamespace(
            outcome="rejected",
            retcode=10006,
            order_ticket=None,
            deal_ticket=None,
            message="broker rejected",
        )

    note = consider_m1_complement(
        adapter=_m1_adapter(),
        account=SimpleNamespace(equity=Decimal("1000"), login=1),
        snapshot=_m1_snapshot(),
        execution_enabled=True,
        primary_forwarded=False,
        submit_market=_submit,
        user_id=uuid4(),
    )
    assert note is not None
    assert note["submitted"] is True
    assert note["broker_ticket"] is None
    assert len(sent) == 1
    intent = sent[0]["intent"]
    assert intent.stop_loss is not None
    assert str(intent.stop_loss) == note["stop"]
    assert sent[0]["request_id"].startswith("m1-")


def test_primary_forward_blocks_a_second_m1_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.domain.institutional_trading.m1_micro.live_bridge import (
        consider_m1_complement,
    )

    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    monkeypatch.setenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", "true")
    sent: list[object] = []
    note = consider_m1_complement(
        adapter=_m1_adapter(),
        account=SimpleNamespace(equity=Decimal("1000"), login=1),
        snapshot=_m1_snapshot(),
        execution_enabled=True,
        primary_forwarded=True,
        submit_market=lambda **kwargs: sent.append(kwargs),
        user_id=uuid4(),
    )
    assert note is not None
    assert note["submitted"] is False
    assert note["submit_withheld"] == "primary_cycle_already_forwarded"
    assert sent == []


def _m1_adapter() -> object:
    from types import SimpleNamespace

    from app.domain.market_data.timeframe import Timeframe

    bars = _trend_bars()

    class _Adapter:
        def copy_rates_from_pos(
            self, symbol: str, timeframe: object, start: int, count: int
        ) -> list[SimpleNamespace]:
            assert symbol == "XAUUSD"
            assert timeframe is Timeframe.M1
            assert start == 0
            return [
                SimpleNamespace(
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                )
                for bar in bars[:count]
            ]

        def latest_tick(self, symbol: str) -> SimpleNamespace:
            assert symbol == "XAUUSD"
            return SimpleNamespace(bid=Decimal("2306.10"), ask=Decimal("2306.30"))

        def list_positions(self) -> list[object]:
            return []

    return _Adapter()


def _m1_snapshot() -> object:
    from types import SimpleNamespace

    class _Trend:
        def effective_bias(self) -> SimpleNamespace:
            return SimpleNamespace(value="up")

    return SimpleNamespace(symbol="XAUUSD", trend=_Trend())


def test_live_execution_engine_does_not_call_the_m1_module() -> None:
    import inspect

    import app.application.services.institutional_execution_engine as engine

    source = inspect.getsource(engine)
    assert "m1_micro" not in source
    assert "evaluate_m1" not in source


def test_primary_block_still_evaluates_m1(monkeypatch: pytest.MonkeyPatch) -> None:
    import inspect
    from types import SimpleNamespace

    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )

    monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
    cycle = inspect.getsource(InstitutionalIteRuntime._run_cycle)
    assert cycle.count("self._record_m1_complement(") == 3
    after_contract = cycle.split('cycle_outcome="execution_contract"', 1)[1]
    assert after_contract.find("self._record_m1_complement(") < after_contract.find(
        "return result"
    )

    class _Boom:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(name)

    result = SimpleNamespace(
        market_context_diagnostics={},
        decision_action="NO_TRADE",
        forwarded_to_oms=False,
    )
    InstitutionalIteRuntime._record_m1_complement(
        SimpleNamespace(  # type: ignore[arg-type]
            mt5_adapter=_Boom(),
            guarded_submit=None,
            guarded_manage=None,
            user_id=None,
        ),
        result,
        account=SimpleNamespace(login=1),
        snapshot=SimpleNamespace(symbol="XAUUSD"),
        execution_enabled=True,
        force_shadow=False,
        primary_forwarded=False,
    )
    assert result.market_context_diagnostics == {}
    assert result.decision_action == "NO_TRADE"
    assert result.forwarded_to_oms is False
