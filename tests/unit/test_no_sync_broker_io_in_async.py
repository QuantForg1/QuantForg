"""Guard: async code must not call the sync MT5 gateway client directly.

16 Nov 2026: such calls blocked the event loop for 30-45 s whenever the
gateway was slow, so /health/live, sign-in and every page stalled together.
Use ``await run_broker_read(fn)`` (request paths) or ``asyncio.to_thread``.
"""

from __future__ import annotations

import ast
import pathlib

SYNC_GATEWAY_CALLS = {
    "history_deals",
    "history_orders",
    "load_history_deals_safe",
    "account_info",
    "account_snapshot",
    "list_positions",
    "list_orders",
    "gateway_health",
    "force_sync_positions",
    "list_symbols",
    "latest_tick",
    "symbol_info",
    "health",
    "_protect_open_positions",
    "_manage_open_positions_after_timeout",
    "_ensure_process_gateway_handle",
    "validate_order",
    "note_scheduler_stalled",
    "attach",
}
RECEIVERS = (
    "self.validation_service",
    "self.market_data",
    "self",
    "self.adapter",
    "self._client",
    "self.portfolio_sync",
    "gw",
    "self.mt5_adapter",
)


class _Finder(ast.NodeVisitor):
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.stack: list[bool] = []
        self.hits: list[str] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append(True)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(False)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.stack.append(False)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        if (
            self.stack
            and self.stack[-1]
            and isinstance(f, ast.Attribute)
            and f.attr in SYNC_GATEWAY_CALLS
            and ast.unparse(f.value) in RECEIVERS
        ):
            self.hits.append(f"{self.path}:{node.lineno} {ast.unparse(f)}()")
        self.generic_visit(node)


def test_no_direct_sync_gateway_calls_in_async_functions() -> None:
    hits: list[str] = []
    for path in pathlib.Path("app").rglob("*.py"):
        finder = _Finder(path)
        finder.visit(ast.parse(path.read_text(encoding="utf-8")))
        hits.extend(finder.hits)
    assert hits == [], "sync gateway I/O on the event loop:\n" + "\n".join(hits)
