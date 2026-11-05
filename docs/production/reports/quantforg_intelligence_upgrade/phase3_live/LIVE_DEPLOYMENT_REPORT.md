# LIVE deployment report

## Pre-deploy baseline

| Item | Value |
|---|---|
| Attribution repair merge | `a4c2e878` (PR #153) |
| Prior Railway deploy | `9cc9afbb` |
| Mode | LIVE |
| Instrument | XAUUSD / Weltrade MT5 |

## This change

| Item | Value |
|---|---|
| PR | [#154](https://github.com/QuantForg1/QuantForg/pull/154) |
| Merge commit | `52b23732` |
| SOE | `soe-v1.5.0` |
| Shadow / Canary | **Not used** (owner directive) |

## Deployed

| Item | Value |
|---|---|
| Railway deployment | `1b0ad18a` **SUCCESS** |
| Commit on deploy | `52b23732` |
| Mode | **LIVE** (`ite_runtime_mode_not_shadow`) |
| Auto-resume | `ROBOT AUTO-RESUMED` — new entries allowed; equity ~15.52 |
| Scheduler | `mode=LIVE` `run_state=running` |
| Gateway | Connected; Weltrade-Real session adopted |
| Strategies | `strategies_evaluated=5`; prefer-no-trade when no passer |
| Real-money test orders | **Not placed** |

## Verification checklist

- [x] Deployed commit SHA matches merge
- [x] LIVE mode active (not canary/shadow)
- [x] Worker + scheduler running
- [x] MT5 gateway connected
- [x] Five strategies evaluate
- [x] Risk / OMS still gate (Execution Gate FAIL when no eligible — expected)
- [ ] Forward close attribution log on next broker SL/TP
- [ ] Ops monitor shows `orchestration_version=soe-v1.5.0` on next snapshot

## Owner risk recalculation

Equity ~$15.52 → 20% per-trade ceiling ~$3.10. Minimum lot 0.01 can still violate ceiling on wide SL → preserve `OWNER_SL_RISK` rejection. No lot/risk increase shipped.
