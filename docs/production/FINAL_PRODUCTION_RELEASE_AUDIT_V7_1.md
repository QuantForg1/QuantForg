# QuantForg Final Production Release Audit — v7.1

Generated: 2026-07-27T19:10Z (approx)  
Updated: 2026-07-27 (trading critical-path hardening follow-up)

## Verdict

**STOP — production release blocked.**

Do **not** commit or push a production release to `main` while verified blockers remain.

## Step 1 — Full audit (blockers)

### Verified operational blockers (release-blocking)

| # | Blocker | Area | Evidence |
|---|---|---|---|
| 1 | Elevated MT5 Gateway process cannot be recycled by ops agent (`Access denied` on taskkill / schtasks) | Gateway / ops | OAT Step 1 & 3 FAIL — `docs/production/V7_1_LIVE_OPERATIONAL_ACCEPTANCE_TEST.md` |
| 2 | Full FE/BE/Gateway/MT5 restart cycle not proven | Deploy / continuity | OAT Step 1 FAIL |
| 3 | Operator browser + PC restart session restore not proven | Auth / broker persistence | OAT Step 4 FAIL (agent browser showed `/login`) |
| 4 | 24-hour continuous soak incomplete | Reliability | OAT Step 5 BLOCKED — soak logger started; 24h not elapsed |

### Code blockers found by trading critical-path audit — fixed in working tree (not released)

| # | Blocker | Fix |
|---|---|---|
| A | `AccountRiskState` falsified peak/daily/open book | `ite_cycle_market_context.py` resolves peak/daily via tracker + history deals; populates open directions/entries |
| B | Continuous-ops hardcoded `oms_ok`/`market_open`/`portfolio_risk` | Live probes; probe exceptions **fail closed** |
| C | Bridge hardcoded `daily_loss_exceeded=False` / `emergency_stop=False` | Wired from plane + account daily PnL; latches `flag_daily_loss()` |
| D | Fail-open exception handlers (portfolio / live-health / pause) | Fail closed (block / abort / demote to NO_TRADE) |
| E | Stale-heartbeat pause dead after `publish_heartbeats()` | `tick()` only refreshes healthy deps; reports failed deps as missing heartbeats |
| F | MT5 heal returned True after `attach` without verifying connection | Verify `client.is_connected` after attach |
| G | Weltrade reconnect fell through to `login=1` | Refuse reconnect without live session or persisted profile |
| H | Bridge live-health never updated `oms_ok` | Pass `oms_ok` from gateway connectivity |

Residual (non-blocking for this gate): `best_open_confidence` still unset in market context — add-on confidence improvement stays inactive until PME confidence is wired.

### Non-blocking / monitored

- Railway `/health` intermittent timeout in soak sample (later direct probe ok)
- Local FE/BE ports not required when using `www.quantforg.com` + Railway
- Gateway + MT5 currently healthy (Weltrade-Real attached, heartbeat live)
- Auth session wipe on 5xx/network fixed in working tree (`auth-provider.tsx`)

### Explicit: no blockers found for

- Martingale / grid (disabled in config)
- Quality floor downgrade (locked to v6.3 baseline)
- Plain-text broker password in profile store (AES ciphertext only)

## Step 2 — Fixes applied (working tree only)

Trading / continuous-ops / reconnect fail-closed hardening as above.

No strategy, risk ceiling, or quality-gate loosening.

## Step 3 — Database

RLS migration present in tree (not applied as release prerequisite here):

- `supabase/migrations/20260727190000_live_account_risk_state_rls.sql`

Apply when targeting Supabase live risk state; not a substitute for OAT operational PASS.

## Step 4 — Validation (this pass)

- Re-run targeted unit suites after hardening (continuous, weltrade reconnect, market context, bridge-related)
- Full CI matrix / frontend typecheck / integration suite: not claimed complete in this STOP gate

## Step 5 — Production readiness

| Item | Status |
|---|---|
| Files changed (unreleased) | ITE runtime, market context, decision pipeline, bridge, continuous_operation, weltrade reconnect, auth-provider, RLS migration, tests, this audit |
| Migrations executed in prod | Not claimed |
| Blockers remaining | **4 operational OAT** (gateway elevate recycle, full restart proof, browser/PC session, 24h soak) |
| Production readiness | **NOT READY for final release commit** |

## Step 6 — Release

**Not executed** (git commit/push to `main` withheld per rule: any blocker → STOP).

## Operator actions required before release

1. Admin recycle of elevated gateway on Windows host; confirm auto-attach + heartbeat
2. Prove FE/Railway recycle without duplicate workers/orders
3. Real browser profile: refresh / reopen / PC restart with Remember Me + broker restore
4. Complete 24h soak; review `docs/production/reports/oat_v71/soak_24h_metrics.jsonl`
5. Re-run PAT/OAT until all PASS, then re-attempt Step 6 release
