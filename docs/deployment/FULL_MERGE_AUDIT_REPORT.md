# Full Merge Audit Report

**Date:** 2026-07-31 (UTC)  
**Repository:** QuantForg1/QuantForg  
**Auditor branch:** `cursor/full-merge-audit-bc83`  
**Guardrails:** No UI / UX / branding / AI / MT5 / OMS / strategy / scoring / auth / schema / API / routing / env / deploy-config / business-logic changes. Consolidation audit + documentation only.

---

## Executive verdict

**Production fully synchronized with main**

| Check | Result |
|---|---|
| `origin/main` HEAD | `f1ab8444e7de90057e700f260af0a73f056c8809` |
| Approved work missing from main | **None** |
| Branches merged in this consolidation | **None required** (already on main) |
| Intentionally skipped open PRs | All remaining open PRs (draft / experimental / dependabot / superseded STOP docs) |
| `https://www.quantforg.com` landing HTML | **Exact byte match** of `origin/main:frontend/public/go-live-landing.html` |
| Promote-every-Preview strategy | **Not used** (forbidden) |

No additional merge into `main` was required. Creating a duplicate consolidation merge would risk churn without adding approved work.

---

## Current production SHA vs main

| Ref | SHA | Notes |
|---|---|---|
| `origin/main` | `f1ab8444e7de90057e700f260af0a73f056c8809` | Tip at audit time |
| `v4.0.0` tag (annotated target) | `f0b639ca2eae215856d8185abc0633d4ac359319` | Ancestor of `origin/main` (**contained**) |
| Production landing (`www.quantforg.com`) | Content hash `796c44e3ffd221993b0c3f1d2b027f02` | Identical to main `go-live-landing.html` |
| Vercel MCP | Unavailable in this agent (needs desktop auth) | Verified via live HTTP + content hash instead |

Production is serving the RC4 + pricing/manual-license landing that is on `origin/main`.

---

## Step 1 — Git / PR inventory (already in main)

### Recent `origin/main` tip (newest first)

| SHA | Subject |
|---|---|
| `f1ab844` | docs(deployment): add Manual License Production release report |
| `f626bf1` | feat(ui): replace self-serve checkout with manual license purchase flow |
| `025e7cd` | docs(deployment): add Pricing v2 push verification report |
| `9ce2651` | feat(pricing): finalize RC4 institutional pricing & conversion experience |
| `6cec27f` | Merge pull request **#65** (owner login recovery report) |
| `2c0583b` | Merge pull request **#64** (RC4 brand rebrand) |
| `550dcd5` / `f0b639c` … | RC4 polish + reports (via #64) |
| `5fd6bd8` … | Limited live pilot / trading-component health (via **#63**) |

### Approved themes verified present on main

| Theme | Evidence on `origin/main` |
|---|---|
| RC4 branding / logo / favicons / OG | PR #64 merged; assets under `frontend/public/brand/` |
| RC4 UI tokens / landing | `globals.css`, `go-live-landing.html`, BrandLogo |
| Pricing / conversion | `9ce2651` |
| Manual license purchase | `f626bf1` |
| Owner login recovery report | PR #65 merged; Admin API password repair was Auth-side (no app code) |
| Production readiness / RC1 / health | PR #63 + prior RC1 pipeline PRs |
| Gateway hardening history | Gateway 1.1.6 + Windows deploy merges on main |

### Recently merged PRs into `main` (selected)

| PR | Merged | Head | Title |
|---|---|---|---|
| #65 | 2026-07-31 | `cursor/owner-login-recovery-bc83` | Owner login recovery report |
| #64 | 2026-07-31 | `cursor/rc4-brand-rebrand-bc83` | RC4 QuantForg brand rebrand |
| #63 | 2026-07-31 | `cursor/prod-readiness-fix-bc83` | Trading-component health + RC1 endpoint |
| #59/#58/#57 | 2026-07-31 | RC1 evidence / validation | RC1 pipeline + STOP evidence |
| #47/#46/#45 | 2026-07-31 | PRE / DPS / 24-7 | Institutional engines + session soft-weight |
| #44–#37 | 2026-07-30/31 | Prod blockers / NOC / validation / v7.1 | Production ops stack |

---

## Step 2 — Branch comparison vs `origin/main`

### Already contained (ahead = 0) — DO NOT MERGE

These tips are ancestors of / already represented on `main` (behind main only):

| Branch | Ahead | Behind | Classification |
|---|---:|---:|---|
| `cursor/rc4-brand-rebrand-bc83` | 0 | 7 | **Already contained** (PR #64) |
| `cursor/owner-login-recovery-bc83` | 0 | 13 | **Already contained** (PR #65) |
| `cursor/prod-readiness-fix-bc83` | 0 | 14 | **Already contained** (PR #63) |
| `cursor/rc1-*` / `final-pre-live-rc1` | 0 | ≥17 | **Already contained** |
| `cursor/portfolio-risk-engine-v2-bc83` | 0 | 23 | **Already contained** (#47) |
| `cursor/dynamic-position-sizing-v2-bc83` | 0 | 25 | **Already contained** (#46) |
| `cursor/24-7-session-soft-weight-bc83` | 0 | 27 | **Already contained** (#45) |
| `cursor/production-blockers-fix-bc83` | 0 | 36 | **Already contained** (#44) |
| `cursor/execution-evidence-collector-bc83` | 0 | 44 | **Already contained** (#43) |
| `cursor/noc-command-center-bc83` | 0 | 48 | **Already contained** (#42) |
| `cursor/production-validation-mode-bc83` | 0 | 64 | **Already contained** (#41) |
| `cursor/prod-ops-verify-bc83` | 0 | 70 | **Already contained** (#40) |
| `cursor/v7-1-*` / gateway / oms heartbeat | 0 | ≥31 | **Already contained** / superseded by later main |

### Unique commits remain (ahead > 0) — DO NOT MERGE

| Branch | Ahead | Behind | Why DO NOT MERGE |
|---|---:|---:|---|
| `cursor/ultra-aggressive-risk-profile-bc83` | 5 | 22 | Draft experimental risk profile — touches risk/strategy; **not approved** for this consolidation |
| `cursor/score-pipeline-integration-bc83` | 4 | 22 | Draft AI/ITE scoring stack — **forbidden** by guardrails (AI/scoring) |
| `cursor/ai-score-calibration-bc83` | 3 | 22 | Draft AI calibration — **forbidden** |
| `cursor/ai-decision-rejection-analysis-bc83` | 3 | 22 | Draft AI evidence — **forbidden** |
| `cursor/m15-trend-semantics-v2-bc83` | 2 | 22 | Draft AI/strategy semantics — **forbidden** |
| `cursor/ai-decision-engine-v2-bc83` | 1 | 22 | Draft AI engine — **forbidden** |
| `cursor/mtf-alignment-diagnostic-bc83` | 1 | 22 | Draft ITE diagnostic — experimental |
| `cursor/mt5-gateway-single-instance(-fix)` | 1–2 | 22 | Draft MT5 gateway changes — **forbidden** (MT5) / not approved |
| `cursor/production-readiness-validation-bc83` | 3 | 17 | STOP / **NOT READY** docs — **superseded** by ready evidence on main (#63) |
| `cursor/p0-gateway-recovery-bc83` | 2 | 17 | STOP / gateway 502 NOT READY — **superseded** |
| `cursor/infra-recovery-rc1-bc83` | 1 | 17 | STOP / NOT READY — **superseded** |
| `dependabot/*` (12 branches) | 1 each | 102–313 | Dependency bumps — **not part of approved product consolidation**; high behind-count |
| `feat/complete-user-platform-foundation` | 2 | 365 | Historical remnant — foundation **already merged** via #15; leftover tip is obsolete |
| `feat/broker-foundation-sprint-1` | 1 | 364 | Historical remnant — **already merged** via #16 |
| `railway/fix-deploy-*` | 1 each | 340–355 | Historical Railway fixes — **already merged** / obsolete relative to main |

---

## Step 3 — Open PR classification

| PR | State | Classification |
|---|---|---|
| #64 RC4 | **MERGED** | Already on main |
| #65 Login recovery docs | **MERGED** | Already on main |
| #48–#54 AI / score / MTF / ULTRA | Open draft | **DO NOT MERGE** (AI/strategy/scoring/risk) |
| #55–#56 MT5 single-instance | Open draft | **DO NOT MERGE** (MT5) |
| #60–#62 STOP NOT READY reports | Open draft / conflicts | **DO NOT MERGE** (superseded / obsolete) |
| #18–#36 Dependabot / railway leftover | Open | **DO NOT MERGE** for this consolidation |
| #65/#64 | Merged | — |

**SAFE TO MERGE now:** none remaining.

---

## Step 4–5 — Merges performed / conflicts

| Action | Result |
|---|---|
| Merge approved outstanding branches | **Skipped — none outstanding** |
| Conflict resolution | **N/A** |
| Risk of overwriting RC4 / Pricing / Login / Prod fixes | **Avoided** by not merging superseded/experimental tips |

---

## Step 6 — Verification (current `origin/main` tip)

| Gate | Result |
|---|---|
| Frontend `tsc --noEmit` | **PASS** |
| Frontend `eslint .` | **PASS** |
| Frontend `npm run build` | **PASS** |
| Backend unit tests | **PASS** — 1421 passed (`.venv/bin/pytest tests/unit -o addopts=''`) |
| Live production landing vs main HTML | **Exact match** |
| Brand assets on production | `/brand/quantforg-mark-256.png`, favicon, OG, manifest → **200** |

---

## Step 7 — Push to main

No consolidation merge commit was created on `main` because that would be empty of approved product delta.

This report is committed on `cursor/full-merge-audit-bc83` for documentation. Merging **only this docs report** into `main` is safe and does not alter application behavior.

---

## Step 8 — Vercel deploy policy

| Policy | Status |
|---|---|
| Deploy Production **only from `main`** | Required / affirmed |
| Sequential “Promote to Production” of Previews | **Forbidden — not performed** |
| Current production content | Matches `origin/main` landing artifact |

Vercel project MCP auth was unavailable in-cloud; content-level verification confirms Production is already reflecting main’s approved frontend tip for the public landing surface.

---

## Step 9 — Lost-work verification

| Approved workstream | Lost? |
|---|---|
| Gateway recovery / deploy scripts | **No** — on main |
| RC1 / trading-component health | **No** — on main (#63) |
| RC4 branding + UI + logo + favicons | **No** — on main (#64); live on www |
| Pricing / manual license | **No** — on main tip |
| Owner login recovery | **No** — Auth repair live; docs on main (#65) |

Experimental AI/MT5/dependabot tips remain open by design and are **not** classified as approved production consolidation inputs.

---

## Final statement

**1. Production fully synchronized with main**

- No approved PRs remain unmerged.
- No additional product merges were required.
- Production public landing is an exact reflection of `origin/main`’s `go-live-landing.html`.
- Remaining open branches are intentionally **DO NOT MERGE**.
