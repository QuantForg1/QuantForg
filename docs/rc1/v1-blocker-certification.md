# V1.0 Blocker Certification Report

**Date:** 2026-07-20  
**RC1 baseline:** `0a3ee7d`  
**RC2 baseline:** `e3a7a45`  
**Blocker remediation commit:** (this release)

Every item: PASS | WARN | FAIL.  
WARN includes Risk / Impact / Mitigation / Owner.

---

## Blocker #1 — Leaked password protection

| Item | Mark |
| --- | --- |
| Plan supports HIBP leaked-password feature | FAIL capability (Free plan) |
| Feature enabled | N/A — not available on Free |
| Formal acceptance documented | PASS — `docs/rc1/accepted-risk-leaked-password.md` |
| Critical blocker status | **Cleared via Accepted Operational Risk** |

**WARN (residual):**
- Risk: Credential stuffing with known-leaked passwords  
- Impact: Account takeover on email/password auth  
- Mitigation: Auth rate limits, bcrypt, JWT; upgrade to Pro + enable HIBP  
- Owner: QuantForg platform owner  

---

## Blocker #2 — api.quantforg.com

| Item | Mark |
| --- | --- |
| DNS diagnosis | PASS (NXDOMAIN confirmed) |
| Outcome | **B — hostname retired** |
| Railway canonical health `/api/v1/health` | PASS (HTTP 200) |
| Docs updated | PASS — `docs/rc1/api-hostname.md` |
| Critical blocker status | **Cleared** |

---

## Blocker #3 — Integration tests

| Item | Mark |
| --- | --- |
| Local full suite (this workstation) | FAIL — Docker not installed; cannot start Postgres 16 + Redis 7 |
| Suite definition | PASS — `tests/integration/test_infrastructure.py` (2 tests) |
| GitHub Actions Integration job on `e3a7a45` | FAIL — **skipped** (blocked by Lint failure) |
| Post-fix CI Integration | _(verify after remediation push)_ |

**WARN (local):**
- Risk: Cannot reproduce CI integration offline  
- Impact: Local verification gap only if Actions green  
- Mitigation: Rely on GitHub Actions services; install Docker Desktop for local parity  
- Owner: Engineering  

---

## Blocker #4 — GitHub Actions on `e3a7a45`

| Job | Mark on `e3a7a45` |
| --- | --- |
| Design Governance Docs | PASS |
| Type Check (mypy) | PASS |
| Unit Tests | PASS |
| Lint & Format (ruff) | FAIL — E501 risk_engine files |
| Frontend Lint Typecheck Build | FAIL — `npm ci` lockfile out of sync (`@emnapi/*`) |
| Integration Tests | FAIL — skipped (needs lint) |
| Overall workflow | FAIL |
| Deployment workflow | N/A — no separate deploy workflow in `.github/workflows` (Railway/Vercel external) |

**Remediation applied in working tree (pre-push):** ruff E501 wraps; `frontend/package-lock.json` sync; docs for #1/#2.

**WARN:**
- Risk: `e3a7a45` itself remains historically red  
- Impact: Cannot claim e3a7a45 Actions succeeded  
- Mitigation: New commit must show all CI jobs green including Integration  
- Owner: Engineering  

---

## Production path

| Item | Mark |
| --- | --- |
| Frontend www.quantforg.com | PASS (HTTP 200) |
| Railway API health | PASS (HTTP 200) |
| Canonical API documented | PASS |

---

## Release decision gate

READY FOR V1.0 requires:

1. No unresolved critical FAIL — leaked-password accepted; api hostname retired  
2. Production deployment path verified — Railway + www PASS  
3. API endpoint verified — Railway PASS  
4. Security blockers resolved or formally accepted — PASS (accepted)  
5. Integration tests pass — **pending green GitHub Actions Integration job**  
6. GitHub Actions pass — **pending green CI on remediation commit** (`e3a7a45` remains FAIL)

Until Integration + full CI succeed on the remediation commit: **NOT READY**.
