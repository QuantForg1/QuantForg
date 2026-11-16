from __future__ import annotations

from core.utils import request_trace


def test_trace_summary_groups_by_kind() -> None:
    tok = request_trace.start()
    try:
        request_trace.record("gateway", "GET /account", 900.0)
        request_trace.record("gateway", "GET /positions", 400.0)
        request_trace.record("postgres", "q", 12.0)
        out = request_trace.summary()
    finally:
        request_trace.reset(tok)
    assert out["by_kind"]["gateway"] == {"n": 2, "ms": 1300.0}
    assert out["slowest"][0] == "gateway:GET /account 900ms"


def test_record_without_trace_is_a_noop() -> None:
    request_trace.record("gateway", "x", 1.0)
    assert request_trace.summary() == {"by_kind": {}, "slowest": []}
