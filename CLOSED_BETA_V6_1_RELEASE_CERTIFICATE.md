# QuantForg V6.1 — Closed Beta Production Certificate

**Date:** 2026-07-15  
**Release:** Closed Beta V6.1 (ops-only — no new modules)  
**Git SHA:** `1a731b878d100225658a0ae24feb8b1c7e3f0a96` (+ follow-up What’s New bump if present on `main`)  
**Remote:** `https://github.com/QuantForg1/QuantForg.git` → `origin/main`

---

## 1. Preflight (verified)

| Check | Result |
|-------|--------|
| Working tree | Clean at push time |
| Commit on `origin/main` | `1a731b878d100225658a0ae24feb8b1c7e3f0a96` |
| pytest unit | **444 passed** |
| Frontend typecheck / build | **Pass** |
| Playwright | **21/21 passed** |
| Locked modules modified | **None** |

---

## 2. Push status

`9074a00..1a731b8` pushed to `origin/main` (2026-07-15).

---

## 3. Railway deployment status

**API:** `https://quantforg-production.up.railway.app`

| Probe | Result |
|-------|--------|
| `GET /health/live` | `{"status":"alive"}` |
| `GET /health` | `healthy` · env `production` · postgres healthy (~165ms) · redis disabled |
| `GET /api/v1/version` | QuantForg `1.0.0` · `/api/v1` |
| Root HTTP | 200 |

Protected routes (`decision-engine`, `quant-ai`, `quant-studio`, `research-lab`, `ops`, `portfolio`) return **401 missing_token** without auth — API up and auth enforced.

> Railway CLI was not authenticated in this environment; status confirmed via public health probes. Auto-deploy of `main` depends on Railway project linkage (operator confirm in dashboard).

---

## 4. Smoke test summary

| Layer | Result |
|-------|--------|
| Production health | Pass |
| Auth gate on desks (unauthenticated) | 401 Pass |
| Local Playwright (broker, workspace, DE, Quant AI/Studio/Lab, dashboard/auth flows) | 21/21 Pass |
| EXECUTION_ENABLED production coerce | Pass — `app_env=production` forces `False` even if set `True` |
| `.env.example` | `EXECUTION_ENABLED=false` |

---

## 5. Surface verification (Closed Beta)

| Surface | Evidence |
|---------|----------|
| Broker / Terminal / Execution | E2E institutional-desk Pass |
| Decision Engine / Quant AI / Studio / Research Lab | Dedicated E2E Pass + prod 401 |
| Dashboard / Portfolio / Settings | beta-launch E2E Pass |
| Wallet / Orders / History | Auth layout gated; route present (polish e2e gap known) |
| Operations / Cloud Ops | Routes present; ops API 401 without admin token |
| What’s New | Curated notes incl. V6.1 Closed Beta |
| Feedback / issue reporting | `FeedbackWidget` + `/support#feedback` wired |

---

## 6. EXECUTION_ENABLED

**Confirmed safe for Closed Beta:**

- Default / example: `false`
- Production settings validator **forces** `execution_enabled=False` when `APP_ENV=production`
- Advisory desks never flip the flag

Operator: in Railway Variables, keep `EXECUTION_ENABLED=false` (redundant but explicit).

---

## 7. Closed Beta controls — enablement

UI already shipped (no new modules): `BetaInviteGate`, `BetaBanner`, `MaintenanceGate`, `FeedbackWidget`, `/whats-new`, Support issue path.

### Frontend host (Vercel / equivalent) — set now

| Variable | Closed Beta V6.1 value | Purpose |
|----------|------------------------|---------|
| `NEXT_PUBLIC_BETA_MODE` | `true` | Invite-only gate + **Closed Beta banner** |
| `NEXT_PUBLIC_BETA_INVITE_CODE` | *(rotate; never commit)* | Cohort unlock |
| `NEXT_PUBLIC_MAINTENANCE_MODE` | `false` | Do **not** hard-block invitees at launch |
| `NEXT_PUBLIC_READ_ONLY_MODE` | `false` (or `true` if freeze) | Optional mutate freeze |
| `NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL` | optional | Feedback sink |
| `NEXT_PUBLIC_API_BASE_URL` | `https://quantforg-production.up.railway.app/api/v1` | API |

After setting vars: **redeploy frontend**. Then smoke: invite unlock → banner visible → `/whats-new` → floating feedback → `/support#feedback`.

**Note:** “Maintenance banner” for launch = Closed Beta banner via `BetaBanner` when `BETA_MODE=true`. Full maintenance lock (`MAINTENANCE_MODE=true`) is for incidents only (`INCIDENT_RESPONSE.md`).

---

## 8. GO / NO GO

### GO — Closed Beta V6.1 (conditional)

**Green:** git on `main`, Railway API healthy, exec kill-switch, tests/e2e green, beta UX wired.

**Operator conditions before inviting users:**

1. Frontend env flags above applied + redeployed  
2. Invite code distributed out-of-band  
3. Confirm Railway `EXECUTION_ENABLED=false`  
4. Owner can open `/ops` and `/cloud-ops`  
5. Paper-first messaging in invite email  

### NO GO

- Unsupervised live trading  
- Public open beta / GA without Major security residuals addressed  

---

## Sign-off

| Role | Stance |
|------|--------|
| Release Engineering | **GO conditional** |
| QA | **GO** (gates green) |
| SRE | **GO conditional** (Railway healthy; frontend flag deploy operator) |
| Production Operations | **GO conditional** (invite + banner enable on frontend host) |
