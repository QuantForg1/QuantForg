"""Payment confirmation + referral reward against a real PostgreSQL.

Runs with ``RUN_INTEGRATION=1`` and the POSTGRES_* variables used by CI.
Everything lives in a throwaway schema that is dropped afterwards.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="Set RUN_INTEGRATION=1 to run integration tests",
    ),
]

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase/migrations/20261120115928_referral_program.sql"
)

BASE_SCHEMA = """
CREATE TABLE users (
  id uuid PRIMARY KEY,
  subscription_plan_id text, subscription_status text,
  subscription_expires_at timestamptz, subscription_provider text,
  updated_at timestamptz
);
CREATE TABLE licenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  tier text NOT NULL, status text NOT NULL, seats int,
  issued_at timestamptz, expires_at timestamptz, revoked_at timestamptz,
  notes text, created_at timestamptz DEFAULT now(), updated_at timestamptz
);
CREATE TABLE billing_orders (
  id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
  plan_id text, status text, provider_status text, provider_payment_id text,
  pay_currency text, paid_at timestamptz, period_start timestamptz,
  period_end timestamptz, expires_at timestamptz, updated_at timestamptz
);
CREATE TABLE billing_trials (
  user_id uuid, status text, converted_at timestamptz, updated_at timestamptz
);
"""

PERIOD, GRACE = 30, 3


_ROLES_SQL = """
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated;
  END IF;
END$$
"""


def _url() -> str:
    return (
        f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:"
        f"{os.environ.get('POSTGRES_PASSWORD', '')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
    )


@pytest.fixture
async def db(request):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    schema = f"qf_ref_{uuid.uuid4().hex[:8]}"
    with_referrals = getattr(request, "param", True)
    engine = create_async_engine(
        _url(), connect_args={"server_settings": {"search_path": schema}}
    )
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
        await conn.execute(text(_ROLES_SQL))
        for stmt in BASE_SCHEMA.split(";"):
            if stmt.strip():
                await conn.execute(text(stmt))
        if with_referrals:
            sql = MIGRATION.read_text().replace("public.", "")
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(sql)  # multi-statement script
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    await engine.dispose()


def _svc():
    from app.application.services.billing_service import BillingService

    svc = object.__new__(BillingService)
    svc.settings = SimpleNamespace(billing_period_days=PERIOD, billing_grace_days=GRACE)
    return svc


async def _user(maker, *, license_expires: datetime | None = None) -> str:
    from sqlalchemy import text

    uid = str(uuid.uuid4())
    async with maker.begin() as s:
        await s.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": uid})
        if license_expires is not None:
            await s.execute(
                text(
                    "INSERT INTO licenses (user_id, tier, status, seats, expires_at)"
                    " VALUES (:u, 'starter', 'active', 1, :e)"
                ),
                {"u": uid, "e": license_expires},
            )
    return uid


async def _attribute(maker, referred: str, referrer: str, at: datetime) -> None:
    from sqlalchemy import text

    async with maker.begin() as s:
        await s.execute(
            text(
                "INSERT INTO referral_codes (user_id, code) VALUES (:r, :c)"
                " ON CONFLICT DO NOTHING"
            ),
            {"r": referrer, "c": referrer[:8].upper()},
        )
        await s.execute(
            text(
                "INSERT INTO referral_attributions"
                " (referred_user_id, referrer_user_id, code, created_at)"
                " VALUES (:a, :b, :c, :t)"
            ),
            {"a": referred, "b": referrer, "c": referrer[:8].upper(), "t": at},
        )


async def _pay(maker, user_id: str) -> str:
    from sqlalchemy import text

    oid = str(uuid.uuid4())
    async with maker.begin() as s:
        await s.execute(
            text(
                "INSERT INTO billing_orders (id, user_id, plan_id, status)"
                " VALUES (:id, :u, 'starter', 'pending_payment')"
            ),
            {"id": oid, "u": user_id},
        )
        order = {
            "id": oid,
            "user_id": user_id,
            "status": "pending_payment",
            "license_tier": "starter",
            "order_code": oid[:8],
            "plan_id": "starter",
        }
        result = await _svc()._fulfill_finished(
            s, order=order, payment_id="p", pay_currency="usdt"
        )
    assert result == "activated"
    return oid


async def _expiry(maker, user_id: str) -> datetime:
    from sqlalchemy import text

    async with maker() as s:
        return (
            await s.execute(
                text(
                    "SELECT max(expires_at) FROM licenses WHERE user_id = :u"
                    " AND status = 'active'"
                ),
                {"u": user_id},
            )
        ).scalar()


async def _events(maker) -> list[dict]:
    from sqlalchemy import text

    async with maker() as s:
        rows = await s.execute(
            text(
                "SELECT event_key, referred_user_id, beneficiary_user_id, reward_status"
                " FROM referral_events ORDER BY created_at"
            )
        )
        return [dict(r._mapping) for r in rows]


def _close(a: datetime, b: datetime, days: float) -> bool:
    return abs((a - b).total_seconds() - days * 86400) < 120


@pytest.mark.asyncio
async def test_first_payment_rewards_active_referrer_30_days_once(db) -> None:
    now = datetime.now(UTC)
    referrer = await _user(db, license_expires=now + timedelta(days=20))
    before = await _expiry(db, referrer)
    friend = await _user(db)
    await _attribute(db, friend, referrer, now - timedelta(minutes=5))

    await _pay(db, friend)
    assert _close(await _expiry(db, referrer), before, 30)
    events = await _events(db)
    assert len(events) == 1 and events[0]["reward_status"] == "applied"
    assert str(events[0]["beneficiary_user_id"]) == referrer

    # The friend renews: no second reward.
    await _pay(db, friend)
    assert _close(await _expiry(db, referrer), before, 30)
    assert len(await _events(db)) == 1


@pytest.mark.asyncio
async def test_reward_waits_for_referrer_without_subscription(db) -> None:
    now = datetime.now(UTC)
    referrer = await _user(db)
    friend = await _user(db)
    await _attribute(db, friend, referrer, now - timedelta(minutes=5))
    await _pay(db, friend)
    assert (await _events(db))[0]["reward_status"] == "pending"

    await _pay(db, referrer)  # referrer's own first payment
    exp = await _expiry(db, referrer)
    assert _close(exp, datetime.now(UTC), PERIOD + GRACE + 30)
    assert (await _events(db))[0]["reward_status"] == "applied"


@pytest.mark.asyncio
async def test_attribution_after_payment_or_without_one_gives_nothing(db) -> None:
    now = datetime.now(UTC)
    referrer = await _user(db, license_expires=now + timedelta(days=5))
    before = await _expiry(db, referrer)
    late = await _user(db)
    await _attribute(db, late, referrer, now + timedelta(hours=1))
    await _pay(db, late)
    stranger = await _user(db)
    await _pay(db, stranger)
    assert await _events(db) == []
    assert await _expiry(db, referrer) == before


@pytest.mark.asyncio
async def test_early_renewal_keeps_remaining_days(db) -> None:
    now = datetime.now(UTC)
    user = await _user(db, license_expires=now + timedelta(days=10 + GRACE))
    before = await _expiry(db, user)
    await _pay(db, user)
    assert _close(await _expiry(db, user), before, PERIOD)


@pytest.mark.asyncio
@pytest.mark.parametrize("db", [False], indirect=True)
async def test_payment_succeeds_when_referral_tables_are_missing(db) -> None:
    user = await _user(db)
    await _pay(db, user)
    assert _close(await _expiry(db, user), datetime.now(UTC), PERIOD + GRACE)
