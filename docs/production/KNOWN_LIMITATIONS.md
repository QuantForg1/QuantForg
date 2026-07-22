# QuantForg v1.0.0 — Known Limitations

1. **Multi-day soak:** Accelerated profiles (`stress` / `24h` / `72h` cycle counts) are not wall-clock proof. Operators must run `--wall-seconds` for 86400 / 259200 / 604800 on a dedicated host and retain reports under `docs/production/reports/`.

2. **DurableResearchStore:** Append-only research / IVP / LLP / RMIP / PRC archives are process-local unless exported (`scripts/backup_production_state.py` from a process that holds the data, or Postgres-backed audits).

3. **Execution default:** `EXECUTION_ENABLED=false`. Live `order_send` requires explicit enablement after Demo certification.

4. **Candle history:** API may filter large windows (≤5000 bars) — medium residual.

5. **Calendar / news:** Empty when feeds unconfigured — never fabricated.

6. **Reconnect counts:** Services-health currently reports probe snapshot reconnect_count as `0` unless extended by reliability timeline; use reliability incidents + soak reports for reconnect trends.

7. **Controlled live:** Release readiness is for controlled / canary deployment — not an unrestricted volume claim without completed wall-clock soaks and OWNER sign-off.
