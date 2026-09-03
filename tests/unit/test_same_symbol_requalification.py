"""Same-symbol close must not re-enter an unchanged setup."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.ai_scalping.same_symbol_requalification import (
    MATERIAL_SCORE_DELTA,
    SetupFingerprint,
    fresh_setup_evidence,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    SymbolStateBook,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _fp(**kwargs: object) -> SetupFingerprint:
    base = {
        "direction": "SELL",
        "setup_family": "bos_continuation",
        "opportunity_score": 73,
        "structure_sig": "bos=M15:4418.6:2026-09-03T01:00:00+00:00",
        "regime": "weak_trend",
    }
    base.update(kwargs)
    return SetupFingerprint(**base)  # type: ignore[arg-type]


def test_same_sell_structure_is_not_fresh() -> None:
    ok, why = fresh_setup_evidence(_fp(), _fp())
    assert ok is False
    assert why == "same_setup_as_closed_trade"


def test_new_bos_is_fresh() -> None:
    nxt = _fp(structure_sig="bos=M15:4425.1:2026-09-03T02:00:00+00:00")
    ok, why = fresh_setup_evidence(_fp(), nxt)
    assert ok is True
    assert "structure_changed" in why


def test_direction_change_is_fresh() -> None:
    ok, why = fresh_setup_evidence(_fp(), _fp(direction="BUY"))
    assert ok is True
    assert "direction_changed" in why


def test_material_score_change_is_fresh() -> None:
    nxt = _fp(opportunity_score=73 + MATERIAL_SCORE_DELTA)
    ok, why = fresh_setup_evidence(_fp(), nxt)
    assert ok is True
    assert "opportunity_score_material_change" in why


def test_one_point_score_drift_is_not_fresh() -> None:
    ok, _why = fresh_setup_evidence(_fp(), _fp(opportunity_score=74))
    assert ok is False


def test_unknown_current_fail_closed() -> None:
    empty = SetupFingerprint(
        direction=None,
        setup_family=None,
        opportunity_score=None,
        structure_sig=None,
        regime=None,
    )
    ok, why = fresh_setup_evidence(_fp(), empty)
    assert ok is False
    assert why == "current_setup_unknown"


def test_book_blocks_until_structure_changes() -> None:
    book = SymbolStateBook()
    closed = _fp()
    book.observe_setup("XAUUSD", closed)
    book.note_closed("XAUUSD", pnl=-7.85, fingerprint=closed)
    ok, why = book.evaluate_requalification("XAUUSD", closed)
    assert ok is False
    assert why == "same_setup_as_closed_trade"
    ok2, why2 = book.evaluate_requalification(
        "XAUUSD", _fp(setup_family="choch_reversal")
    )
    assert ok2 is True
    assert "setup_family_changed" in why2
    # Last closed fingerprint stays until the next close — stale SELL/BOS
    # still blocked.
    ok3, why3 = book.evaluate_requalification("XAUUSD", closed)
    assert ok3 is False
    assert why3 == "same_setup_as_closed_trade"


def test_other_symbol_not_blocked() -> None:
    book = SymbolStateBook()
    book.note_closed("XAUUSD", pnl=-7.85, fingerprint=_fp())
    ok, why = book.evaluate_requalification("EURUSD", _fp())
    assert ok is True
    assert why == "requalify_not_required"


def test_close_does_not_reset_cooldown_gate() -> None:
    book = SymbolStateBook()
    book.note_entry("XAUUSD", seconds=90)
    book.note_closed("XAUUSD", pnl=-1.0, fingerprint=_fp())
    state = book.get("XAUUSD")
    assert state._cooldown._last_entry_mono is not None
    assert state.require_requalify is True


def test_ite_close_path_does_not_wipe_desk_or_global_cooldown() -> None:
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "application"
        / "services"
        / "institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "clear_for_post_close_rescan" not in src
    assert ".reset(closed_sym)" not in src
    assert "note_closed(" in src
    assert "fingerprint_from_snapshot" in src


def test_scoring_applies_same_symbol_requalify_wait() -> None:
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "institutional_trading"
        / "ai_scalping"
        / "scoring.py"
    ).read_text(encoding="utf-8")
    assert "evaluate_requalification" in src
    assert "REQUALIFY_REJECT" in src
    assert "observe_setup" in src
