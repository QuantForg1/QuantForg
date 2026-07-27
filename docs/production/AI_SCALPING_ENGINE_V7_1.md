# Institutional AI Scalping Engine v7.1 — Continuous Autonomous Operation

Uses **v7** as the multi-asset baseline. Quality floors and risk knobs remain
locked to **v6.3**.

## Architecture changes

Additive continuous-operation controller on top of existing:

- HeartbeatRegistry
- RecoveryOrchestrator (gateway/MT5/safe-read — never order_send retry)
- AutomaticReconnectManager
- Encrypted broker credentials (AES-256-GCM)
- Decision-hash restart continuity
- PME position recovery from MT5

New modules:

- `continuous_operation.py` — heal deps, pause NEW entries only, post-close rescan
- `broker_profile_store.py` — persist broker/server/login/terminal_path (+ encrypted password)

## Autonomous scalping

- `max_open_trades = 5` (configurable)
- Portfolio exposure (`max_daily_exposure_pct = 2.00`) and daily loss still bind
- Additional entries only when quality + cooldown + health + portfolio allow

## Login persistence

Frontend Remember Me:

- checked → localStorage (survive refresh/restart)
- unchecked → sessionStorage (tab lifetime)
- Refresh token flow unchanged

## Database migrations

**None required** — uses existing `broker_credentials` / sessions tables plus
encrypted local profile file under `data/`.

## Tests

`tests/unit/test_ai_scalping_v7_1_continuous.py`
