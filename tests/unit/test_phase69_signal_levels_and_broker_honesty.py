"""Phase 69 — signal Price/Entry/SL/TP propagation + broker honesty."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import signal_center_service
from app.application.services.research_universe_scanner import evaluate_injected_contexts
from app.domain.market_universe.opportunity_board import project_opportunity_row
from app.domain.market_universe.research_signals import build_research_signals

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_row_preserves_price_entry_sl_tp() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "USDJPY",
            "broker_symbol": "USDJPY",
            "canonical_symbol": "USDJPY",
            "direction": "BUY",
            "opportunity_score": 75,
            "directional_edge": 32,
            "entry": "149.250",
            "stop_loss": "148.900",
            "take_profit": "149.900",
            "bid": 149.24,
            "ask": 149.26,
            "mid": 149.25,
            "price": 149.25,
            "asset_class": "FOREX",
            "session": "NEW YORK",
            "research_rank_score": 108.2,
            "features_as_of": "2026-08-30T12:00:00+00:00",
        }
    )
    assert row["symbol"] == "USDJPY"
    assert row["price"] == pytest.approx(149.25)
    assert row["entry"] == pytest.approx(149.25)
    assert row["stop_loss"] == pytest.approx(148.9)
    assert row["take_profit"] == pytest.approx(149.9)
    assert row["authorizes_trade"] is False
    assert row["pipeline"]["forwarded_to_oms"] is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_missing_levels_remain_honest_none() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "direction": "SELL",
            "opportunity_score": 70,
            "directional_edge": 10,
            "entry": None,
            "stop_loss": "UNKNOWN",
            "take_profit": "",
            "price": None,
        }
    )
    assert row["entry"] is None
    assert row["stop_loss"] is None
    assert row["take_profit"] is None
    assert row["price"] is None


@pytest.mark.unit
@pytest.mark.trading_core
def test_price_from_bid_ask_mid_only() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "XAUUSD",
            "direction": "SELL",
            "opportunity_score": 71,
            "directional_edge": 12,
            "bid": 2400.1,
            "ask": 2400.5,
        }
    )
    assert row["price"] == pytest.approx(2400.3)
    assert row["entry"] is None


@pytest.mark.unit
@pytest.mark.trading_core
def test_symbol_identity_not_overwritten_by_xauusd() -> None:
    eurusd = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 80,
            "directional_edge": 10,
            "price": 1.085,
            "entry": 1.085,
            "stop_loss": 1.08,
            "take_profit": 1.09,
        }
    )
    xau = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "XAUUSD",
            "broker_symbol": "XAUUSD",
            "direction": "SELL",
            "opportunity_score": 80,
            "directional_edge": 10,
            "price": 2401.0,
            "entry": 2401.0,
            "stop_loss": 2410.0,
            "take_profit": 2380.0,
        }
    )
    assert eurusd["symbol"] == "EURUSD"
    assert eurusd["price"] == pytest.approx(1.085)
    assert xau["symbol"] == "XAUUSD"
    assert xau["price"] == pytest.approx(2401.0)
    assert eurusd["price"] != xau["price"]


@pytest.mark.unit
@pytest.mark.trading_core
def test_opportunity_board_projects_quote_and_levels() -> None:
    projected = project_opportunity_row(
        {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "opportunity_score": 72,
            "directional_edge": 14,
            "entry": 1.275,
            "stop_loss": 1.28,
            "take_profit": 1.265,
        },
        registry_item={"asset_class": "FOREX", "bid": 1.2748, "ask": 1.2752},
    )
    assert projected["symbol"] == "GBPUSD"
    assert projected["price"] == pytest.approx(1.275)
    assert projected["entry"] == 1.275
    assert projected["stop_loss"] == 1.28
    assert projected["take_profit"] == 1.265
    assert projected["authorizes_trade"] is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_evaluate_injected_preserves_structure_targets() -> None:
    out = evaluate_injected_contexts(
        [
            {
                "symbol": "AUDUSD",
                "direction": "SELL",
                "opportunity_score": 73,
                "directional_edge": 11,
                "entry": "0.6520",
                "stop_loss": "0.6550",
                "take_profit": "0.6480",
                "bid": 0.6519,
                "ask": 0.6521,
                "mid": 0.652,
            }
        ]
    )
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["ALLOW_LIVE_PROMOTION"] is False
    row = out["rows"][0]
    assert row["entry"] == "0.6520"
    assert row["stop_loss"] == "0.6550"
    assert row["take_profit"] == "0.6480"
    assert row["price"] == 0.652


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_signals_emit_price_and_levels() -> None:
    payload = build_research_signals(
        [
            {
                "broker_symbol": "BTCUSD",
                "symbol": "BTCUSD",
                "canonical_symbol": "BTCUSD",
                "direction": "BUY",
                "opportunity_score": 74,
                "directional_edge": 15,
                "entry": 64000,
                "stop_loss": 63000,
                "take_profit": 66000,
                "bid": 63990,
                "ask": 64010,
                "mid": 64000,
                "asset_class": "CRYPTO",
                "features_as_of": "2026-08-30T12:00:00+00:00",
            }
        ]
    )
    sig = payload["signals"][0]
    assert sig["kind"] == "RESEARCH_SIGNAL"
    assert sig["not"] == "LIVE_ORDER"
    assert sig["live_eligible"] is False
    assert sig["price"] == 64000
    assert sig["entry_candidate"] == 64000
    assert sig["SL_candidate"] == 63000
    assert sig["TP_candidate"] == 66000


@pytest.mark.unit
@pytest.mark.trading_core
def test_merge_research_enriches_price_levels_without_oms() -> None:
    merged, meta = signal_center_service._merge_research_into_signals(
        [
            {
                "symbol": "ETHUSD",
                "direction": "BUY",
                "opportunity_score": None,
                "entry": None,
                "price": None,
                "authorizes_trade": False,
            }
        ],
        research_snap={
            "catalogue_source": "LIVE_BROKER",
            "opportunity_board": {
                "live_ranked": [
                    {
                        "symbol": "ETHUSD",
                        "broker_symbol": "ETHUSD",
                        "direction": "BUY",
                        "opportunity_score": 76,
                        "directional_edge": 18,
                        "entry": 3200.5,
                        "stop_loss": 3150.0,
                        "take_profit": 3300.0,
                        "price": 3200.5,
                        "bid": 3200.0,
                        "ask": 3201.0,
                        "research_rank_score": 90,
                    }
                ]
            },
        },
    )
    assert meta["scanner_status"] == "ACTIVE"
    row = next(r for r in merged if r["symbol"] == "ETHUSD")
    assert row["price"] == pytest.approx(3200.5)
    assert row["entry"] == pytest.approx(3200.5)
    assert row["stop_loss"] == pytest.approx(3150.0)
    assert row["take_profit"] == pytest.approx(3300.0)
    assert row["authorizes_trade"] is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_password_not_hardcoded_in_repo() -> None:
    """Phase 69 — never commit admin credentials."""
    script = ROOT / "scripts" / "provision_admin_user.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "ADMIN_EMAIL" in text
    assert "ADMIN_PASSWORD" in text
    assert "infojimvio@gmail.com" not in text
    assert 'password = "' not in text.lower()
    # Spot-check frontend/backend for accidental env default embedding.
    for rel in (
        "frontend/src/lib/auth/ite-ops-access.ts",
        "frontend/src/app/(app)/admin/layout.tsx",
        "app/presentation/dependencies/auth.py",
    ):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert "ADMIN_PASSWORD" not in body
        assert "infojimvio@gmail.com" not in body


@pytest.mark.unit
@pytest.mark.trading_core
def test_require_roles_admin_gate_exists() -> None:
    from app.domain.enums.user import UserRole
    from app.presentation.dependencies.auth import require_roles

    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    assert callable(dep)
