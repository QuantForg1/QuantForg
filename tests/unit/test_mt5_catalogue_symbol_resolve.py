"""Catalogue identity aliases — XAUUSD_I must resolve to a live book name."""

from __future__ import annotations

import pytest

from services.mt5_gateway.symbol_resolve import (
    catalogue_exact_names,
    resolve_catalogue_symbol,
)


@pytest.mark.unit
@pytest.mark.trading_core
def test_xauusd_i_maps_to_unsuffixed_catalogue_gold() -> None:
    idx = {"XAUUSD": "XAUUSD"}
    assert resolve_catalogue_symbol("XAUUSD_I", idx) == "XAUUSD"
    assert resolve_catalogue_symbol("XAUUSD_i", idx) == "XAUUSD"
    assert catalogue_exact_names("XAUUSD_I", idx) == ("XAUUSD",)


@pytest.mark.unit
@pytest.mark.trading_core
def test_xauusd_i_maps_to_weltrade_lowercase_suffix() -> None:
    idx = {"XAUUSD_I": "XAUUSD_i"}
    assert resolve_catalogue_symbol("XAUUSD_I", idx) == "XAUUSD_i"
    assert resolve_catalogue_symbol("XAUUSD", idx) == "XAUUSD_i"


@pytest.mark.unit
@pytest.mark.trading_core
def test_unknown_symbol_does_not_steal_gold() -> None:
    idx = {"XAUUSD": "XAUUSD"}
    assert resolve_catalogue_symbol("NOTAREALSYM", idx) is None
    assert catalogue_exact_names("NOTAREALSYM", idx) == ()


@pytest.mark.unit
def test_eurusd_i_maps_to_unsuffixed_when_that_is_the_book() -> None:
    idx = {"EURUSD": "EURUSD"}
    assert resolve_catalogue_symbol("EURUSD_I", idx) == "EURUSD"
