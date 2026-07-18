"""Quant Studio — in-memory strategy marketplace (no DB schema change)."""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


class StrategyMarketplaceStore:
    """Process-memory catalog for strategy lifecycle operations.

    Supports save, version, compare, share, clone, publish, and favorite actions.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self._favorites: dict[str, set[str]] = {}

    def save(
        self,
        *,
        user_id: UUID,
        name: str,
        graph: dict[str, Any],
        assumptions: dict[str, Any] | None = None,
        notes: str = "",
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            now = datetime.now(UTC).isoformat()
            if strategy_id and strategy_id in self._items:
                item = self._items[strategy_id]
                if str(item["owner_id"]) != str(user_id):
                    return {
                        "status": "forbidden",
                        "reason": "Cannot modify another user's strategy",
                    }
                versions = list(item.get("versions") or [])
                version = len(versions) + 1
                versions.append(
                    {
                        "version": version,
                        "graph": deepcopy(graph),
                        "assumptions": deepcopy(assumptions or {}),
                        "notes": notes,
                        "created_at": now,
                    }
                )
                item["versions"] = versions
                item["name"] = name or item["name"]
                item["updated_at"] = now
                item["latest_version"] = version
                return {"status": "available", "strategy": deepcopy(item)}

            sid = strategy_id or str(uuid4())
            item = {
                "id": sid,
                "owner_id": str(user_id),
                "name": name or "Untitled strategy",
                "published": False,
                "shared": False,
                "created_at": now,
                "updated_at": now,
                "latest_version": 1,
                "versions": [
                    {
                        "version": 1,
                        "graph": deepcopy(graph),
                        "assumptions": deepcopy(assumptions or {}),
                        "notes": notes,
                        "created_at": now,
                    }
                ],
                "clone_of": None,
            }
            self._items[sid] = item
            return {"status": "available", "strategy": deepcopy(item)}

    def list_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            favs = self._favorites.get(str(user_id), set())
            out = []
            for item in self._items.values():
                visible = str(item["owner_id"]) == str(user_id) or item.get("published")
                if not visible:
                    continue
                row = {
                    "id": item["id"],
                    "name": item["name"],
                    "owner_id": item["owner_id"],
                    "published": item.get("published", False),
                    "shared": item.get("shared", False),
                    "latest_version": item.get("latest_version"),
                    "updated_at": item.get("updated_at"),
                    "favorite": item["id"] in favs,
                    "clone_of": item.get("clone_of"),
                }
                out.append(row)
            out.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
            return out

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(strategy_id)
            return deepcopy(item) if item else None

    def compare(self, a_id: str, b_id: str) -> dict[str, Any]:
        a = self.get(a_id)
        b = self.get(b_id)
        if not a or not b:
            return {
                "status": "unavailable",
                "reason": "One or both strategies not found",
            }
        av = (a.get("versions") or [{}])[-1]
        bv = (b.get("versions") or [{}])[-1]
        return {
            "status": "available",
            "a": {
                "id": a["id"],
                "name": a["name"],
                "version": av.get("version"),
                "assumptions": av.get("assumptions"),
            },
            "b": {
                "id": b["id"],
                "name": b["name"],
                "version": bv.get("version"),
                "assumptions": bv.get("assumptions"),
            },
            "diff_keys": sorted(
                set(dict(av.get("assumptions") or {}))
                | set(dict(bv.get("assumptions") or {}))
            ),
        }

    def clone(self, *, user_id: UUID, strategy_id: str) -> dict[str, Any]:
        src = self.get(strategy_id)
        if not src:
            return {"status": "unavailable", "reason": "Strategy not found"}
        if not (src.get("published") or str(src["owner_id"]) == str(user_id)):
            return {"status": "forbidden", "reason": "Strategy not shareable"}
        latest = (src.get("versions") or [{}])[-1]
        result = self.save(
            user_id=user_id,
            name=f"{src['name']} (clone)",
            graph=dict(latest.get("graph") or {}),
            assumptions=dict(latest.get("assumptions") or {}),
            notes=f"Cloned from {src['id']}",
        )
        if result.get("status") == "available":
            with self._lock:
                sid = result["strategy"]["id"]
                self._items[sid]["clone_of"] = src["id"]
                result["strategy"] = deepcopy(self._items[sid])
        return result

    def publish(
        self, *, user_id: UUID, strategy_id: str, published: bool = True
    ) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(strategy_id)
            if not item:
                return {"status": "unavailable", "reason": "Strategy not found"}
            if str(item["owner_id"]) != str(user_id):
                return {"status": "forbidden", "reason": "Not owner"}
            item["published"] = published
            item["shared"] = published
            item["updated_at"] = datetime.now(UTC).isoformat()
            return {"status": "available", "strategy": deepcopy(item)}

    def favorite(
        self, *, user_id: UUID, strategy_id: str, favorited: bool = True
    ) -> dict[str, Any]:
        with self._lock:
            if strategy_id not in self._items:
                return {"status": "unavailable", "reason": "Strategy not found"}
            favs = self._favorites.setdefault(str(user_id), set())
            if favorited:
                favs.add(strategy_id)
            else:
                favs.discard(strategy_id)
            return {
                "status": "available",
                "strategy_id": strategy_id,
                "favorite": favorited,
            }


_STORE = StrategyMarketplaceStore()


def get_marketplace_store() -> StrategyMarketplaceStore:
    return _STORE
