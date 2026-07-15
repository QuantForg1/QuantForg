# Closed Beta Go / No-Go Certificate

**Product:** QuantForg  
**Stage:** Closed Beta (invite-only)  
**Date:** 2026-07-15  
**Baseline SHA:** `9074a00294272a35759fa106fd58e2365afbc238`

## Decision

# GO — Closed Beta (conditional)

**NO GO** for unsupervised live trading and public GA until Major items in `CLOSED_BETA_PRODUCTION_AUDIT.md` are mitigated.

## Conditions

1. `EXECUTION_ENABLED=false` in production.  
2. Beta invite + maintenance/read-only flags operable.  
3. Broker passwords never in Railway/browser.  
4. `/ops` monitored; feedback channel live.  
5. Paper-first onboarding enforced in communications.  
6. What’s New updated for this build when invites ship.

## Evidence package

| Artifact | Path |
|----------|------|
| Production audit | `CLOSED_BETA_PRODUCTION_AUDIT.md` |
| Beta kit | `CLOSED_BETA_KIT.md` |
| Monitoring prep | `CLOSED_BETA_MONITORING.md` |
| Onboarding / ops | `BETA_*.md` |

## Sign-off

| Role | Stance |
|------|--------|
| Release Engineering | GO conditional |
| QA | GO conditional (E2E 21/21 on prior release gate; unit 444) |
| Security | GO conditional (Major: localStorage tokens, in-process RL) |
| SRE / Ops | GO conditional (operator drills + `/ops`) |
| Product | GO conditional (paper + research cohort) |
