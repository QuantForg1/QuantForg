"""Durable Weltrade account selection and encrypted broker password.

The selected account lives in ``broker_accounts``. The password, when the
owner submits one, is stored only as AES-GCM ciphertext in
``broker_credentials``. Callers never receive the ciphertext or the
plaintext. A missing store does not invent a connection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import BrokerAccount, BrokerCredential
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCredentialType,
    BrokerEnvironment,
    BrokerPlatform,
    BrokerType,
    CredentialStatus,
)
from app.domain.value_objects.identity import EntitySlug
from core.logging import get_logger
from core.security.credential_encryption import CredentialEncryptionService
from core.security.crypto import credential_hint

logger = get_logger(__name__)

WELTRADE_SLUG = "weltrade"
_MIN_SECRET_LEN = 32


def _broker_label(broker: Any, name: str, slug: str) -> str:
    raw = getattr(broker.name, "value", broker.name)
    return str(raw or name or slug or "MT5")


class BrokerSecretStore:
    """Persist the owner's selected Weltrade account in the broker tables."""

    def __init__(self, uow_factory: Any, *, secret_key: str) -> None:
        self._uow_factory = uow_factory
        self._secret_key = secret_key

    def _crypto(self) -> CredentialEncryptionService | None:
        if len(self._secret_key) < _MIN_SECRET_LEN:
            return None
        return CredentialEncryptionService(secret_key=self._secret_key, key_version=1)

    async def save_selection(
        self,
        *,
        user_id: UUID,
        login: int,
        server: str,
        environment: str,
        currency: str = "",
        account_mode: str = "",
        trade_allowed: bool | None = None,
        password: str = "",
        broker_slug: str = WELTRADE_SLUG,
        broker_name: str = "",
        pending_terminal: bool = False,
    ) -> bool:
        """Upsert the verified account. Encrypt ``password`` only when present.

        ``pending_terminal``: saved for a dedicated worker terminal; the shared
        platform terminal is never touched (customer accounts).
        """
        if self._uow_factory is None or int(login) <= 1 or not str(server).strip():
            return False
        crypto = self._crypto()
        if password and crypto is None:
            logger.warning(
                "broker_secret_persist_skipped",
                reason="encryption_key_too_short",
            )
            return False
        env = (
            BrokerEnvironment.LIVE
            if str(environment).strip().lower() == "live"
            else BrokerEnvironment.DEMO
        )
        verified = datetime.now(UTC).isoformat()
        meta = {
            "selected": "true",
            "currency": str(currency or ""),
            "account_mode": str(account_mode or ""),
            "trade_allowed": (
                "" if trade_allowed is None else "true" if trade_allowed else "false"
            ),
            "last_verified": "" if pending_terminal else verified,
        }
        if pending_terminal:
            meta["assignment"] = "pending_terminal"
            meta["submitted_at"] = verified
        try:
            async with self._uow_factory() as uow:
                broker = await self._ensure_broker(
                    uow, slug=broker_slug, name=broker_name
                )
                # One non-revoked account per user (DB unique index). A new
                # login or broker replaces the previous account.
                await self._retire_replaced_accounts(
                    uow, user_id=user_id, broker_id=broker.id, login=int(login)
                )
                account = await self._upsert_account(
                    uow,
                    label=str(
                        getattr(broker.name, "value", broker.name)
                        or broker_name
                        or broker_slug
                    ),
                    broker_id=broker.id,
                    user_id=user_id,
                    login=int(login),
                    server=str(server).strip(),
                    environment=env,
                    metadata=meta,
                )
                await self._deselect_others(
                    uow, user_id=user_id, broker_id=broker.id, keep_id=account.id
                )
                if password and crypto is not None:
                    await self._store_password(
                        uow, account_id=account.id, password=password, crypto=crypto
                    )
                await uow.commit()
        except Exception:
            logger.exception("broker_secret_persist_failed")
            return False
        logger.info(
            "broker_secret_saved",
            user_id=str(user_id),
            has_password=bool(password),
            environment=env.value,
        )
        return True

    async def public_selection(self, *, user_id: UUID) -> dict[str, Any] | None:
        """Non-secret selected-account view. Never includes ciphertext."""
        row = await self._selected_account(user_id)
        if row is None:
            return None
        account, has_secret, broker_slug = row
        return {
            "broker": broker_slug or WELTRADE_SLUG,
            "server": account.server,
            "login": int(account.external_account_id),
            "environment": account.environment.value,
            "account_mode": str(account.metadata.get("account_mode") or ""),
            "currency": str(account.metadata.get("currency") or ""),
            "trade_allowed": str(account.metadata.get("trade_allowed") or ""),
            "last_verified": account.metadata.get("last_verified") or None,
            "has_encrypted_password": has_secret,
            "assignment": str(account.metadata.get("assignment") or ""),
            "selected": True,
        }

    async def clear_selection(self, *, user_id: UUID) -> bool:
        """Deselect and revoke the user's selected broker account(s).

        Never touches the shared platform MT5 session. Idempotent when nothing
        is selected. Credentials are revoked so workers cannot re-login.
        """
        if self._uow_factory is None:
            return False
        cleared = 0
        try:
            async with self._uow_factory() as uow:
                accounts = list(await uow.accounts.list_for_user(user_id))
                selected = [
                    a
                    for a in accounts
                    if a.status != BrokerAccountStatus.REVOKED
                    and str(a.metadata.get("selected") or "") == "true"
                ]
                targets = selected or [
                    a for a in accounts if a.status == BrokerAccountStatus.ACTIVE
                ]
                for account in targets:
                    meta = dict(account.metadata)
                    meta["selected"] = "false"
                    meta.pop("assignment", None)
                    account.update_fields(metadata=meta)
                    account.revoke()
                    await uow.accounts.update(account)
                    cred = await uow.credentials.get_by_account_and_type(
                        account.id, BrokerCredentialType.PASSWORD
                    )
                    if cred is not None and cred.status != CredentialStatus.REVOKED:
                        cred.status = CredentialStatus.REVOKED
                        await uow.credentials.update(cred)
                    cleared += 1
                await uow.commit()
        except Exception:
            logger.exception("broker_secret_clear_failed")
            return False
        logger.info(
            "broker_secret_cleared",
            user_id=str(user_id),
            cleared=cleared,
        )
        return True

    async def requeue_selection(self, *, user_id: UUID) -> dict[str, Any] | None:
        """Mark the selected account as pending worker assignment again.

        Requires an encrypted password already on file. Does not call the
        shared platform terminal. Idempotent when already pending.
        """
        if self._uow_factory is None:
            return None
        try:
            async with self._uow_factory() as uow:
                selected: BrokerAccount | None = None
                broker_slug = WELTRADE_SLUG
                for account in await uow.accounts.list_for_user(user_id):
                    if account.status in {
                        BrokerAccountStatus.REVOKED,
                        BrokerAccountStatus.INACTIVE,
                    }:
                        continue
                    if str(account.metadata.get("selected") or "") != "true":
                        continue
                    selected = account
                    broker = await uow.brokers.get_by_id(account.broker_id)
                    if broker is not None:
                        broker_slug = str(
                            getattr(broker.slug, "value", broker.slug) or ""
                        )
                    break
                if selected is None:
                    return None
                cred = await uow.credentials.get_by_account_and_type(
                    selected.id, BrokerCredentialType.PASSWORD
                )
                if (
                    cred is None
                    or cred.status == CredentialStatus.REVOKED
                    or not cred.encrypted_payload
                ):
                    return {
                        "ok": False,
                        "code": "PASSWORD_REQUIRED",
                        "message": (
                            "Enter your MT5 master password to reconnect this account."
                        ),
                    }
                meta = dict(selected.metadata)
                meta["assignment"] = "pending_terminal"
                meta["submitted_at"] = datetime.now(UTC).isoformat()
                meta["selected"] = "true"
                selected.update_fields(metadata=meta)
                if selected.status != BrokerAccountStatus.ACTIVE:
                    selected.activate()
                await uow.accounts.update(selected)
                await uow.commit()
                return {
                    "ok": True,
                    "state": "QUEUED_FOR_TERMINAL",
                    "broker": broker_slug,
                    "environment": selected.environment.value.upper(),
                    "login": int(selected.external_account_id),
                    "server": selected.server,
                    "message": (
                        "Requeued. Your account is assigned to a QuantForg "
                        "trading terminal automatically."
                    ),
                }
        except Exception:
            logger.exception("broker_secret_requeue_failed")
            return None

    async def load_password(self, *, user_id: UUID) -> tuple[int, str, str, str] | None:
        """Return ``(login, server, environment, password)`` for restore.

        The plaintext stays in the caller. This method does not log it.
        """
        crypto = self._crypto()
        if crypto is None or self._uow_factory is None:
            return None
        try:
            async with self._uow_factory() as uow:
                broker = await uow.brokers.get_by_slug(EntitySlug(value=WELTRADE_SLUG))
                if broker is None:
                    return None
                account = await self._find_selected(
                    uow, user_id=user_id, broker_id=broker.id
                )
                if account is None:
                    return None
                cred = await uow.credentials.get_by_account_and_type(
                    account.id, BrokerCredentialType.PASSWORD
                )
                if cred is None or cred.status == CredentialStatus.REVOKED:
                    return None
                password = crypto.decrypt(cred.encrypted_payload)
        except Exception:
            logger.exception("broker_secret_load_failed")
            return None
        if not password:
            return None
        return (
            int(account.external_account_id),
            account.server,
            account.environment.value,
            password,
        )

    async def _selected_account(
        self, user_id: UUID
    ) -> tuple[BrokerAccount, bool, str] | None:
        """Return the user's selected account across any registered broker."""
        if self._uow_factory is None:
            return None
        try:
            async with self._uow_factory() as uow:
                chosen: BrokerAccount | None = None
                broker_slug = WELTRADE_SLUG
                for account in await uow.accounts.list_for_user(user_id):
                    if account.status in {
                        BrokerAccountStatus.REVOKED,
                        BrokerAccountStatus.INACTIVE,
                    }:
                        continue
                    if str(account.metadata.get("selected") or "") == "true":
                        chosen = account
                        broker = await uow.brokers.get_by_id(account.broker_id)
                        if broker is not None:
                            broker_slug = str(
                                getattr(broker.slug, "value", broker.slug)
                                or WELTRADE_SLUG
                            )
                        break
                    if chosen is None:
                        chosen = account
                        broker = await uow.brokers.get_by_id(account.broker_id)
                        if broker is not None:
                            broker_slug = str(
                                getattr(broker.slug, "value", broker.slug)
                                or WELTRADE_SLUG
                            )
                if chosen is None:
                    return None
                cred = await uow.credentials.get_by_account_and_type(
                    chosen.id, BrokerCredentialType.PASSWORD
                )
                has_secret = (
                    cred is not None
                    and cred.status != CredentialStatus.REVOKED
                    and bool(cred.encrypted_payload)
                )
                return chosen, has_secret, broker_slug
        except Exception:
            logger.exception("broker_secret_public_load_failed")
            return None

    async def _ensure_broker(
        self, uow: Any, *, slug: str = WELTRADE_SLUG, name: str = ""
    ) -> Broker:
        key = (slug or WELTRADE_SLUG).strip().lower()
        entity_slug = EntitySlug(value=key)
        existing = await uow.brokers.get_by_slug(entity_slug)
        if existing is not None:
            return cast("Broker", existing)
        if key != WELTRADE_SLUG:
            broker = Broker.register(
                name=name or key.replace("-", " ").title(),
                slug=entity_slug,
                broker_type=BrokerType.RETAIL,
                platform_code=BrokerPlatform.MT5,
                country_code="SC",
                website="",
                description=f"{name or key} MT5",
            )
            broker.activate()
            await uow.brokers.add(broker)
            return broker
        broker = Broker.register(
            name="Weltrade",
            slug=entity_slug,
            broker_type=BrokerType.RETAIL,
            platform_code=BrokerPlatform.MT5,
            country_code="SC",
            website="https://www.weltrade.com",
            description="Weltrade MT5",
        )
        broker.activate()
        await uow.brokers.add(broker)
        return broker

    async def _upsert_account(
        self,
        uow: Any,
        *,
        broker_id: UUID,
        user_id: UUID,
        login: int,
        server: str,
        environment: BrokerEnvironment,
        metadata: dict[str, str],
        label: str = "MT5",
    ) -> BrokerAccount:
        found = await uow.accounts.get_by_user_broker_external(
            user_id, broker_id, str(login)
        )
        if found is not None and found.status == BrokerAccountStatus.REVOKED:
            found = None
        if found is None:
            account = BrokerAccount.link(
                user_id=user_id,
                broker_id=broker_id,
                external_account_id=str(login),
                label=label,
                environment=environment,
                server=server,
                metadata=metadata,
            )
            account.activate()
            await uow.accounts.add(account)
            return account
        found.update_fields(
            server=server, environment=environment, metadata=metadata, label=label
        )
        if found.status != BrokerAccountStatus.ACTIVE:
            found.activate()
        await uow.accounts.update(found)
        return cast("BrokerAccount", found)

    async def _retire_replaced_accounts(
        self, uow: Any, *, user_id: UUID, broker_id: UUID, login: int
    ) -> None:
        """Revoke the user's other non-revoked accounts and their credentials.

        Runs before the insert so the one-account-per-user index never trips.
        The same broker + login is kept (it is updated in place).
        """
        for account in await uow.accounts.list_for_user(user_id):
            if account.status == BrokerAccountStatus.REVOKED:
                continue
            if account.broker_id == broker_id and str(
                account.external_account_id
            ) == str(login):
                continue
            meta = dict(account.metadata)
            meta["selected"] = "false"
            meta["replaced_at"] = datetime.now(UTC).isoformat()
            account.update_fields(metadata=meta)
            account.revoke()
            await uow.accounts.update(account)
            cred = await uow.credentials.get_by_account_and_type(
                account.id, BrokerCredentialType.PASSWORD
            )
            if cred is not None and cred.status != CredentialStatus.REVOKED:
                cred.revoke()
                await uow.credentials.update(cred)
            logger.info(
                "broker_account_replaced",
                user_id=str(user_id),
                replaced_account_id=str(account.id),
            )

    async def _deselect_others(
        self, uow: Any, *, user_id: UUID, broker_id: UUID, keep_id: UUID
    ) -> None:
        for account in await uow.accounts.list_for_user(user_id):
            if account.id == keep_id or account.broker_id != broker_id:
                continue
            if account.status == BrokerAccountStatus.REVOKED:
                continue
            meta = dict(account.metadata)
            meta["selected"] = "false"
            account.update_fields(metadata=meta)
            if account.status == BrokerAccountStatus.ACTIVE:
                account.deactivate()
            await uow.accounts.update(account)

    async def _store_password(
        self,
        uow: Any,
        *,
        account_id: UUID,
        password: str,
        crypto: CredentialEncryptionService,
    ) -> None:
        ciphertext, version = crypto.encrypt(password)
        hint = credential_hint(password, visible=0)
        existing = await uow.credentials.get_by_account_and_type(
            account_id, BrokerCredentialType.PASSWORD
        )
        if existing is None:
            cred = BrokerCredential.store(
                broker_account_id=account_id,
                credential_type=BrokerCredentialType.PASSWORD,
                encrypted_payload=ciphertext,
                key_hint=hint,
                encryption_key_version=version,
            )
            await uow.credentials.add(cred)
            return
        existing.encrypted_payload = ciphertext
        existing.key_hint = hint
        existing.encryption_key_version = version
        existing.status = CredentialStatus.ACTIVE
        await uow.credentials.update(existing)

    async def _find_selected(
        self, uow: Any, *, user_id: UUID, broker_id: UUID
    ) -> BrokerAccount | None:
        chosen: BrokerAccount | None = None
        for account in await uow.accounts.list_for_user(user_id):
            if account.broker_id != broker_id:
                continue
            if account.status in {
                BrokerAccountStatus.REVOKED,
                BrokerAccountStatus.INACTIVE,
            }:
                continue
            if str(account.metadata.get("selected") or "") == "true":
                return cast("BrokerAccount", account)
            chosen = account
        return chosen
