"""Physical/logical execution wall for market-universe research.

Shadow / research code must not import OMS, gateway_client, or order_send.
ALLOW_LIVE_PROMOTION remains False.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION

FORBIDDEN_IMPORT_FRAGMENTS = (
    "gateway_client",
    "institutional_oms",
    "institutional_ite_runtime",
    "force_first_trade",
)
FORBIDDEN_NAMES = (
    "order_send",
    "submit_order",
    "place_order",
    "FORCE_FIRST_TRADE",
)

PACKAGE_ROOT = Path(__file__).resolve().parent


class ResearchExecutionBlocked(RuntimeError):
    """Raised if research code is asked to execute."""


def submit_order(*_args: Any, **_kwargs: Any) -> None:
    raise ResearchExecutionBlocked("MARKET_UNIVERSE_CANNOT_SEND_ORDERS")


def promote_live(*_args: Any, **_kwargs: Any) -> None:
    raise ResearchExecutionBlocked("ALLOW_LIVE_PROMOTION is false")


def scan_package_isolation(root: Path | None = None) -> dict[str, Any]:
    """AST-scan the market_universe package for execution imports/calls."""
    base = root or PACKAGE_ROOT
    hits: list[dict[str, str]] = []
    files = list(base.glob("*.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            hits.append({"file": path.name, "issue": f"syntax: {exc}"})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if any(frag in name for frag in FORBIDDEN_IMPORT_FRAGMENTS):
                        hits.append({"file": path.name, "issue": f"import {name}"})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(frag in mod for frag in FORBIDDEN_IMPORT_FRAGMENTS):
                    hits.append({"file": path.name, "issue": f"from {mod} import ..."})
            elif isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in FORBIDDEN_NAMES and path.name != "shadow_wall.py":
                    hits.append({"file": path.name, "issue": f"call {name}()"})
    return {
        "isolated": not hits,
        "hits": hits,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "package": str(base),
        "files_scanned": len(files),
    }
