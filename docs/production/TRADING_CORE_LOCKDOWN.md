# QuantForg Trading Core — Production Lockdown

**Status:** LOCKED  
**Date:** 2026-08-04  
**Tag baseline:** continuous LIVE proven (`ORDER ACCEPTED` → PME → BE → PARTIAL → TRAIL → close → next fill)

## Architecture (frozen)

```
Scheduler (ITE runtime)
  → Multi-symbol scanner
  → AI Decision / Scalping / Alpha path
  → Risk Engine + Portfolio gates
  → Execution Bridge
  → OMS
  → MT5 Gateway
  → Broker (Weltrade)
  → ORDER ACCEPTED
  → PME (BE → Partial → Trail → Close)
  → Position Recovery / MT5 truth sync
  → Next opportunity
```

## Execution pipeline

1. **Scheduler Tick** — `InstitutionalIteRuntime.run_forever`
2. **Scanning Symbols** — multi-asset scanner + close-only router
3. **AI Decision** — quality / confluence / MTF / adaptive thresholds
4. **Risk** — sizing, daily/weekly/monthly loss, drawdown, margin
5. **OMS Submit** — guarded port + transient retry
6. **Gateway `order_send`** — Cloudflare tunnel → MT5 terminal
7. **ORDER ACCEPTED** — retcode 10009 path
8. **PME** — break-even → partial (or min-lot advance) → ATR trail → exit
9. **Recovery** — restart-safe re-attach from `/positions`

## OMS

- Submit: `GuardedOmsSubmitPort` + `RetryingOmsSubmitPort`
- Manage: `GuardedOmsManagePort` (SLTP / partial / close)
- Kill switch / daily-loss flags on control plane halt OMS

## Gateway

- Client: `GatewayMT5Client` (`app/infrastructure/brokers/mt5/gateway_client.py`)
- Adapter: `MT5Adapter`
- Auth: caller token headers; health `/health`
- Verbose candle/quote HTTP logs are debug; trade paths remain info/warning

## PME

- Scalping knobs via `pme_config_for_scalping` (BE@0.5R, partial@1.0R, trail)
- Lifecycle: OPEN → BE_MOVED → PARTIAL → TRAILING → EXITED
- Min-lot: partial may advance lifecycle without volume cut
- Broker BE already on: recovery reconstructs 1R and marks `BE_MOVED`

## Risk Engine

- Hard max / micro min-lot path for small equity
- Daily / weekly / monthly / drawdown / margin / invalid stops & volume
- `FORCE_FIRST_TRADE` and `ALLOW_RISK_LOCK_OVERRIDE` **permanently disabled**

## Recovery

- `recover_positions_from_mt5` + `force_sync_positions`
- Account open count = **all** MT5 tickets (multi-symbol)
- Symbol-scoped repair never drops other symbols’ tickets
- Missing tickets → `Position Closed` log

## Deployment (Railway)

- Service: QuantForg (auto-deploy from `main`)
- `APP_ENV=production`, `EXECUTION_ENABLED=true`
- Requires gateway URL + caller token

## Environment variables (critical)

| Variable | Production expectation |
|----------|------------------------|
| `APP_ENV` | `production` |
| `EXECUTION_ENABLED` | `true` |
| `MT5_GATEWAY_BASE_URL` | set |
| `MT5_GATEWAY_CALLER_TOKEN` | set |
| `FORCE_FIRST_TRADE` | `false` (ignored if true) |
| `ALLOW_RISK_LOCK_OVERRIDE` | `false` (ignored if true) |
| `PRODUCTION_VALIDATION_MODE` | `false` in live |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No `order_send` | Risk reject, exposure limit, safety plane, EXEC off |
| PME noop | Wrong mid / risk_distance; recovery register errors |
| `MT5 positions: 0` while open | Old bug; account count must include all symbols |
| Index `503` | Broker does not expose NAS100/US30/GER40 — external |
| After restart, unmanaged fill | Watch `PME recovered position` / `BREAK_EVEN` |

## Freeze policy

See `.cursor/rules/quantforg-trading-core-freeze.mdc`.  
Regression gate: `pytest -m trading_core`.

## Post-deploy runtime checklist

Run `scripts/verify-trading-core-runtime.sh` (or PowerShell equivalent) and confirm:

- Gateway Connected  
- MT5 Connected  
- OMS Healthy  
- PME Healthy  
- Scheduler Running  
- Auto Trading Running  
- Continuous Trading Active  
