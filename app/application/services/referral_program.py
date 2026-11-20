"""Referral program: codes, attribution and the reward ledger view.

Rewards (30 subscription days for the referrer) are created only inside
the payment confirmation, see ``referral_rewards``. Customers cannot mint
them through this API.
"""

from __future__ import annotations

import secrets
from typing import Any, Protocol

from app.domain.referrals.ledger import (
    Attribution,
    attribute_referral,
    record_qualifying_event,
)


class DuplicateRecord(Exception):
    """The database already has this code or attribution."""


class StoreUnavailable(Exception):
    """The referral tables are not available."""


class ReferralStore(Protocol):
    async def code_for(self, user_id: str) -> str | None: ...

    async def save_code(self, user_id: str, code: str) -> None: ...

    async def code_owner(self, code: str) -> str | None: ...

    async def attribution_for(self, referred_user_id: str) -> Attribution | None: ...

    async def save_attribution(self, attribution: Attribution) -> None: ...

    async def history_for(self, referrer_user_id: str) -> list[dict[str, Any]]: ...

    async def events_for(self, referrer_user_id: str) -> list[dict[str, Any]]: ...

    async def known_events(self) -> frozenset[str]: ...

    async def save_event(
        self,
        *,
        event_id: str,
        event_type: str,
        referred_user_id: str | None,
        decision: dict[str, Any],
    ) -> None: ...

    async def attempts_allowed(self, user_id: str, *, limit: int) -> bool: ...

    async def record_attempt(self, user_id: str, outcome: str) -> None: ...

    async def has_paid(self, user_id: str) -> bool: ...


class MemoryReferralStore:
    """Process-local store used by tests and as a behavior reference."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}
        self.owners: dict[str, str] = {}
        self.attributions: dict[str, Attribution] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, list[str]] = {}
        self.paid: set[str] = set()
        self.rewards: list[dict[str, Any]] = []

    async def code_for(self, user_id: str) -> str | None:
        return self.codes.get(user_id)

    async def save_code(self, user_id: str, code: str) -> None:
        if user_id in self.codes or code in self.owners:
            raise DuplicateRecord
        self.codes[user_id] = code
        self.owners[code] = user_id

    async def code_owner(self, code: str) -> str | None:
        return self.owners.get(code)

    async def attribution_for(self, referred_user_id: str) -> Attribution | None:
        return self.attributions.get(referred_user_id)

    async def save_attribution(self, attribution: Attribution) -> None:
        if attribution.referred_user_id in self.attributions:
            raise DuplicateRecord
        self.attributions[attribution.referred_user_id] = attribution

    async def history_for(self, referrer_user_id: str) -> list[dict[str, Any]]:
        return [
            {"status": "attributed", "code": item.code}
            for item in self.attributions.values()
            if item.referrer_user_id == referrer_user_id
        ]

    async def events_for(self, referrer_user_id: str) -> list[dict[str, Any]]:
        rows = []
        for event in self.events.values():
            attribution = self.attributions.get(str(event.get("referred_user_id")))
            if (
                attribution is not None
                and attribution.referrer_user_id == referrer_user_id
            ):
                rows.append(
                    {
                        "event_id": event["event_id"],
                        "reward_amount": None,
                        "reward_status": event["reward_status"],
                    }
                )
        rows.extend(
            dict(row)
            for row in self.rewards
            if row.get("beneficiary_user_id") == referrer_user_id
        )
        return rows

    async def has_paid(self, user_id: str) -> bool:
        return user_id in self.paid

    async def known_events(self) -> frozenset[str]:
        return frozenset(self.events)

    async def save_event(
        self,
        *,
        event_id: str,
        event_type: str,
        referred_user_id: str | None,
        decision: dict[str, Any],
    ) -> None:
        if event_id in self.events:
            raise DuplicateRecord
        self.events[event_id] = {
            "event_id": event_id,
            "event_type": event_type,
            "referred_user_id": referred_user_id,
            "reward_status": decision["reward_status"],
        }

    async def attempts_allowed(self, user_id: str, *, limit: int) -> bool:
        return len(self.attempts.get(user_id, [])) < limit

    async def record_attempt(self, user_id: str, outcome: str) -> None:
        self.attempts.setdefault(user_id, []).append(outcome)


class ReferralProgram:
    """Issues codes and stores attributions. It does not pay rewards."""

    def __init__(self, store: ReferralStore) -> None:
        self._store = store

    async def summary(self, user_id: str) -> dict[str, Any]:
        issued = await self._ensure_code(user_id)
        rewards = await self._store.events_for(user_id)
        applied = sum(
            int(r.get("reward_days") or 0)
            for r in rewards
            if r.get("reward_status") == "applied"
        )
        pending = sum(
            int(r.get("reward_days") or 0)
            for r in rewards
            if r.get("reward_status") == "pending"
        )
        return {
            "available": True,
            "code": issued["code"],
            "link_path": issued["link_path"],
            "history": await self._store.history_for(user_id),
            "rewards": rewards,
            "reward_rule": {
                "kind": "free_month",
                "days": 30,
                "when": "first confirmed payment of a customer you referred",
            },
            "reward_days_applied": applied,
            "reward_days_pending": pending,
            "reward_balance": None,
            "sales_or_payouts": False,
        }

    async def attribute(self, *, user_id: str, code: str) -> dict[str, Any]:
        if not await self._store.attempts_allowed(user_id, limit=10):
            await self._store.record_attempt(user_id, "rate_limited")
            return _rejected("rate_limited")
        if await self._store.has_paid(user_id):
            await self._store.record_attempt(user_id, "existing_customer")
            return _rejected("existing_customer")
        owner = await self._store.code_owner(code.strip().upper())
        existing = await self._store.attribution_for(user_id)
        decision = attribute_referral(
            code=code,
            referrer_user_id=owner or "",
            referred_user_id=user_id,
            existing=() if existing is None else (existing,),
        )
        if owner is None and decision["reason"] != "self_referral":
            decision = _rejected("invalid_referral")
        await self._store.record_attempt(user_id, str(decision["reason"]))
        if decision["status"] != "attributed":
            return decision
        try:
            await self._store.save_attribution(
                Attribution(
                    referred_user_id=user_id,
                    referrer_user_id=str(decision["referrer_user_id"]),
                    code=str(decision["code"]),
                )
            )
        except DuplicateRecord:
            return _rejected("duplicate_attribution")
        return decision

    async def record_event(
        self,
        *,
        event_id: str,
        event_type: str,
        referred_user_id: str | None,
    ) -> dict[str, Any]:
        """Server-side only. Customers cannot call this to mint a reward."""
        decision = record_qualifying_event(
            event_id=event_id,
            event_type=event_type,
            already_recorded=await self._store.known_events(),
        )
        if decision["status"] == "rejected":
            return decision
        if (
            referred_user_id is None
            or await self._store.attribution_for(referred_user_id) is None
        ):
            decision = {
                **decision,
                "status": "recorded",
                "reason": "no_attribution",
                "reward_amount": None,
                "reward_status": "not_qualified",
            }
        try:
            await self._store.save_event(
                event_id=event_id.strip(),
                event_type=event_type,
                referred_user_id=referred_user_id,
                decision=decision,
            )
        except DuplicateRecord:
            return _rejected("duplicate_event")
        return decision

    async def _ensure_code(self, user_id: str) -> dict[str, str]:
        current = await self._store.code_for(user_id)
        if current:
            return {"code": current, "link_path": f"/register?ref={current}"}
        for _ in range(5):
            code = secrets.token_hex(4).upper()
            try:
                await self._store.save_code(user_id, code)
            except DuplicateRecord:
                continue
            return {"code": code, "link_path": f"/register?ref={code}"}
        raise StoreUnavailable


def _rejected(reason: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "reason": reason,
        "reward_amount": None,
        "reward_status": "not_issued",
    }
