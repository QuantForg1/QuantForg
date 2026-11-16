"""Workers receive the customer's own vault credentials, owner-checked."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.worker_credential_vault import load_vault_credential
from core.security.credential_encryption import CredentialEncryptionService

pytestmark = [pytest.mark.unit]

KEY = "k" * 48


def _row(**over: object) -> dict[str, object]:
    token, _ = CredentialEncryptionService(secret_key=KEY, key_version=1).encrypt(
        "s3cret-master"
    )
    base: dict[str, object] = {
        "external_account_id": "12345678",
        "server": "XMGlobal-MT5 2",
        "environment": "demo",
        "status": "active",
        "encrypted_payload": token,
    }
    base.update(over)
    return base


def test_decrypts_the_assigned_account_password() -> None:
    seen: list[tuple[object, ...]] = []

    def fetch(_q: str, *args: object) -> list[dict[str, object]]:
        seen.append(args)
        return [_row()]

    acct, user = uuid4(), uuid4()
    cred = load_vault_credential(
        broker_account_id=acct, user_id=user, fetch=fetch, keys=(KEY, ())
    )
    assert cred is not None
    assert cred.password == "s3cret-master"
    assert cred.login == "12345678" and cred.server == "XMGlobal-MT5 2"
    assert seen == [(str(acct), str(user))]  # ownership is part of the query
    assert "s3cret" not in repr(cred)


def test_no_row_means_no_credential() -> None:
    assert (
        load_vault_credential(
            broker_account_id=uuid4(),
            user_id=uuid4(),
            fetch=lambda *_a: [],
            keys=(KEY, ()),
        )
        is None
    )


def test_revoked_account_is_refused() -> None:
    assert (
        load_vault_credential(
            broker_account_id=uuid4(),
            user_id=uuid4(),
            fetch=lambda *_a: [_row(status="revoked")],
            keys=(KEY, ()),
        )
        is None
    )


def test_wrong_key_is_refused_not_guessed() -> None:
    assert (
        load_vault_credential(
            broker_account_id=uuid4(),
            user_id=uuid4(),
            fetch=lambda *_a: [_row()],
            keys=("z" * 48, ()),
        )
        is None
    )


def test_read_error_is_refused() -> None:
    def boom(*_a: object) -> list[dict[str, object]]:
        raise RuntimeError("db down")

    assert (
        load_vault_credential(
            broker_account_id=uuid4(), user_id=uuid4(), fetch=boom, keys=(KEY, ())
        )
        is None
    )
