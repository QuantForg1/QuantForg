"""Micro-safe USD major alignment — catalogue resolve + priority, no risk weaken."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_SCALPING_UNIVERSE,
    MICRO_SAFE_USD_MAJOR_DESKS,
)
from app.domain.institutional_trading.ai_scalping.session_symbol_priority import (
    prioritize_universe_for_session,
    session_priority_score,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    build_dynamic_scalping_universe,
    discover_from_broker_rows,
    resolve_seed_to_broker_symbol,
)
from app.domain.institutional_trading.atr import stop_distance_from_atr
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile


_WELTRADE_ROWS = [
    {"code": "EURUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "GBPUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "AUDUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "NZDUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "USDCHF_I", "trade_mode": 4, "digits": 5},
    {"code": "USDCAD_I", "trade_mode": 4, "digits": 5},
    {"code": "USDJPY_I", "trade_mode": 4, "digits": 3},
    {"code": "XAUUSD_I", "trade_mode": 4, "digits": 3},
    {"code": "CADCHF_I", "trade_mode": 4, "digits": 5},
    {"code": "BTCUSD", "trade_mode": 4, "digits": 2},
    {"code": "ETHUSD", "trade_mode": 4, "digits": 2},
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("desk", "broker"),
    [
        ("EURUSD", "EURUSD_I"),
        ("GBPUSD", "GBPUSD_I"),
        ("AUDUSD", "AUDUSD_I"),
        ("NZDUSD", "NZDUSD_I"),
        ("USDCHF", "USDCHF_I"),
        ("USDCAD", "USDCAD_I"),
    ],
)
def test_micro_safe_desk_resolves_to_weltrade_i(desk: str, broker: str) -> None:
    discovered = discover_from_broker_rows(_WELTRADE_ROWS)
    assert resolve_seed_to_broker_symbol(desk, discovered=discovered) == broker


@pytest.mark.unit
def test_default_universe_seeds_micro_safe_majors_first() -> None:
    assert DEFAULT_SCALPING_UNIVERSE[:6] == MICRO_SAFE_USD_MAJOR_DESKS
    assert "XAUUSD" in DEFAULT_SCALPING_UNIVERSE
    assert "USDJPY" in DEFAULT_SCALPING_UNIVERSE


@pytest.mark.unit
def test_dynamic_universe_includes_resolved_micro_safe_majors() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_ROWS)
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    for desk, broker in zip(
        MICRO_SAFE_USD_MAJOR_DESKS,
        (
            "EURUSD_I",
            "GBPUSD_I",
            "AUDUSD_I",
            "NZDUSD_I",
            "USDCHF_I",
            "USDCAD_I",
        ),
        strict=True,
    ):
        assert broker in universe
        assert desk not in universe  # bare desk remapped when catalogue has _I
    # Crosses still discoverable for analysis — not removed globally.
    assert "CADCHF_I" in universe
    assert "XAUUSD_I" in universe


@pytest.mark.unit
def test_london_session_prioritizes_micro_safe_over_gold_and_crosses() -> None:
    assert session_priority_score("EURUSD", "london") > session_priority_score(
        "XAUUSD", "london"
    )
    assert session_priority_score("AUDUSD", "london") > session_priority_score(
        "EURJPY", "london"
    )
    assert session_priority_score("USDCAD_I", "london") > session_priority_score(
        "CADCHF_I", "london"
    )
    ordered = prioritize_universe_for_session(
        ("XAUUSD_I", "CADCHF_I", "EURUSD_I", "AUDUSD_I", "USDJPY_I"),
        "london",
    )
    assert ordered[0] == "EURUSD_I"
    assert ordered.index("AUDUSD_I") < ordered.index("XAUUSD_I")
    assert ordered.index("AUDUSD_I") < ordered.index("CADCHF_I")


@pytest.mark.unit
def test_xauusd_i_still_min_lot_constrained_on_micro_equity() -> None:
    """Alignment must not weaken gold MIN_LOT_CONSTRAINT on ~$100."""
    equity = Decimal("100.72")
    price = Decimal("4380.013")
    atr = (price * Decimal("0.0015")).quantize(Decimal("0.001"))
    dist = stop_distance_from_atr(atr)
    engine = RiskEngine()
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="align-xau-1",
            symbol="XAUUSD_I",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=dist,
            atr=atr,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=price,
        ),
        account=AccountSnapshot(
            login=1,
            balance=equity,
            equity=equity,
            margin=Decimal("0"),
            free_margin=equity,
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=2000,
        ),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    assert "MIN_LOT_EXCEEDS_RISK_BUDGET" in " ".join(result.reasons)
    profile = MicroAccountProfile()
    min_loss = (Decimal("0.01") * Decimal("100") * dist).quantize(Decimal("0.01"))
    needed = (min_loss / equity * Decimal("100")).quantize(Decimal("0.01"))
    assert needed > profile.hard_max_risk_pct


@pytest.mark.unit
def test_usdjpy_i_existing_cs_stop_sizing_still_rejects_micro_equity() -> None:
    """Do not alter JPY sizing semantics — cs×stop path still rejects ~$100."""
    equity = Decimal("100.72")
    # Live-like USDJPY stop (ATR×1.5 ≈ 0.10); existing engine uses cs×stop.
    stop = Decimal("0.1020")
    cs = Decimal("100000")
    risk_pct = DEFAULT_ITE_CONFIG.risk_per_trade_pct
    risk_budget = (equity * risk_pct / Decimal("100")).quantize(Decimal("0.01"))
    raw = risk_budget / (cs * stop)
    assert raw < Decimal("0.01")
    min_loss = (Decimal("0.01") * cs * stop).quantize(Decimal("0.01"))
    needed = (min_loss / equity * Decimal("100")).quantize(Decimal("0.01"))
    profile = MicroAccountProfile()
    assert needed > profile.hard_max_risk_pct
    engine = RiskEngine()
    size = engine.size_position(
        equity=equity,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=stop,
        atr=None,
        entry_price=Decimal("159.174"),
        contract_size=cs,
        risk_per_trade_pct=risk_pct,
    )
    assert size.approved_lots == Decimal("0")
    assert size.capped is True


@pytest.mark.unit
def test_alignment_does_not_change_risk_ceilings() -> None:
    profile = MicroAccountProfile()
    assert profile.hard_max_risk_pct == Decimal("5.0")
    assert DEFAULT_ITE_CONFIG.risk_per_trade_pct == Decimal("1.0")
    # Seed list still contains gold — analysis retained, not force-executable.
    assert "XAUUSD" in DEFAULT_SCALPING_UNIVERSE
