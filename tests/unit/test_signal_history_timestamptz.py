"""signal_history direct upsert: observed_at must be a datetime (2026-10-23).

Live every write failed: asyncpg "expected a datetime.date or datetime.datetime
instance, got 'str'" for $2::timestamptz, so signal_history stayed empty.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.services import signal_intelligence_service as sis

pytestmark = pytest.mark.unit


def test_direct_upsert_sends_observed_at_as_aware_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.persistence import direct_postgres

    captured: list = []

    def fake_executemany(query, args_seq, **_kw):
        captured.extend(args_seq)
        return len(args_seq)

    monkeypatch.setattr(direct_postgres, "direct_postgres_available", lambda: True)
    monkeypatch.setattr(direct_postgres, "executemany", fake_executemany)
    rows = [
        {
            "observed_at": "2026-10-23T09:18:14.356856Z",
            "scan_as_of": "2026-10-23T09:18:14Z",
            "symbol": "xauusd",
            "direction": "SELL",
        },
        {"scan_as_of": "2026-10-23T09:18:15Z", "symbol": "XAUUSD"},
    ]
    assert sis._upsert_history_direct(rows) == 2
    first, second = captured
    assert first[1] == datetime(2026, 10, 23, 9, 18, 14, 356856, tzinfo=UTC)
    assert isinstance(second[1], datetime) and second[1].tzinfo is not None
    assert first[3] == "XAUUSD"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-23T09:18:14Z", datetime(2026, 10, 23, 9, 18, 14, tzinfo=UTC)),
        ("2026-10-23T09:18:14+00:00", datetime(2026, 10, 23, 9, 18, 14, tzinfo=UTC)),
        (
            datetime(2026, 10, 23, 9, 18, 14),
            datetime(2026, 10, 23, 9, 18, 14, tzinfo=UTC),
        ),
    ],
)
def test_as_utc_datetime(value, expected) -> None:
    assert sis._as_utc_datetime(value) == expected


def test_unparseable_value_falls_back_to_now() -> None:
    got = sis._as_utc_datetime("not-a-date")
    assert got.tzinfo is not None
    assert abs((datetime.now(UTC) - got).total_seconds()) < 5
