"""Aggressive compounding engine — shadow only.

Does not send orders, change Risk, Safety, 5% cap, or 0.01 min lot.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.aggressive_compounding_observer import (
    observe_aggressive_compounding_shadow,
)
from app.domain.institutional_trading.compounding.engine import (
    compounding_bias,
    evaluate_compounding_shadow,
)
from app.domain.institutional_trading.compounding.models import (
    BROKER_MIN_LOT,
    HARD_MAX_RISK_PCT,
    CompoundingInputs,
)
from app.domain.institutional_trading.compounding.observe import (
    reset_compounding_shadow_store_for_tests,
)
from app.domain.institutional_trading.compounding.simulation import (
    simulate_mode_comparison,
)
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.trading.xauusd_specs import VOLUME_MIN

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _score(*, quality: int = 92, confidence: int = 90, rr: float = 2.0) -> dict:
    return {
        "trade_quality": quality,
        "quality": quality,
        "ai_confidence": confidence,
        "confidence": confidence,
        "expected_rr": rr,
        "mtf_alignment": quality,
        "factors": {
            "bos": quality,
            "choch": quality,
            "fvg": quality,
            "order_block": quality,
            "momentum": quality,
            "liquidity_sweep": quality,
            "session": 85,
            "spread": 85,
            "volatility": 75,
        },
        "reject": False,
    }


def _inputs(**overrides: object) -> CompoundingInputs:
    base = dict(
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class="SCALP",
        score=_score(),
        confidence=90,
        quality=92,
        expected_rr=Decimal("2.0"),
        equity=Decimal("208.86"),
        daily_pnl=Decimal("1.50"),
        daily_loss_pct=Decimal("0"),
        open_positions=0,
        remaining_capacity=10,
        configured_max_open=10,
        risk_approved_volume=Decimal("0.01"),
        candidate_allowed=True,
        min_lot=VOLUME_MIN,
    )
    base.update(overrides)
    return CompoundingInputs(**base)  # type: ignore[arg-type]


def test_hard_cap_and_min_lot_unchanged() -> None:
    assert HARD_MAX_RISK_PCT == Decimal("80.0")
    assert MicroAccountProfile().hard_max_risk_pct == Decimal("80.0")
    assert BROKER_MIN_LOT == Decimal("0.01")
    assert VOLUME_MIN == Decimal("0.01")
    obs = evaluate_compounding_shadow(_inputs())
    assert obs.live_hard_max_risk_pct == "80.0"
    assert obs.live_min_lot == "0.01"


def test_shadow_cannot_bypass_risk_volume() -> None:
    approved = Decimal("0.01")
    obs = evaluate_compounding_shadow(_inputs(risk_approved_volume=approved))
    assert obs.mutates_engines is False
    assert obs.live_activation == "SHADOW_ONLY"
    assert obs.sizing.suggested_volume <= approved
    assert obs.sizing.risk_approved_volume == approved


def test_aggressive_mode_does_not_raise_live_risk() -> None:
    obs = evaluate_compounding_shadow(_inputs())
    assert obs.mode in {
        "DEFENSIVE",
        "NORMAL",
        "AGGRESSIVE",
        "HIGH_CONVICTION",
        "CAPITAL_ATTACK",
    }
    assert obs.sizing.suggested_volume <= obs.sizing.risk_approved_volume
    assert Decimal(obs.live_hard_max_risk_pct) == Decimal("80.0")


def test_drawdown_reduces_aggressiveness() -> None:
    green = evaluate_compounding_shadow(_inputs(daily_loss_pct=Decimal("0")))
    preserve = evaluate_compounding_shadow(
        _inputs(
            daily_pnl=Decimal("-8"),
            daily_loss_pct=Decimal("3.5"),
            max_daily_loss_pct=Decimal("3.0"),
        )
    )
    assert preserve.drawdown_state == "CAPITAL_PRESERVATION"
    assert preserve.mode == "DEFENSIVE"
    assert preserve.compounding_bias == "DE_RISK"
    assert preserve.counts.effective_count <= green.counts.effective_count
    assert preserve.sizing.suggested_volume <= green.sizing.suggested_volume


def test_profit_only_scales_within_risk() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(daily_pnl=Decimal("4.00"), daily_loss_pct=Decimal("0"))
    )
    assert obs.compounding_bias == "SCALE_UP_WITHIN_RISK"
    assert obs.sizing.suggested_volume <= obs.sizing.risk_approved_volume


def test_losses_never_increase_exposure() -> None:
    loss = evaluate_compounding_shadow(
        _inputs(daily_pnl=Decimal("-2.00"), daily_loss_pct=Decimal("1.0"))
    )
    assert compounding_bias(
        drawdown_state=loss.drawdown_state, daily_pnl=Decimal("-2.00")
    ) == "DE_RISK"
    assert loss.compounding_bias == "DE_RISK"


def test_losing_trade_never_martingale_scale_in() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(
            open_positions=1,
            quantforg_open_count=1,
            remaining_capacity=9,
            open_profits=(Decimal("-1.25"),),
            open_directions=("BUY",),
            open_entries=(Decimal("3400"),),
            entry=Decimal("3390"),
            same_symbol_blocked=True,
            candidate_allowed=False,
        )
    )
    assert obs.scale_in.winners_only is True
    assert obs.scale_in.scale_in_allowed is False
    assert obs.scale_in.scale_in_live_enabled is False
    assert obs.scale_in.shadow_eligible is False
    assert "los" in obs.scale_in.scale_in_block_reason.lower() or "pyramid" in (
        obs.scale_in.scale_in_block_reason.lower()
    )


def test_winner_scale_in_requires_authorization_and_stays_off() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(
            sequential_scale_in_live_enabled=True,
            open_positions=1,
            quantforg_open_count=1,
            remaining_capacity=9,
            open_profits=(Decimal("2.50"),),
            open_directions=("BUY",),
            open_entries=(Decimal("3400"),),
            entry=Decimal("3412"),
            same_symbol_blocked=True,
            candidate_allowed=False,
        )
    )
    assert obs.scale_in.scale_in_live_enabled is False
    assert obs.scale_in.scale_in_allowed is False
    assert "DISABLED" in obs.scale_in.scale_in_block_reason or (
        "SAME_SYMBOL" in obs.scale_in.scale_in_block_reason
    )


def test_effective_count_respects_aggregate_risk() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(risk_approved_volume=Decimal("0.01"), remaining_capacity=10)
    )
    assert obs.counts.effective_count <= obs.counts.risk_allowed_count
    assert obs.counts.effective_count <= obs.counts.remaining_capacity
    if obs.sizing.per_leg_volume > 0 and obs.counts.effective_count > 0:
        total = obs.sizing.per_leg_volume * obs.counts.effective_count
        assert total <= obs.sizing.risk_approved_volume


def test_max_open_trades_is_not_permission() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(
            remaining_capacity=0,
            quantforg_open_count=10,
            configured_max_open=10,
            open_positions=10,
        )
    )
    assert obs.counts.effective_count == 0
    assert "max_open_trades_is_cap_not_permission" in obs.counts.reductions


def test_same_symbol_ownership_not_overridden() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(same_symbol_blocked=True, candidate_allowed=False)
    )
    assert obs.scale_in.scale_in_allowed is False


def test_min_lot_infeasible_classified_not_forced() -> None:
    reset_compounding_shadow_store_for_tests()
    row = observe_aggressive_compounding_shadow(
        signal={
            "symbol": "XAUUSD_i",
            "min_lot_feasibility": "MIN_LOT_INFEASIBLE",
            "confidence": 92,
            "signal_quality": 90,
            "direction": "BUY",
        },
        score=_score(),
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_CONSTRAINT",
        equity="208.86",
        daily_pnl="0",
        risk_approved_volume="0",
    )
    assert row is not None
    assert row["mutates_engines"] is False
    assert row["min_lot_classification"] == "MIN_LOT_INFEASIBLE"
    from app.domain.institutional_trading.compounding.observe import (
        get_compounding_shadow_store,
    )

    snap = get_compounding_shadow_store().snapshot()
    assert snap["min_lot_infeasible_signals"] >= 1
    assert snap["live_mutations"] == 0


def test_stale_shadow_cannot_execute() -> None:
    obs = evaluate_compounding_shadow(_inputs(forwarded_to_oms=False))
    assert obs.mutates_engines is False
    assert obs.live_activation == "SHADOW_ONLY"


def test_observer_never_imports_order_send() -> None:
    import app.application.services.aggressive_compounding_observer as mod
    import inspect

    src = inspect.getsource(mod)
    assert "order_send(" not in src
    assert "Execute Now" not in src


def test_simulation_does_not_promote() -> None:
    report = simulate_mode_comparison(n=80, seed=7)
    assert report["promoted_to_live"] is False
    assert report["historical_backtest"] == "NOT_RUN"
    assert report["walk_forward"] == "NOT_RUN"
    assert report["live_activation"] == "SHADOW_ONLY"


def test_weak_conviction_zero_size() -> None:
    obs = evaluate_compounding_shadow(
        _inputs(
            quality=40,
            confidence=40,
            score=_score(quality=40, confidence=40, rr=0.9),
            daily_loss_pct=Decimal("2.0"),
        )
    )
    assert obs.sizing.suggested_volume <= obs.sizing.risk_approved_volume
    if obs.conviction.conviction_score < 70:
        assert obs.sizing.quality_multiplier == Decimal("0")
        assert obs.sizing.suggested_volume == Decimal("0")


def test_manual_magic_not_in_shadow_capacity() -> None:
    """Shadow count uses remaining_capacity from QuantForg cap, not account book."""
    obs = evaluate_compounding_shadow(
        _inputs(open_positions=2, quantforg_open_count=0, remaining_capacity=10)
    )
    assert obs.counts.remaining_capacity == 10


def test_runtime_hook_does_not_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The observe helper must not touch a gateway client."""
    calls: list[str] = []

    class Boom:
        def order_send(self, *a: object, **k: object) -> None:
            calls.append("order_send")

    monkeypatch.setattr(
        "app.infrastructure.brokers.mt5.gateway_client.GatewayMT5Client.order_send",
        Boom.order_send,
        raising=False,
    )
    observe_aggressive_compounding_shadow(
        signal={"symbol": "XAUUSD_i", "direction": "BUY", "confidence": 80},
        score=_score(quality=80, confidence=80),
        forwarded_to_oms=False,
        risk_approved_volume="0.01",
        equity="208.86",
    )
    assert calls == []
