# Production Hardening v6

Institutional reliability for continuous live trading. **No experimental trading features. No architecture rewrite.**

## Scope

| Area | Behaviour |
|------|-----------|
| Execution lifecycle | Timestamped stages: Signal → AI Decision → Risk → OMS → MT5 Gateway → Broker → Confirmation → Position Monitor → Exit |
| Smart retry | Exponential backoff for requote / busy / timeout / gateway delay only |
| Never retry | Invalid volume, invalid stops, insufficient margin, market closed |
| Health | Healthy / Warning / Offline for Gateway, Broker, OMS, Auto Trading, AI, Market Data, DB, Railway |
| Live performance | Submits, fills, rejects, retries, latency, slippage, spread, win rate, PnL windows |
| Explainability | Permanent why-* records per fill |
| Incidents | Burst rejects, disconnect, reconnect loops, high latency/slippage, DB / position sync |
| Position recovery | On Railway restart: reload MT5 positions, restore BE / partial / trail flags, no duplicate tickets |
| Backtest vs live | Per-strategy deltas + material deviation flags |
| Learning | Gradual Opportunity Score weight multipliers — base rules preserved |
| Secrets audit | Env **names** only — never values in logs or UI |

## Package

`app/domain/institutional_trading/production_hardening/`

- `retry.py` — `RetryingOmsSubmitPort` wraps Guarded OMS
- `lifecycle.py` — JSONL timeline
- `performance.py` — live counters
- `explainability.py` — permanent trade explanations
- `incidents.py` — automatic alerts into ReliabilityPlatform
- `position_recovery.py` — PME cold-start restore
- `learning.py` — weight multipliers
- `backtest_live.py` — comparison store
- `secrets_audit.py` — name-only audit
- `observe.py` — runtime hooks

## Wiring

1. `build_ite_runtime()` wraps Guarded submit with `RetryingOmsSubmitPort`
2. `InstitutionalIteRuntime._run_cycle` records lifecycle + explainability + performance
3. PME state persisted each manage tick; recovery on container startup
4. Alpha `score_opportunity` applies learning multipliers

## API / UI

- `GET /ite/reliability/production-hardening` — full production dashboard payload
- Desk: `/production-reliability` (OWNER/ADMIN)

## Tests

`tests/unit/test_production_hardening_v6.py` — retry classify, lifecycle, recovery no-dupe, learning bounds, secrets never leak values, dashboard shape.

## Operator notes

- Retries are transparent to the Execution Bridge (OMS port wrapper).
- Permanent rejects fail once — no silent loops.
- Kill switch / risk plane behaviour unchanged.
