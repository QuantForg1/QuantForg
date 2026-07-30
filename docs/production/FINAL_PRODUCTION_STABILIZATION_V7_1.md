# QuantForg Final Production Stabilization — v7.1

Generated: 2026-07-30T11:30Z (approx)

## Verdict

**STOP — production release to `main` blocked.**

Software fail-open defects found in audit were fixed on branch
`cursor/v7-1-production-stabilization-bc83`. Live PAT/OAT acceptance remains
**NOT ACCEPTED**. Do not commit or push Outcome A release to `main`.

## Software defects fixed this pass

| # | Defect | Fix |
|---|---|---|
| 1 | Daily PnL fail-open when `history_deals` unavailable (treated as 0) | Fail closed: trip daily-loss gate until deals readable; never invent flat PnL |
| 2 | Add-on/duplicate guard fail-open when book facts missing with open positions | Mark incomplete; decision pipeline blocks add-ons |
| 3 | OMS retry mutated `request_id` + retried TIMEOUT/CONNECTION | Preserve `request_id`; remove ambiguous retcodes from auto-retry |
| 4 | Bridge `risk_allowed=True` ignored decision risk checks | Bridge context uses `decision.eligibility.checks["risk_available"]` |
| 5 | Unknown MT5 AutoTrading / broker-restriction defaults to tradable | Fail closed for AutoTrading unknown; derive restrictions from account flags |
| 6 | Reliability heartbeats always refreshed as healthy | Publish only for currently healthy probe components |
| 7 | Continuous-ops tick exception left pause unset | Fail-closed pause snapshot on tick failure |
| 8 | Attach persisted synthetic `login=1` | Prefer account_info login; store 0 when untrusted |

No strategy, risk ceiling, quality-gate, or forced-entry changes.

## Database

**No migration required** for this stabilization pass.

(Prior optional RLS migration `20260727190000_live_account_risk_state_rls.sql`
remains in tree; not a substitute for OAT PASS and not required by these code fixes.)

## Validation (this environment)

| Gate | Result |
|---|---|
| Unit tests (`pytest -m unit`) | **1042 passed** |
| Integration (`pytest -m integration`) | **106 passed**, 2 skipped (need `RUN_INTEGRATION=1`) |
| Regression marker | No tests selected under `-m regression` |
| Ruff (changed modules) | Clean aside from pre-existing long import lines |
| MyPy (changed risk/retry/adapter modules) | Clean |
| Production FE `www.quantforg.com` | HTTP 200 |
| PAT / OAT | Still **NOT ACCEPTED** (see below) |

## Remaining release blockers (evidence)

### PAT — NOT ACCEPTED

`docs/production/reports/v7_1_pat_latest.json`:

- `production_accepted`: false
- Summary: PASS 4 · FAIL 0 · **BLOCKED 6**
- Declaration: reconnect soak, 24h run, browser/PC restart still BLOCKED

### OAT — NOT ACCEPTED

`docs/production/V7_1_LIVE_OPERATIONAL_ACCEPTANCE_TEST.md`:

1. Full FE/BE/Gateway/MT5 restart — **FAIL** (elevated gateway Access denied)
2. MT5 session reconnect — **PASS**
3. Gateway process restart — **FAIL** (elevated process)
4. Browser / PC restart session restore — **FAIL**
5. 24h soak — **incomplete** (metrics ~16h wall: 2026-07-27T18:35Z → 2026-07-28T10:45Z)

### Ops environment limits (this agent)

- Cannot recycle elevated Windows MT5 Gateway (`Access denied`)
- Cannot complete operator browser Remember-Me / PC restart proof
- Cannot start production trading workers against live MT5 from this cloud pod
  without gateway credentials / Windows host access
- Do **not** force entries

## Release rule

Per operator instruction: release commit/push to `main` only if PAT=ACCEPTED,
OAT=ACCEPTED, production validation PASS, and no blockers remain.

**Those conditions are not met → STOP. No `main` commit/push.**
