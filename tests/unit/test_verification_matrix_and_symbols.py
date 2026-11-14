"""Verification matrix honesty + broker symbol fail-closed rules."""

from __future__ import annotations

from pathlib import Path

from app.domain.broker_connectivity.broker_symbol_validation import (
    validate_broker_symbol,
)
from app.domain.broker_connectivity.broker_verification_evidence import (
    record_verification_success,
)
from app.domain.broker_connectivity.verification_matrix import (
    TARGET_BROKERS,
    build_verification_matrix,
)


def test_matrix_targets_seven_non_weltrade_brokers(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    monkeypatch.setenv("QF_BROKER_VERIFICATION_EVIDENCE_PATH", str(path))
    matrix = build_verification_matrix()
    ordered = [r["broker"] for r in matrix["brokers"]]
    assert ordered == list(TARGET_BROKERS)
    assert "justmarkets" in ordered
    assert "weltrade" not in ordered
    for row in matrix["brokers"]:
        # Owner-authorized LIVE brokers are connectable in Production catalogue.
        assert row["connectable"] is True
        assert row["display_label"] == "Verified"
        # Session PASS still requires authenticated evidence rows.
        assert row["demo"]["status"] == "BLOCKED"
        assert row["live"]["status"] == "BLOCKED"


def test_matrix_pass_after_evidence(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "ev.json"
    monkeypatch.setenv("QF_BROKER_VERIFICATION_EVIDENCE_PATH", str(path))
    record_verification_success(
        broker_slug="xm",
        server="XMGlobal-MT5",
        environment="demo",
        login=55,
        trade_allowed=True,
        market_data_ok=True,
        balance=100.0,
        path=path,
    )
    matrix = build_verification_matrix()
    xm = next(r for r in matrix["brokers"] if r["broker"] == "xm")
    assert xm["connectable"] is True
    assert xm["demo"]["status"] == "PASS"
    assert xm["demo"]["server"] == "XMGlobal-MT5"
    assert xm["live"]["status"] == "BLOCKED"


def test_symbol_validation_fail_closed_without_session() -> None:
    result = validate_broker_symbol(
        broker_slug="exness", symbol="XAUUSD", session_symbols=None
    )
    assert result.ok is False
    assert result.reason == "broker_session_symbols_unavailable"


def test_symbol_validation_weltrade_delegated() -> None:
    result = validate_broker_symbol(broker_slug="weltrade", symbol="XAUUSD")
    assert result.ok is True


def test_symbol_validation_volume_step() -> None:
    result = validate_broker_symbol(
        broker_slug="ic-markets",
        symbol="EURUSD",
        volume=0.03,
        session_symbols=[
            {"name": "EURUSD", "volume_min": 0.01, "volume_step": 0.01, "digits": 5}
        ],
    )
    assert result.ok is True
    bad = validate_broker_symbol(
        broker_slug="ic-markets",
        symbol="EURUSD",
        volume=0.015,
        session_symbols=[
            {"name": "EURUSD", "volume_min": 0.01, "volume_step": 0.01, "digits": 5}
        ],
    )
    assert bad.ok is False
