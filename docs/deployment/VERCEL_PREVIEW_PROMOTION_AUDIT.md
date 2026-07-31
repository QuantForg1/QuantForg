# Vercel Preview Deployment Audit

**Date:** 2026-07-31 18:20 UTC
**Source:** GitHub Deployments API (`environment=Preview` / `Production`) created by `vercel[bot]`
**Note:** Vercel MCP/CLI token unavailable in this agent; audit uses GitHub deployment records + git ancestry.

## Production baseline

| Field | Value |
|---|---|
| Current Production SHA | `df16aecbe2cb3a9758893380cec56895c47b43a1` |
| `origin/main` SHA | `df16aecbe2cb3a9758893380cec56895c47b43a1` |
| Match | **Yes** (Production tip == main tip) |
| Promote action taken | **None** |

## Policy applied

1. Never promote an older Preview over newer Production.
2. Only promote if Preview is newer **and** all changes are approved.
3. If multiple Previews contain different unique work, **stop and report** — do not promote one-by-one.
4. No sequential Promote-to-Production of Previews.

## Summary

- Preview deployments audited: **119**
- Unique commit SHAs: **119**
- Older than Production (Skipped): **67**
- Identical to Production: **0**
- Diverged / unique work (STOP — report only): **32**
- Unknown SHA (not in clone): **20**
- **Promoted: 0**

## Decision

**No Preview deployments were promoted.**

Multiple Previews contain **different unique work not on `origin/main`** (AI/scoring drafts, MT5 drafts, STOP docs, Dependabot). Per rule 5, promotion is halted and those SHAs are reported below.

All Previews that are ancestors of Production were **Skipped** to avoid rollback.

## Unique work not on origin/main (STOP set)

These Preview SHAs contain commits absent from `origin/main`. Do **not** promote individually.

### `0ed0828` — `cursor/ultra-aggressive-risk-profile-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686497009
- Unique commits (5):
  - `0ed0828 fix: log control-plane risk fallback failure in cycle diagnostics`
  - `2322cca fix: use active risk profile in cycle sizing diagnostics`
  - `8886cc5 fix: allow PRE v2 trades that land exactly on ULTRA exposure caps`
  - `f9f1abd style: format ULTRA_AGGRESSIVE risk profile files for CI`
  - `9e12558 feat: add ULTRA_AGGRESSIVE institutional risk profile`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `035903e` — `cursor/score-pipeline-integration-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690909642
- Unique commits (4):
  - `035903e feat(ite): Score Pipeline Integration — Liquidity v2 + M15/MTF into Q/C`
  - `14ff760 feat(ite): AI Score Calibration audit — Quality/Confidence decomposition`
  - `41e1fce feat(ite): M15 Trend Semantics v2 — pullback taxonomy + H1+M15 lock`
  - `a5c4971 feat(ite): AI Decision Engine v2 — regime MTF + liquidity context`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `2322cca` — `cursor/ultra-aggressive-risk-profile-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686470595
- Unique commits (4):
  - `2322cca fix: use active risk profile in cycle sizing diagnostics`
  - `8886cc5 fix: allow PRE v2 trades that land exactly on ULTRA exposure caps`
  - `f9f1abd style: format ULTRA_AGGRESSIVE risk profile files for CI`
  - `9e12558 feat: add ULTRA_AGGRESSIVE institutional risk profile`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `14ff760` — `cursor/ai-score-calibration-bc83, cursor/score-pipeline-integration-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690810029
- Unique commits (3):
  - `14ff760 feat(ite): AI Score Calibration audit — Quality/Confidence decomposition`
  - `41e1fce feat(ite): M15 Trend Semantics v2 — pullback taxonomy + H1+M15 lock`
  - `a5c4971 feat(ite): AI Decision Engine v2 — regime MTF + liquidity context`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `5763d63` — `cursor/production-readiness-validation-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5692059123
- Unique commits (3):
  - `5763d63 docs: FINAL_PRODUCTION_READINESS_REPORT — NOT READY (STOP)`
  - `61b2e76 docs: FINAL_GATEWAY_RECOVERY_REPORT — NOT READY (gateway 502)`
  - `d681071 docs: FINAL_RC1_INFRA_REPORT — NOT READY (gateway 502)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `6832c49` — `cursor/ai-decision-rejection-analysis-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690039898
- Unique commits (3):
  - `6832c49 fix(ite): map NO_SNAPSHOT/SAFETY in rejection family taxonomy`
  - `a93a469 chore(ops): harden rejection collectors against store races`
  - `d0a4cbf feat(ite): add AI decision rejection analysis (evidence-only)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `8886cc5` — `cursor/ultra-aggressive-risk-profile-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686415018
- Unique commits (3):
  - `8886cc5 fix: allow PRE v2 trades that land exactly on ULTRA exposure caps`
  - `f9f1abd style: format ULTRA_AGGRESSIVE risk profile files for CI`
  - `9e12558 feat: add ULTRA_AGGRESSIVE institutional risk profile`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `2facfa9` — `cursor/mt5-gateway-single-instance-fix-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5691068929
- Unique commits (2):
  - `2facfa9 fix(mt5-gateway): fail-closed single-instance gate before uvicorn bind`
  - `679f723 feat(mt5-gateway): single-instance protection for port 8765`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `41e1fce` — `cursor/ai-score-calibration-bc83, cursor/m15-trend-semantics-v2-bc83, cursor/score-pipeline-integration-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690717078
- Unique commits (2):
  - `41e1fce feat(ite): M15 Trend Semantics v2 — pullback taxonomy + H1+M15 lock`
  - `a5c4971 feat(ite): AI Decision Engine v2 — regime MTF + liquidity context`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `61b2e76` — `cursor/p0-gateway-recovery-bc83, cursor/production-readiness-validation-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5691796605
- Unique commits (2):
  - `61b2e76 docs: FINAL_GATEWAY_RECOVERY_REPORT — NOT READY (gateway 502)`
  - `d681071 docs: FINAL_RC1_INFRA_REPORT — NOT READY (gateway 502)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `a93a469` — `cursor/ai-decision-rejection-analysis-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686633542
- Unique commits (2):
  - `a93a469 chore(ops): harden rejection collectors against store races`
  - `d0a4cbf feat(ite): add AI decision rejection analysis (evidence-only)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `f9f1abd` — `cursor/ultra-aggressive-risk-profile-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686378672
- Unique commits (2):
  - `f9f1abd style: format ULTRA_AGGRESSIVE risk profile files for CI`
  - `9e12558 feat: add ULTRA_AGGRESSIVE institutional risk profile`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `1c40522` — `dependabot/pip/cryptography-49.0.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5526894420
- Unique commits (1):
  - `1c40522 build(deps): bump cryptography from 48.0.1 to 49.0.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `204ae8a` — `dependabot/pip/testcontainers-4.15.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618589826
- Unique commits (1):
  - `204ae8a build(deps-dev): bump testcontainers from 4.14.2 to 4.15.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `287651c` — `undefined`

- Relation: `diverged_unique_work`
- Deployment IDs: 5696146778
- Unique commits (1):
  - `287651c docs(deployment): full merge audit — main already consolidated`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `2a780ca` — `cursor/mtf-alignment-diagnostic-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690568887
- Unique commits (1):
  - `2a780ca feat(ite): MTF alignment diagnostic (evidence-only)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `36892df` — `dependabot/pip/ruff-0.16.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618700967
- Unique commits (1):
  - `36892df build(deps-dev): bump ruff from 0.15.21 to 0.16.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `41d2fad` — `dependabot/pip/faker-40.36.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618633984
- Unique commits (1):
  - `41d2fad build(deps-dev): bump faker from 33.3.1 to 40.36.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `679f723` — `cursor/mt5-gateway-single-instance-bc83, cursor/mt5-gateway-single-instance-fix-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690984927
- Unique commits (1):
  - `679f723 feat(mt5-gateway): single-instance protection for port 8765`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `820654c` — `dependabot/pip/pytest-9.1.1`

- Relation: `diverged_unique_work`
- Deployment IDs: 5526878632
- Unique commits (1):
  - `820654c build(deps-dev): bump pytest from 8.4.2 to 9.1.1`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `8f1b925` — `dependabot/pip/httpx2-2.9.1`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618611531
- Unique commits (1):
  - `8f1b925 build(deps): bump httpx2 from 2.5.0 to 2.9.1`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `986738a` — `dependabot/pip/pre-commit-4.6.1`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618673996
- Unique commits (1):
  - `986738a build(deps-dev): bump pre-commit from 4.6.0 to 4.6.1`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `9e12558` — `cursor/ultra-aggressive-risk-profile-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686358356
- Unique commits (1):
  - `9e12558 feat: add ULTRA_AGGRESSIVE institutional risk profile`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `a21fc67` — `dependabot/github_actions/actions/setup-python-7`

- Relation: `diverged_unique_work`
- Deployment IDs: 5518115610
- Unique commits (1):
  - `a21fc67 build(deps): Bump actions/setup-python from 6 to 7`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `a2cb460` — `dependabot/pip/mypy-2.3.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5526907880
- Unique commits (1):
  - `a2cb460 build(deps-dev): bump mypy from 2.2.0 to 2.3.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `a5c4971` — `cursor/ai-decision-engine-v2-bc83, cursor/ai-score-calibration-bc83, cursor/m15-trend-semantics-v2-bc83, cursor/score-pipeline-integration-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5690505102
- Unique commits (1):
  - `a5c4971 feat(ite): AI Decision Engine v2 — regime MTF + liquidity context`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `babea43` — `dependabot/github_actions/actions/setup-node-7`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618568028
- Unique commits (1):
  - `babea43 build(deps): bump actions/setup-node from 4 to 7`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `d0a4cbf` — `cursor/ai-decision-rejection-analysis-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5686614416
- Unique commits (1):
  - `d0a4cbf feat(ite): add AI decision rejection analysis (evidence-only)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `d2de6fd` — `dependabot/pip/fastapi-0.140.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5618655309
- Unique commits (1):
  - `d2de6fd build(deps): bump fastapi from 0.139.0 to 0.140.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `d681071` — `cursor/infra-recovery-rc1-bc83, cursor/p0-gateway-recovery-bc83, cursor/production-readiness-validation-bc83`

- Relation: `diverged_unique_work`
- Deployment IDs: 5691675450
- Unique commits (1):
  - `d681071 docs: FINAL_RC1_INFRA_REPORT — NOT READY (gateway 502)`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `fb2a413` — `dependabot/pip/asyncpg-0.31.0`

- Relation: `diverged_unique_work`
- Deployment IDs: 5526965176
- Unique commits (1):
  - `fb2a413 build(deps): bump asyncpg from 0.30.0 to 0.31.0`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

### `fd2969f` — `dependabot/docker/python-3.14-slim-bookworm`

- Relation: `diverged_unique_work`
- Deployment IDs: 5427738885
- Unique commits (1):
  - `fd2969f build(deps): Bump python from 3.13-slim-bookworm to 3.14-slim-bookworm`
- Status: **Skipped / STOP — report only**
- Reason: Unique work not present on origin/main; not an approved single Production candidate

## Full Preview inventory

| Deployment ID | Commit SHA | Branch | Relation | Status | Reason |
|---|---|---|---|---|---|
| `5696146778` | `287651c` | `undefined` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5694043153` | `550dcd5` | `cursor/full-merge-audit-bc83, cursor/owner-login-recovery-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693941536` | `f0b639c` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693914777` | `67649aa` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693797022` | `53df422` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693771513` | `4aad09b` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693710116` | `f03d464` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5693685339` | `4a5e080` | `cursor/full-merge-audit-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5692297534` | `5fd6bd8` | `cursor/full-merge-audit-bc83, cursor/owner-login-recovery-bc83, cursor/prod-readiness-fix-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5692229687` | `ebf1094` | `cursor/full-merge-audit-bc83, cursor/owner-login-recovery-bc83, cursor/prod-readiness-fix-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5692139573` | `2d3a28f` | `cursor/full-merge-audit-bc83, cursor/owner-login-recovery-bc83, cursor/prod-readiness-fix-bc83, cursor/rc4-brand-rebrand-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5692059123` | `5763d63` | `cursor/production-readiness-validation-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 3 unique commit(s) not on origin/main |
| `5691796605` | `61b2e76` | `cursor/p0-gateway-recovery-bc83, cursor/production-readiness-validation-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 2 unique commit(s) not on origin/main |
| `5691675450` | `d681071` | `cursor/infra-recovery-rc1-bc83, cursor/p0-gateway-recovery-bc83, cursor/production-readiness-validation-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5691547599` | `b431463` | `cursor/full-merge-audit-bc83, cursor/infra-recovery-rc1-bc83, cursor/owner-login-recovery-bc83, cursor/p0-gateway-recovery-bc83, cursor/prod-readiness-fix-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5691459046` | `7dfe073` | `cursor/full-merge-audit-bc83, cursor/infra-recovery-rc1-bc83, cursor/owner-login-recovery-bc83, cursor/p0-gateway-recovery-bc83, cursor/prod-readiness-fix-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5691425014` | `8d8670f` | `cursor/final-pre-live-rc1-bc83, cursor/full-merge-audit-bc83, cursor/infra-recovery-rc1-bc83, cursor/owner-login-recovery-bc83, cursor/p0-gateway-recovery-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5691395372` | `7fe9be5` | `cursor/final-pre-live-rc1-bc83, cursor/full-merge-audit-bc83, cursor/infra-recovery-rc1-bc83, cursor/owner-login-recovery-bc83, cursor/p0-gateway-recovery-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5691227411` | `e8ca6be` | `cursor/final-pre-live-rc1-bc83, cursor/full-merge-audit-bc83, cursor/infra-recovery-rc1-bc83, cursor/owner-login-recovery-bc83, cursor/p0-gateway-recovery-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5691068929` | `2facfa9` | `cursor/mt5-gateway-single-instance-fix-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 2 unique commit(s) not on origin/main |
| `5690984927` | `679f723` | `cursor/mt5-gateway-single-instance-bc83, cursor/mt5-gateway-single-instance-fix-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5690909642` | `035903e` | `cursor/score-pipeline-integration-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 4 unique commit(s) not on origin/main |
| `5690810029` | `14ff760` | `cursor/ai-score-calibration-bc83, cursor/score-pipeline-integration-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 3 unique commit(s) not on origin/main |
| `5690717078` | `41e1fce` | `cursor/ai-score-calibration-bc83, cursor/m15-trend-semantics-v2-bc83, cursor/score-pipeline-integration-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 2 unique commit(s) not on origin/main |
| `5690568887` | `2a780ca` | `cursor/mtf-alignment-diagnostic-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5690505102` | `a5c4971` | `cursor/ai-decision-engine-v2-bc83, cursor/ai-score-calibration-bc83, cursor/m15-trend-semantics-v2-bc83, cursor/score-pipeline-integration-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5690039898` | `6832c49` | `cursor/ai-decision-rejection-analysis-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 3 unique commit(s) not on origin/main |
| `5686633542` | `a93a469` | `cursor/ai-decision-rejection-analysis-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 2 unique commit(s) not on origin/main |
| `5686614416` | `d0a4cbf` | `cursor/ai-decision-rejection-analysis-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5686497009` | `0ed0828` | `cursor/ultra-aggressive-risk-profile-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 5 unique commit(s) not on origin/main |
| `5686470595` | `2322cca` | `cursor/ultra-aggressive-risk-profile-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 4 unique commit(s) not on origin/main |
| `5686415018` | `8886cc5` | `cursor/ultra-aggressive-risk-profile-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 3 unique commit(s) not on origin/main |
| `5686378672` | `f9f1abd` | `cursor/ultra-aggressive-risk-profile-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 2 unique commit(s) not on origin/main |
| `5686358356` | `9e12558` | `cursor/ultra-aggressive-risk-profile-bc83` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5686101938` | `3a4ddba` | `cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/final-pre-live-rc1-bc83, cursor/full-merge-audit-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5686024642` | `38a3f9f` | `cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/final-pre-live-rc1-bc83, cursor/full-merge-audit-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685936244` | `05d0d03` | `cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83, cursor/final-pre-live-rc1-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685731214` | `9b2e5bf` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685620002` | `8a6aeea` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685531356` | `31f6ada` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685388101` | `0424688` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685206234` | `21f9a21` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685035631` | `ed1e8ea` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5685013937` | `97d3bc4` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5684470623` | `6f5b426` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5684425201` | `d4c3787` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5684258891` | `d95b5ff` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5684208169` | `4cdacb7` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5683758789` | `d9b26bf` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5683608776` | `1dab880` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5683196541` | `d639e28` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5682805872` | `0587ead` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5682805519` | `56447b9` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5682778298` | `9e4f9ab` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5681519293` | `0335fe6` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5679875564` | `dae1a94` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5679752100` | `2daefb6` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5679456237` | `2bd96cb` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5679234249` | `c45a5e7` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5678964109` | `ded3625` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5678658335` | `974324a` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5678335792` | `b17eb69` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5678246493` | `ec3eb2d` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5677821368` | `d83003d` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5677557435` | `6126414` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5677210969` | `530e016` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676675437` | `52980ec` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676633561` | `1f2d8e2` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676555373` | `2ce703a` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676490039` | `1d71886` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676460553` | `0dc5f5a` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676413730` | `38cd895` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5676228564` | `a60715e` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5675995555` | `be4a003` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5675546428` | `d35c48b` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5675360994` | `63ca709` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5675074404` | `42f4bf7` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5675029919` | `de992f1` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674894584` | `2fc0c3e` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674839107` | `a5d6e74` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674737524` | `9837123` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674441646` | `12becf7` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674258469` | `cc0210d` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5674141834` | `24be32b` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5673936204` | `0d8834b` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5638446473` | `6addea9` | `cursor/24-7-session-soft-weight-bc83, cursor/ai-decision-engine-v2-bc83, cursor/ai-decision-rejection-analysis-bc83, cursor/ai-score-calibration-bc83, cursor/dynamic-position-sizing-v2-bc83` | `older_than_production` | **Skipped** | Commit is ancestor of Production — promoting would roll Production backward |
| `5618700967` | `36892df` | `dependabot/pip/ruff-0.16.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618673996` | `986738a` | `dependabot/pip/pre-commit-4.6.1` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618655309` | `d2de6fd` | `dependabot/pip/fastapi-0.140.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618633984` | `41d2fad` | `dependabot/pip/faker-40.36.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618611531` | `8f1b925` | `dependabot/pip/httpx2-2.9.1` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618589826` | `204ae8a` | `dependabot/pip/testcontainers-4.15.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5618568028` | `babea43` | `dependabot/github_actions/actions/setup-node-7` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5526986406` | `40485ec` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5526965176` | `fb2a413` | `dependabot/pip/asyncpg-0.31.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5526947338` | `53da695` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5526934081` | `b303533` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5526920885` | `fe75731` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5526907880` | `a2cb460` | `dependabot/pip/mypy-2.3.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5526894420` | `1c40522` | `dependabot/pip/cryptography-49.0.0` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5526878632` | `820654c` | `dependabot/pip/pytest-9.1.1` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5520744329` | `1ca0075` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518424446` | `1b9fc27` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518159499` | `b379945` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518149208` | `2b19662` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518140409` | `6b5563f` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518132709` | `f50a3c7` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518125666` | `b66f118` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5518115610` | `a21fc67` | `dependabot/github_actions/actions/setup-python-7` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5436629092` | `43ce102` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5436617745` | `ab1af1c` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5436605818` | `4557322` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5436597398` | `c7e5101` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5427738885` | `fd2969f` | `dependabot/docker/python-3.14-slim-bookworm` | `diverged_unique_work` | **STOP — report only** | Diverged from main; 1 unique commit(s) not on origin/main |
| `5420647216` | `cdc9d59` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5420640188` | `cd208cd` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5420633541` | `270d3c3` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5420627056` | `13cc7b5` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |
| `5420618013` | `72a92c4` | `unknown` | `unknown_sha` | **Skipped** | Commit not found in local clone |

## Production deployments (reference, newest first)

| Deployment ID | Commit SHA | Created |
|---|---|---|
| `5696170351` | `df16aec` | 2026-07-31T18:17:38Z |
| `5696170219` | `d4eca8c` | 2026-07-31T18:17:37Z |
| `5696170216` | `9dbe400` | 2026-07-31T18:17:37Z |
| `5696170207` | `f669ab7` | 2026-07-31T18:17:37Z |
| `5696081625` | `f1ab844` | 2026-07-31T18:10:24Z |
| `5696011125` | `f626bf1` | 2026-07-31T18:04:34Z |
| `5695761983` | `025e7cd` | 2026-07-31T17:44:48Z |
| `5695738163` | `9ce2651` | 2026-07-31T17:42:51Z |
| `5694669427` | `6cec27f` | 2026-07-31T16:19:03Z |
| `5694069465` | `f0b639c` | 2026-07-31T15:35:19Z |
| `5692325780` | `5fd6bd8` | 2026-07-31T13:31:24Z |
| `5686140050` | `77208f7` | 2026-07-31T04:01:42Z |
| `5685774205` | `3cf28c9` | 2026-07-31T03:15:18Z |
| `5685407576` | `55f5e1e` | 2026-07-31T02:29:25Z |
| `5685226212` | `dc3bedd` | 2026-07-31T02:06:10Z |

## Final recommendation

1. Keep Production on `origin/main` only (`df16aec`).
2. Do **not** promote any current Preview.
3. For unique experimental Previews (AI / MT5 / Dependabot / STOP docs): leave as Preview or close; merge to main only via explicit approved PRs later.
4. Authenticate Vercel MCP/CLI in desktop if a native Vercel Deployment ID (dpl_*) inventory is required beyond GitHub deployment IDs.
