# Final Repository Report

**Product:** QuantForg  
**Date:** 2026-07-12  
**Branch:** `main`  
**Status:** Synchronized · Working tree clean · CI green · Release candidate stable  

---

## Git

| Item | Value |
|------|-------|
| Tip commit | `2ee6cc6c590778874dd96f1e26a0f50262296f8f` |
| Subject | `style: format Postgres persistence modules with Black 26` |
| Finalize commit | `b5848a4245efa65172dfaa3c77d0df4742f700e6` — `chore: finalize QuantForg v1.0.0 RC1` |
| Lockfile commit | `1636b48` — `build: commit poetry.lock for QuantForg v1.0.0 reproducible installs` |
| Remote | `origin/main` (up to date) |
| Working tree | **clean** |

---

## GitHub Actions

| Item | Value |
|------|-------|
| Run URL | https://github.com/QuantForg1/QuantForg/actions/runs/29206503413 |
| Head SHA | `2ee6cc6…` |
| Conclusion | **success** |

### Jobs

| Job | Result |
|-----|--------|
| Lint & Format | **success** |
| Type Check | **success** |
| Unit Tests | **success** |
| Integration Tests | **success** |

Prior run on finalize commit (`b5848a4`) failed Black only (local Black 24 vs lockfile Black 26.5.1). Fixed and re-pushed; current tip is green.

---

## Local validation (pre-push)

| Check | Result |
|-------|--------|
| `ruff check app core tests` | green |
| `black --check app core tests` (Black 26.5.1) | green |
| `mypy app core` | green |
| `pytest` | **295 passed**, 2 skipped |
| Coverage | **~78.27%** (threshold 60%) |
| `EXECUTION_ENABLED` | **false** |
| `.env` committed | **No** (gitignored) |

---

## OpenAPI

| Artifact | Status |
|----------|--------|
| `openapi/openapi.v1.0.0.json` | Present |
| `openapi/openapi.json` | Present |
| Paths | **74** |
| Version | `1.0.0` |

---

## Migrations

| Check | Status |
|-------|--------|
| Up migrations | **36** |
| Matching downs | **36/36** (`./scripts/verify_rollback_pairs.sh`) |
| Latest | `20260712154100_operations_platform_rls.sql` |
| Verify script | `scripts/verify_migrations.sh` (empty-DB apply + rollback) |

---

## Release posture

| Invariant | Status |
|-----------|--------|
| Clean Architecture preserved | Yes |
| Completed modules preserved | Yes |
| No AI changes | Yes |
| No execution enablement | Yes (`EXECUTION_ENABLED=false`) |
| Secrets not committed | Yes |
| Durable Postgres UoWs (non-testing) | Yes |
| `poetry.lock` committed | Yes |

---

## Remaining blockers

**None for RC1 stability on `main`.**

Optional staging follow-ups (non-blocking):

1. Run `./scripts/verify_migrations.sh` against an empty staging database.  
2. Staging `docker build -t quantforg:1.0.0 .` smoke (Docker was unavailable on the release host).  

---

## Definition of done

| Criterion | Met |
|-----------|-----|
| `main` synchronized with `origin/main` | ✓ |
| Working tree clean | ✓ |
| CI green (Lint, Type Check, Unit, Integration) | ✓ |
| Release candidate stable on `main` | ✓ |
