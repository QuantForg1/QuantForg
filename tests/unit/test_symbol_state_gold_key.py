"""Gold desk identity collapses XAUUSD / XAUUSD_i in SymbolStateBook."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.ai_scalping.symbol_state import SymbolStateBook


@pytest.mark.unit
def test_gold_suffix_variants_share_state_key() -> None:
    book = SymbolStateBook()
    a = book.get("XAUUSD")
    b = book.get("XAUUSD_i")
    assert a is b
    book.update_scan("XAUUSD_i", quality=88, confidence=80)
    assert book.get("XAUUSD").last_quality == 88
