"""16 Nov 2026: after each deploy the API stopped answering (even /health/live)
for ~3 minutes and sign-in took up to 104 s, because three startup recovery
steps read broker history synchronously inside the async orchestrator."""

from __future__ import annotations

import inspect

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
)


def test_startup_recovery_runs_off_the_event_loop() -> None:
    raw = inspect.getsource(InstitutionalIteRuntime.run_forever)
    src = " ".join(raw.replace("(", "( ").replace(",", ", ").split())
    src = src.replace("( ", "(").replace(" )", ")")
    for fn in (
        "recover_buy_cascade_on_startup",
        "recover_sell_cascade_on_startup",
        "recover_strategy_attribution_on_startup",
    ):
        assert f"await asyncio.to_thread({fn}, self.mt5_adapter" in src
        assert f"{fn}(self.mt5_adapter)" not in src
