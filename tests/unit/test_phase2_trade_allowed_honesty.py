"""Registry Verified display must never invent MT5 trade_allowed truth."""

from __future__ import annotations

from app.domain.broker_connectivity.mt5_server_catalogue import broker_registry_rows


def test_registry_rows_expose_trade_allowed_separately_from_verified() -> None:
    rows = broker_registry_rows()
    assert rows
    for row in rows:
        assert "trade_allowed" in row
        assert "verification_status" in row or "display_label" in row
        # Display Verified does not imply we omit the MT5 permission field.
        if row.get("display_label") == "Verified":
            assert isinstance(row.get("trade_allowed"), bool)
