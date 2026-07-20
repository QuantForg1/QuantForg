# V1.0 Blocker Certification Report

**Date:** 2026-07-20  
**RC1 baseline:** `0a3ee7d`  
**RC2 baseline:** `e3a7a45` (CI historically **failure**)  
**Blocker remediation:** `52d09fd` (CI **success**, including Integration)

Every item: PASS | WARN | FAIL.  
WARN includes Risk / Impact / Mitigation / Owner.

---

## Blocker #1 — Leaked password protection

| Item | Mark |
| --- | --- |
| Org plan | Free (MCP `get_organization`) |
| HIBP feature available on plan | FAIL capability — Pro+ only |
| Formal acceptance | PASS — `accepted-risk-leaked-password.md` |
| Critical blocker | Cleared via **Accepted Operational Risk** |

**WARN (residual):**
- Risk: Credential stuffing with known-leaked passwords
- Impact: Account takeover on email/password auth
- Mitigation: Auth rate limits; bcrypt; JWT; upgrade to Pro + enable HIBP
- Owner: QuantForg platform owner

---

## Blocker #2 — api.quantforg.com

| Item | Mark |
| --- | --- |
| DNS | PASS — NXDOMAIN (8.8.8.8 / 1.1.1.1) |
| Outcome | B — hostname **retired** |
| Railway `/api/v1/health` | PASS — HTTP 200 |
| Docs | PASS — `api-hostname.md` |
| Critical blocker | Cleared |

---

## Blocker #3 — Integration tests

| Item | Mark |
| --- | --- |
| Local Docker suite | WARN — Docker not installed on cert workstation |
| GitHub Actions Integration on `52d09fd` | PASS — job success (run 29787248957) |
| Suite content | PASS — postgres + redis health probes |

**WARN (local only):**
- Risk: No local Docker parity
- Impact: Engineers without Docker cannot run integration offline
- Mitigation: CI services are source of truth; install Docker Desktop for local
- Owner: Engineering

---

## Blocker #4 — GitHub Actions

### On `e3a7a45` (historical)

| Job | Mark |
| --- | --- |
| Design Governance | PASS |
| Type Check | PASS |
| Unit Tests | PASS |
| Lint & Format | FAIL |
| Frontend | FAIL (`npm ci`) |
| Integration | FAIL (skipped) |
| Overall | FAIL |

### On `52d09fd` (remediation — verified)

| Job | Mark |
| --- | --- |
| Design Governance Docs | PASS |
| Type Check | PASS |
| Lint & Format | PASS |
| Unit Tests | PASS |
| Frontend Lint Typecheck Build | PASS |
| Integration Tests | PASS |
| Overall CI workflow | PASS |
| Separate Deployment workflow | WARN — none in repo; Railway/Vercel external |

**WARN (deploy workflow):**
- Risk: No GitHub Actions deploy gate
- Impact: Deploy success inferred from live health, not Actions
- Mitigation: Railway + Vercel health probes; add deploy workflow later if required
- Owner: Engineering

---

## Production path

| Item | Mark |
| --- | --- |
| www.quantforg.com | PASS |
| Railway API health | PASS |
| Canonical API | PASS — Railway (api.quantforg.com retired) |

---

## Release decision

Critical FAIL items remaining: **none**  
Security: resolved or **formally accepted**  
API endpoint: **verified** (Railway)  
Integration: **PASS** on `52d09fd` Actions  
GitHub Actions: **PASS** on `52d09fd` (e3a7a45 remains historically FAIL)

### READY FOR V1.0
