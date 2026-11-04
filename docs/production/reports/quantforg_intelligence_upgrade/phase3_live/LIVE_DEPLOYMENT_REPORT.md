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
| Branch | `feat/phase3-live-intelligence` |
| SOE | `soe-v1.5.0` |
| Shadow / Canary | **Not used** (owner directive) |

## Required post-merge checks

1. CI green (unit, trading_core, lint).
2. Railway worker/scheduler redeploy; confirm commit SHA.
3. Vercel only if frontend touched (this PR: backend/strategy — typically Railway).
4. Verify LIVE Enabled; MT5 gateway connected; five strategies evaluate; Risk/OMS active.
5. **Do not** place real-money test orders.

## Verification checklist (fill after deploy)

- [ ] Deployed commit SHA matches merge
- [ ] LIVE mode active (not canary/shadow)
- [ ] Worker + scheduler running
- [ ] MT5 gateway connected
- [ ] SOE version reports `soe-v1.5.0`
- [ ] Risk / OMS / OWNER_* safeguards unchanged
- [ ] Close attribution logs `broker_confirmed_close_attributed` on next broker SL/TP

## Owner risk recalculation

Equity ~$15.52 → 20% per-trade ceiling ~$3.10. Minimum lot 0.01 can still violate ceiling on wide SL → preserve `OWNER_SL_RISK` rejection. No lot/risk increase shipped.
