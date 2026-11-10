# Phase 5.1 — Eligibility production acceptance

**Status:** Acceptance evidence captured; merge/deploy verification follows PR.  
**Baseline API SHA at start:** `a3d4e531`  
**Gates:** `MULTI_ACCOUNT_DISPATCH_ENABLED=false`, `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`

## Matrix (automated)

| Case | Expected | Result | Evidence label |
|---|---|---|---|
| A Eligible + readiness | ELIGIBLE dry-run | PASS | Automated test verified |
| B Over-ceiling prefs | BLOCKED | PASS | Automated test verified |
| C Inactive account | BLOCKED | PASS | Automated test verified |
| D Worker unavailable / stale | BLOCKED | PASS | Automated test verified |
| E Foreign user | AuthorizationError | PASS | Automated test verified |
| F Missing prefs / storage error | BLOCKED fail-closed | PASS | Automated test verified |
| G Duplicate account claim | ConflictError (registry) | PASS | Automated test verified (+ Phase 1a indexes) |
| H Concurrent users | No cross-leak | PASS | Automated test verified (ThreadPool) |

Suite: `tests/unit/test_phase51_eligibility_matrix.py` (+ Phase 5 / Phase 1 companions).

## Production dry-run (read-only)

**Label: Production verified** (inventory + flags only; not execution-ready claims).

Probe: `.tmp-phase3b/phase51_prod_probe.py` via `railway run` against Production Postgres (SELECT only).

| Check | Value |
|---|---|
| `dispatch_allowed` | `false` |
| `live_submit_allowed` | `false` |
| `user_risk_settings` | n=1, active=1 |
| Active P7 preference | `planned_risk_pct=10.0000`, `source=user_edit` |
| Broker accounts | active=1, revoked=2 |
| `execution_workers` rows | **0** (table present; no assigned workers) |
| Readiness claim | Account registered ≠ worker assigned ≠ terminal authenticated ≠ execution-ready |

Railway `/api/v1/version` SHA: `a3d4e531a83e` (pre-merge baseline).  
`/health/live` 200 · `/health/ready` 200.  
Vercel `www.quantforg.com`: `dpl_D8C4PtKruoMe6EB1w6MCUJDMfaJu` READY.

### Dry-run execution boundary

Eligibility + Phase 6 `plan_signal_dispatch` do **not** invoke dispatcher LIVE paths, OMS submit, or MT5 `order_send`. Phase 6 dry-run forces `live_submit_allowed=False` and `delivery_suppressed=True` on every item.

Full Production eligibility ELIGIBLE classification with real worker readiness was **not** claimed: no Production `execution_workers` rows exist to inject as ready.

## Phase 4.1 live blockers (unchanged)

- P7 logout/login persistence: **BLOCKED** (authorized session credentials unavailable)
- Ordinary customer Owner denial (live session): **BLOCKED** (non-owner session unavailable)
- Automated Owner-gate tests: pass separately (`test_phase41_owner_policy_denial.py`, `test_owner_control_plane.py`)

## Security (automated + prior Production probes)

- Own-account evaluation enforced via `assert_own_user`
- Foreign account evaluation denied without disclosing foreign prefs
- Global Owner ceilings always win in `resolve_effective_risk`
- No passwords / sealed credentials in eligibility or dispatch plan payloads (unit-asserted)

## Local / CI regression evidence

| Check | Result | Label |
|---|---|---|
| Phase 5.1 / 5 / 6 + Phase 4.1 / foundation / worker / adapter / trading-core unit set | 115 passed | Locally verified |
| `pytest -m trading_core` | 2186 passed, 3 xfailed | Locally verified |
| Ruff (touched modules) | clean | Locally verified |
| `tsc --noEmit` | exit 0 | Locally verified |
| ESLint | 0 errors (pre-existing warnings) | Locally verified |
| Frontend production build | **ENOSPC** on local disk | Blocked locally — CI must verify |

## Final Phase 5.1 status

**ACCEPTED for dry-run eligibility + readiness matrix** with Production inventory confirmation that multi-account LIVE remains disabled and no workers are assigned for fan-out.
