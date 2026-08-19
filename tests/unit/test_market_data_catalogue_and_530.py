"""Market-data catalogue routing + 530/503 diagnostics — not live OMS."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.ite_cycle_market_context import (
    build_ite_cycle_market_context,
)
from app.domain.entities.mt5_market import MT5Rate
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    catalogue_ordered_candidates,
    resolve_canonical_market_data_symbol,
)
from app.domain.institutional_trading.operations.execution_halt_policy import (
    HaltClass,
    classify_halt_condition,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    classify_candidate_outcome,
)
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.gateway_client import classify_gateway_failure

REPO = Path(__file__).resolve().parents[2]
WELTRADE_ROWS = (
    {"code": "AUDUSD_i", "trade_mode": 4},
    {"code": "AUDJPY_i", "trade_mode": 4},
    {"code": "EURUSD_i", "trade_mode": 4},
    {"code": "XAUUSD_i", "trade_mode": 4},
    {"code": "NZDUSD_i", "trade_mode": 4},
    {"code": "GBPUSD_i", "trade_mode": 4},
)


def _rate(symbol: str, tf: Timeframe, i: int) -> MT5Rate:
    base = Decimal("1.0000") + Decimal(i) / Decimal("10000")
    return MT5Rate(
        symbol=symbol,
        timeframe=tf,
        open_time=datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
        open=base,
        high=base + Decimal("0.0002"),
        low=base - Decimal("0.0002"),
        close=base + Decimal("0.0001"),
        tick_volume=10,
        real_volume=Decimal("1"),
    )


def _stub_fetch(monkeypatch: pytest.MonkeyPatch, rows: tuple[dict, ...]) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.universe_discovery."
        "fetch_broker_symbol_rows",
        lambda *_a, **_k: rows,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("desk", "broker"),
    [
        ("AUDUSD", "AUDUSD_I"),
        ("AUDJPY", "AUDJPY_I"),
        ("EURUSD", "EURUSD_I"),
        ("XAUUSD", "XAUUSD_I"),
    ],
)
def test_desk_maps_to_catalogue_i_only(desk: str, broker: str) -> None:
    resolved = resolve_canonical_market_data_symbol(
        desk, broker_symbol_rows=WELTRADE_ROWS
    )
    ordered = catalogue_ordered_candidates(desk, broker_symbol_rows=WELTRADE_ROWS)
    assert resolved == broker
    assert ordered == (broker,)
    assert desk not in ordered


@pytest.mark.unit
def test_canonical_has_no_unsuffixed_fallback() -> None:
    ordered = catalogue_ordered_candidates("AUDUSD", broker_symbol_rows=WELTRADE_ROWS)
    assert "AUDUSD" not in ordered
    assert ordered == ("AUDUSD_I",)


@pytest.mark.unit
def test_missing_catalogue_does_not_invent_suffix() -> None:
    assert resolve_canonical_market_data_symbol("AUDUSD", broker_symbol_rows=()) == ""
    assert catalogue_ordered_candidates("AUDUSD", broker_symbol_rows=()) == ()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unresolved_catalogue_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_fetch(monkeypatch, ())
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    ctx = await build_ite_cycle_market_context(adapter, symbol="AUDUSD")
    assert ctx.ok is False
    assert "SYMBOL_CATALOGUE_RESOLUTION_FAILED" in ctx.reason
    assert ctx.diagnostics.get("logical_symbol") == "AUDUSD"
    assert ctx.diagnostics.get("canonical_broker_symbol") is None
    assert ctx.diagnostics.get("next_action") == "FAIL_CLOSED"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_market_context_uses_canonical_and_keeps_logical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    _stub_fetch(monkeypatch, WELTRADE_ROWS)
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.client.symbol_info = MagicMock(return_value=None)

    def _bars(symbol: str, tf: Timeframe, start: int, count: int) -> list[MT5Rate]:
        seen.append(str(symbol))
        return [_rate(str(symbol), tf, i) for i in range(count)]

    adapter.copy_rates_from_pos.side_effect = _bars
    adapter.latest_tick.return_value = SimpleNamespace(
        bid=Decimal("0.65"),
        ask=Decimal("0.6502"),
        mid=Decimal("0.6501"),
        volume=Decimal("1"),
        timestamp=datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
    )
    adapter.account_info.return_value = SimpleNamespace(
        login=1,
        name="t",
        server="s",
        equity=Decimal("100"),
        balance=Decimal("100"),
        free_margin=Decimal("100"),
        margin=Decimal("0"),
        leverage=100,
        trade_mode="real",
    )
    adapter.list_positions.return_value = []
    adapter.history_deals = None

    async def _fake_analyze(*_a: object, **_k: object) -> SimpleNamespace:
        return SimpleNamespace(
            symbol="AUDUSD_I",
            atr=Decimal("0.001"),
            spread=Decimal("0.0002"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="sydney"), allowed=True
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
            mt5_positions=0, internal_positions=0, repaired=False, tickets=[]
        ),
    )
    ctx = await build_ite_cycle_market_context(adapter, symbol="AUDUSD")
    assert seen
    assert all(sym.upper() == "AUDUSD_I" for sym in seen)
    assert all(s.upper() != "AUDUSD" for s in seen)
    assert ctx.diagnostics.get("logical_symbol") == "AUDUSD"
    assert str(ctx.diagnostics.get("canonical_broker_symbol")).upper() == "AUDUSD_I"
    tick_symbols = [str(c.args[0]) for c in adapter.latest_tick.call_args_list]
    assert tick_symbols
    assert all(s.upper() == "AUDUSD_I" for s in tick_symbols)
    info_symbols = [
        str(c.args[0]) for c in adapter.client.symbol_info.call_args_list
    ]
    if info_symbols:
        assert all(s.upper() == "AUDUSD_I" for s in info_symbols)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_530_keeps_status_and_hard_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_fetch(monkeypatch, ({"code": "AUDUSD_i", "trade_mode": 4},))
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.copy_rates_from_pos.side_effect = RuntimeError(
        "CLOUDFLARE_ORIGIN_UNREACHABLE: Gateway /candles/AUDUSD_I "
        "failed upstream HTTP 530 at https://gateway.quantforg.com/candles/AUDUSD_I: "
        "The host is configured as a Cloudflare Tunnel, but Cloudflare is currently "
        "unable to reach it."
    )
    ctx = await build_ite_cycle_market_context(adapter, symbol="AUDUSD")
    assert ctx.ok is False
    assert ctx.diagnostics.get("http_status") == 530
    assert ctx.diagnostics.get("failure_class") == "MARKET_DATA_ORIGIN_UNREACHABLE"
    assert ctx.diagnostics.get("logical_symbol") == "AUDUSD"
    assert str(ctx.diagnostics.get("canonical_broker_symbol")).upper() == "AUDUSD_I"
    assert ctx.diagnostics.get("endpoint") == "/candles/AUDUSD_I"
    assert ctx.diagnostics.get("gateway_host") == "https://gateway.quantforg.com"
    assert ctx.diagnostics.get("next_action") == "FAIL_CLOSED"
    assert "530" in ctx.reason
    assert "CLOUDFLARE_ORIGIN_UNREACHABLE" in ctx.reason
    assert "HTTP 503" not in ctx.reason
    out = classify_candidate_outcome(
        abort_reason="NO_MARKET_CONTEXT",
        failed_reasons=(ctx.reason,),
        cycle_outcome="no_snapshot",
    )
    assert out["fault_class"] == FaultClass.HARD_BLOCK.value
    assert out["next_action"] == CandidateAction.FAIL_CLOSED.value
    assert out["decision_state"] != DecisionState.DEGRADED.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_symbol_specific_503_is_not_relabeled_530(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_fetch(monkeypatch, ({"code": "AUDUSD_i", "trade_mode": 4},))
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.copy_rates_from_pos.side_effect = RuntimeError(
        "GATEWAY_MARKET_DATA_UNAVAILABLE: Gateway /candles/AUDUSD "
        "failed upstream HTTP 503 at https://gateway.quantforg.com/candles/AUDUSD: "
        "symbol unavailable: AUDUSD"
    )
    ctx = await build_ite_cycle_market_context(adapter, symbol="AUDUSD")
    assert ctx.ok is False
    assert ctx.diagnostics.get("http_status") == 503
    assert ctx.diagnostics.get("failure_class") == "GATEWAY_MARKET_DATA_UNAVAILABLE"
    assert ctx.diagnostics.get("failure_class") != "MARKET_DATA_ORIGIN_UNREACHABLE"
    assert "530" not in ctx.reason
    assert "503" in ctx.reason


@pytest.mark.unit
def test_503_is_not_relabeled_530() -> None:
    label = classify_gateway_failure(
        status_code=503,
        cloudflare=True,
        error="symbol unavailable: AUDUSD",
        body_preview="symbol unavailable: AUDUSD",
    )
    assert label == "GATEWAY_MARKET_DATA_UNAVAILABLE"
    assert "530" not in label
    assert label != "CLOUDFLARE_ORIGIN_UNREACHABLE"
    halt = classify_halt_condition("NO_MARKET_CONTEXT market data load failed")
    assert halt is HaltClass.HARD_BLOCK


@pytest.mark.unit
def test_execution_and_order_send_paths_unchanged() -> None:
    engine = (
        REPO / "app/application/services/institutional_execution_engine.py"
    ).read_text(encoding="utf-8")
    gateway = (REPO / "app/application/services/execution_gateway.py").read_text(
        encoding="utf-8"
    )
    client = (REPO / "app/infrastructure/brokers/mt5/gateway_client.py").read_text(
        encoding="utf-8"
    )
    assert "self.gateway.submit" in engine
    assert "Never retry order_send" in client
    assert "order_calc_margin" not in gateway
    assert "cloudflared" not in engine.lower()
    assert "Restart-Service" not in client
    assert "duplicate cloudflared" not in client.lower()
    for rel in (
        "app/application/services/institutional_execution_engine.py",
        "app/application/services/execution_gateway.py",
        "app/domain/institutional_trading/operations/fast_decision_path.py",
    ):
        src = (REPO / rel).read_text(encoding="utf-8")
        assert "Restart-Service" not in src
        assert "cloudflared.exe" not in src.lower()
