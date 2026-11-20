"""Postgres referral store. Missing tables stay unavailable."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.application.services.referral_program import DuplicateRecord, StoreUnavailable
from app.domain.referrals.ledger import Attribution


def _unavailable(exc: ProgrammingError) -> StoreUnavailable | ProgrammingError:
    if "does not exist" in str(exc).lower():
        return StoreUnavailable()
    return exc


class PostgresReferralStore:
    def __init__(self, database: Any) -> None:
        self._database = database

    async def code_for(self, user_id: str) -> str | None:
        row = await self._one(
            "SELECT code FROM referral_codes WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        return None if row is None else str(row[0])

    async def save_code(self, user_id: str, code: str) -> None:
        await self._write(
            "INSERT INTO referral_codes (user_id, code) VALUES (:user_id, :code)",
            {"user_id": user_id, "code": code},
        )

    async def code_owner(self, code: str) -> str | None:
        row = await self._one(
            "SELECT user_id FROM referral_codes WHERE code = :code",
            {"code": code},
        )
        return None if row is None else str(row[0])

    async def attribution_for(self, referred_user_id: str) -> Attribution | None:
        row = await self._one(
            "SELECT referred_user_id, referrer_user_id, code "
            "FROM referral_attributions WHERE referred_user_id = :user_id",
            {"user_id": referred_user_id},
        )
        if row is None:
            return None
        return Attribution(str(row[0]), str(row[1]), str(row[2]))

    async def save_attribution(self, attribution: Attribution) -> None:
        await self._write(
            "INSERT INTO referral_attributions "
            "(referred_user_id, referrer_user_id, code) "
            "VALUES (:referred, :referrer, :code)",
            {
                "referred": attribution.referred_user_id,
                "referrer": attribution.referrer_user_id,
                "code": attribution.code,
            },
        )

    async def history_for(self, referrer_user_id: str) -> list[dict[str, Any]]:
        rows = await self._all(
            "SELECT code FROM referral_attributions "
            "WHERE referrer_user_id = :user_id ORDER BY created_at DESC",
            {"user_id": referrer_user_id},
        )
        return [{"status": "attributed", "code": str(row[0])} for row in rows]

    async def events_for(self, referrer_user_id: str) -> list[dict[str, Any]]:
        rows = await self._all(
            "SELECT event_key, reward_status, reward_kind, reward_days, "
            "created_at, applied_at FROM referral_events "
            "WHERE beneficiary_user_id = :user_id ORDER BY created_at DESC",
            {"user_id": referrer_user_id},
        )
        return [
            {
                "event_id": str(row[0]),
                "reward_amount": None,
                "reward_status": str(row[1]),
                "reward_kind": None if row[2] is None else str(row[2]),
                "reward_days": None if row[3] is None else int(row[3]),
                "created_at": None if row[4] is None else row[4].isoformat(),
                "applied_at": None if row[5] is None else row[5].isoformat(),
            }
            for row in rows
        ]

    async def has_paid(self, user_id: str) -> bool:
        row = await self._one(
            "SELECT 1 FROM billing_orders WHERE user_id = :user_id "
            "AND paid_at IS NOT NULL LIMIT 1",
            {"user_id": user_id},
        )
        return row is not None

    async def known_events(self) -> frozenset[str]:
        rows = await self._all("SELECT event_key FROM referral_events", {})
        return frozenset(str(row[0]) for row in rows)

    async def save_event(
        self,
        *,
        event_id: str,
        event_type: str,
        referred_user_id: str | None,
        decision: dict[str, Any],
    ) -> None:
        await self._write(
            "INSERT INTO referral_events "
            "(event_key, event_type, referred_user_id, reward_status) "
            "VALUES (:event_id, :event_type, :referred, :reward_status)",
            {
                "event_id": event_id,
                "event_type": event_type,
                "referred": referred_user_id,
                "reward_status": decision["reward_status"],
            },
        )

    async def attempts_allowed(self, user_id: str, *, limit: int) -> bool:
        row = await self._one(
            "SELECT count(*) FROM referral_attempts "
            "WHERE user_id = :user_id "
            "AND created_at > now() - interval '1 hour'",
            {"user_id": user_id},
        )
        count = 0 if row is None else int(row[0])
        return count < limit

    async def record_attempt(self, user_id: str, outcome: str) -> None:
        await self._write(
            "INSERT INTO referral_attempts (user_id, outcome) "
            "VALUES (:user_id, :outcome)",
            {"user_id": user_id, "outcome": outcome},
        )

    async def _one(self, sql: str, params: dict[str, Any]) -> Any:
        rows = await self._all(sql, params)
        return None if not rows else rows[0]

    async def _all(self, sql: str, params: dict[str, Any]) -> list[Any]:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), params)
                return list(result.all())
        except ProgrammingError as exc:
            raise _unavailable(exc) from exc

    async def _write(self, sql: str, params: dict[str, Any]) -> None:
        try:
            async with self._database.session() as session:
                await session.execute(text(sql), params)
        except IntegrityError as exc:
            raise DuplicateRecord from exc
        except ProgrammingError as exc:
            raise _unavailable(exc) from exc
