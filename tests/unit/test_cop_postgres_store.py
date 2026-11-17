"""Support tickets survive deploys: Postgres-backed document store.

17 Nov 2026: tickets lived in a JSON file on the Railway container, which has
no volume, so every deploy erased them.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.domain.customer_operations import cop_persistence
from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    PostgresDocumentStore,
    durable_document_store,
)

pytestmark = [pytest.mark.unit]


class _FakeDP:
    """Minimal stand-in for direct_postgres over public.cop_documents."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.seq = 0

    def direct_postgres_available(self) -> bool:
        return True

    def fetch(self, query: str, *args: Any, timeout: float = 8.0) -> list[dict]:
        coll = args[0]
        mine = [r for r in self.rows if r["collection"] == coll]
        if "count(*)" in query:
            return [{"n": len(mine)}]
        if "AND id = $2" in query:
            return [{"doc": r["doc"]} for r in mine if r["id"] == args[1]]
        ordered = sorted(mine, key=lambda r: r["seq"], reverse=True)[: args[1]]
        return [{"doc": r["doc"]} for r in ordered]

    def execute(self, query: str, *args: Any, timeout: float = 8.0) -> str:
        if query.startswith("INSERT"):
            coll, doc_id, doc = args
            if any(r["collection"] == coll and r["id"] == doc_id for r in self.rows):
                raise RuntimeError("duplicate key")
            self.seq += 1
            self.rows.append(
                {"collection": coll, "id": doc_id, "doc": doc, "seq": self.seq}
            )
            return "INSERT 0 1"
        coll, doc_id, doc = args
        for r in self.rows:
            if r["collection"] == coll and r["id"] == doc_id:
                r["doc"] = doc
        return "UPDATE 1"


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> tuple[PostgresDocumentStore, _FakeDP]:
    fake = _FakeDP()
    monkeypatch.setattr(PostgresDocumentStore, "_dp", staticmethod(lambda: fake))
    return PostgresDocumentStore("tickets"), fake


def test_append_get_list_order_and_redaction(
    store: tuple[PostgresDocumentStore, _FakeDP],
) -> None:
    s, fake = store
    s.append({"id": "t1", "subject": "a", "password": "hunter2"})
    s.append({"id": "t2", "subject": "b"})
    s.append({"id": "t3", "subject": "c"})
    assert [d["id"] for d in s.list(limit=2)] == ["t2", "t3"]
    assert s.count() == 3
    got = s.get("t1")
    assert got is not None and got["subject"] == "a"
    assert "hunter2" not in json.dumps(fake.rows)  # secrets never stored


def test_upsert_updates_and_missing_returns_none(
    store: tuple[PostgresDocumentStore, _FakeDP],
) -> None:
    s, _ = store
    s.append({"id": "t1", "status": "open"})
    out = s.upsert("t1", lambda d: {**d, "status": "closed"})
    assert out is not None and out["status"] == "closed" and out["updated_at"]
    assert s.get("t1")["status"] == "closed"  # type: ignore[index]
    assert s.upsert("nope", lambda d: d) is None


def test_collections_are_separate(
    store: tuple[PostgresDocumentStore, _FakeDP],
) -> None:
    s, fake = store
    s.append({"id": "t1"})
    other = PostgresDocumentStore("other")
    assert other.list() == [] and other.get("t1") is None
    assert len(fake.rows) == 1


def test_append_requires_id(store: tuple[PostgresDocumentStore, _FakeDP]) -> None:
    s, _ = store
    with pytest.raises(ValueError):
        s.append({"subject": "x"})


def test_factory_uses_postgres_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from app.infrastructure.persistence import direct_postgres as dp

    monkeypatch.setattr(dp, "direct_postgres_available", lambda: True)
    assert isinstance(
        durable_document_store("x.json", "tickets"), PostgresDocumentStore
    )
    monkeypatch.setattr(dp, "direct_postgres_available", lambda: False)
    monkeypatch.setattr(cop_persistence, "data_path", lambda f: tmp_path / f)
    assert isinstance(durable_document_store("x.json", "tickets"), JsonDocumentStore)
