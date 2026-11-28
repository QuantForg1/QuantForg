from __future__ import annotations

from unittest.mock import patch

from app.application.services import public_performance as pp


def _row(pnl: str, r: str, when: str = "2099-01-01T10:00:00+00:00") -> dict:
    return {
        "symbol": "XAUUSD",
        "side": "BUY",
        "status": "CLOSED",
        "pnl": pnl,
        "r_multiple": r,
        "opened_at": when,
    }


def test_includes_wins_and_losses_and_hides_identifiers() -> None:
    rows = [_row("2.0", "1.5"), _row("-1.0", "-1"), _row("-1.0", "-1")]
    with patch.object(pp, "fetch_closed_rows", return_value=rows):
        out = pp.build_public_performance()
    assert out["available"] is True
    s = out["all_time"]
    assert (s["trades"], s["wins"], s["losses"]) == (3, 1, 2)
    assert s["win_rate_pct"] == 33.3
    assert s["profit_factor"] == 1.0
    assert all(
        set(t) == {"opened_at", "side", "result_r", "outcome"} for t in out["recent"]
    )


def test_unavailable_when_db_down() -> None:
    with patch.object(pp, "fetch_closed_rows", return_value=None):
        assert pp.build_public_performance() == {"available": False}
