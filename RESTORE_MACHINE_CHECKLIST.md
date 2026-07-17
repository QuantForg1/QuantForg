# QuantForg — Windows Machine Restore Checklist

**Date:** 2026-07-17  
**Scope:** Inspect, diagnose, and document local development recovery after a clean Windows reinstall.  
**Guardrails:** No application architecture, business logic, schema, API, UI, or package upgrades were changed. This file is documentation only.

---

## Executive verdict

| Area | Status | Action required |
|------|--------|-----------------|
| Git / Node / npm / pnpm | OK | None |
| Frontend deps | OK (installed) | Create `frontend/.env.local` |
| Poetry → PyPI network | OK (IPv4) | See diagnosis — failure is **not** primarily network |
| Backend Poetry install | **FAILING** | Install **Python 3.13** (project target); current host is **3.14.6** |
| Docker | Missing | Recommended for Postgres + Redis; not the only path |
| Root / frontend `.env` | Missing | Copy from `*.env.example` |
| Make | Missing | Optional; use Poetry / Compose commands directly |

**Root cause of backend install failure:** Poetry can reach PyPI. Install fails while building `asyncpg==0.30.0` from source on **Python 3.14 / Windows**, because that release publishes **no `cp314` Windows wheel** (wheels exist for `cp313`). Without Microsoft C++ Build Tools, the compile step fails (`Microsoft Visual C++ 14.0 or greater is required`).

---

## 1. Required local prerequisites

### Core (documented by repo)

| Prerequisite | Version / notes | Source of truth |
|--------------|-----------------|-----------------|
| Python | **3.13.x** (`pyproject.toml`: `python = "^3.13"`; README / bootstrap expect 3.13) | `pyproject.toml`, `README.md`, `scripts/bootstrap.sh`, `Dockerfile` |
| Poetry | 1.8+ (machine has 2.4.1 via `python -m poetry`) | `docs/development.md` |
| Git | Any recent | clone already OK |
| Docker Desktop + Compose | For local Postgres 16 + Redis 7 (+ optional API container) | `docs/development.md`, `docker-compose.yml`, `scripts/bootstrap.sh` |
| Make | Optional | `Makefile`, `docs/development.md` |

### Frontend

| Prerequisite | Version / notes | Source of truth |
|--------------|-----------------|-----------------|
| Node.js | Machine has v24.18.0 (works; no `engines` pin in `package.json`) | `frontend/package.json` |
| pnpm and/or npm | Both present; lockfiles: `pnpm-lock.yaml` + `package-lock.json` | `frontend/` |
| Frontend deps | Already installed | User status |

### Windows-specific tooling

| Tool | Why |
|------|-----|
| Git Bash (`C:\Program Files\Git\bin\bash.exe`) | Present — needed to run `scripts/bootstrap.sh` (bash) |
| Chocolatey | Present (2.7.3) — useful to install Python 3.13 / Docker / make |
| Microsoft C++ Build Tools | **Only** needed if staying on Python 3.14 and compiling native wheels; prefer Python 3.13 instead |
| WSL2 | Optional alternative for Docker / Linux-like workflow; not required if Docker Desktop runs natively |

### Optional / feature-specific

| Prerequisite | When needed |
|--------------|-------------|
| MetaTrader 5 terminal | Live MT5 adapter / Windows gateway (`MT5_USE_MOCK=false`) |
| MT5 Windows Gateway process | Bridge from API to local MT5 (`deploy/mt5_gateway/`) |
| Market-data API keys | Finnhub, Trading Economics, Twelve Data, Alpha Vantage, Polygon — empty = providers unconfigured |

---

## 2. Required environment files

| File | Template | Purpose | Present on this machine? |
|------|----------|---------|--------------------------|
| `.env` (repo root) | `.env.example` | Backend / Compose / Alembic settings | **MISSING** |
| `frontend/.env.local` | `frontend/.env.example` | Next.js public config (`NEXT_PUBLIC_*`) | **MISSING** |
| MT5 gateway env (process / NSSM / lines in root `.env`) | `deploy/mt5_gateway/gateway.env.example` | Local MT5 gateway only | **MISSING** (optional for core API) |

**Do not commit** real `.env` / `.env.local` / gateway secrets.

---

## 3. Complete gap checklist

### 3.1 Missing software

- [ ] **Python 3.13.x** (critical — only 3.14.6 is installed; no 3.13 on `py -0p`)
- [ ] **Docker Desktop** (and ensure Compose v2: `docker compose`)
- [ ] **Make** (optional; Chocolatey: `choco install make`)
- [ ] **Poetry on PATH** (optional convenience — currently only `python -m poetry` works; `poetry` shim not found)
- [ ] **MSVC Build Tools** (avoid if possible — only if you insist on Python 3.14 + source builds)

### 3.2 Missing environment files / variables

#### Root `.env` (copy from `.env.example`)

Minimum for a healthy local boot (from `docs/configuration.md` + `.env.example`):

| Variable | Required for local? | Notes |
|----------|---------------------|-------|
| `APP_ENV` | Yes | `development` |
| `SECRET_KEY` | Yes | ≥ 32 chars; change from example default for anything beyond throwaway |
| `POSTGRES_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` | Yes for durable local DB | Defaults in example target Docker Compose |
| `DATABASE_URL` | Alternative | Overrides `POSTGRES_*`; use for remote Postgres / Supabase pooler |
| `REDIS_HOST` / `PORT` | Optional | Compose uses these inside containers |
| `REDIS_URL` | Optional | **If unset, Redis is treated as disabled** (`settings.redis_configured`) |
| `SUPABASE_URL` + key(s) | Optional | Needed for Supabase auth / client features |
| `SUPABASE_DB_PASSWORD` | Optional | Composes pooler DSN when `DATABASE_URL` unset |
| `AUTH_REDIRECT_URL` | Recommended with Supabase | Default example: `http://localhost:3000/auth/callback` |
| `MT5_*` / gateway tokens | Optional | Mock MT5 is default (`MT5_USE_MOCK=true`) |
| `EXECUTION_ENABLED` | Keep `false` locally unless intentional | |
| Market-data `*_API_KEY` | Optional | |

#### Frontend `.env.local` (copy from `frontend/.env.example`)

| Variable | Local recommendation |
|----------|----------------------|
| `NEXT_PUBLIC_API_BASE_URL` | Point at local API: `http://localhost:8000/api/v1` (example currently points at Railway) |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` |
| `NEXT_PUBLIC_APP_ENV` | `development` for local DX |
| `NEXT_PUBLIC_MOCK_AI` / feature flags / beta flags | As needed; see template |

### 3.3 Missing local services

| Service | Port (default) | Role | How repo expects it |
|---------|----------------|------|---------------------|
| PostgreSQL 16 | 5432 | Primary durable store / Alembic | `docker compose` service `postgres`, or native/remote DB |
| Redis 7 | 6379 | Cache (optional if `REDIS_URL` unset) | `docker compose` service `redis` |
| QuantForg API | 8000 | FastAPI | `make run` / `poetry run uvicorn ...` or Compose `api` |
| Next.js frontend | 3000 | UI | `pnpm dev` / `npm run dev` in `frontend/` |
| MT5 Gateway | 8765 | Windows-only bridge | Optional |

### 3.4 Missing credentials / secrets

Obtain or generate locally (never commit):

- [ ] Strong `SECRET_KEY` (and keep JWT aliases consistent if used in deploy platforms)
- [ ] Postgres password aligned with running DB (`POSTGRES_PASSWORD` / `DATABASE_URL`)
- [ ] Supabase project URL + anon/publishable (+ service role only if required) — if using Supabase auth
- [ ] `SUPABASE_DB_PASSWORD` or full `DATABASE_URL` — if using hosted DB instead of Docker Postgres
- [ ] Optional: Finnhub / Trading Economics / Twelve Data / Alpha Vantage / Polygon keys
- [ ] Optional: `MT5_GATEWAY_TOKEN` / `MT5_GATEWAY_CALLER_TOKEN` pair for gateway
- [ ] Optional: beta invite code if exercising closed-beta frontend gates

---

## 4. Poetry / PyPI diagnosis (this machine)

### Checks performed

| Check | Result |
|-------|--------|
| Proxy env (`HTTP(S)_PROXY`, etc.) | **Unset** (process / user / machine) |
| WinHTTP proxy | **Direct access (no proxy)** |
| IE/system ProxyEnable | **0** |
| DNS `pypi.org` | Resolves (A + AAAA) |
| TCP 443 → `pypi.org` | **Success** (IPv4) |
| HTTPS GET `https://pypi.org/simple/pip/` | **HTTP 200** (PowerShell + curl) |
| `python -m pip index versions pip` | **Works** |
| Poetry config index/proxy overrides | **None** unusual; parallel installer on; keyring enabled |
| pip config files | No custom `index-url`; only sandbox cache-dir override in this agent environment |
| IPv4 curl to PyPI | **200** |
| IPv6 curl to PyPI | **Fails** (`Could not resolve host` over `-6`) |
| `poetry install --dry-run` | Resolves lockfile / package plan successfully |
| `poetry install` (real) | **Fails on `asyncpg` build** (MSVC required) |

### What is *not* the primary problem

- Not a configured HTTP(S) proxy.
- Not a Poetry “wrong index” configuration.
- Not a pip.ini pointing at a broken mirror.
- Not a total DNS blackhole for PyPI (IPv4 works).

### What *is* the problem

1. **Wrong Python major for Windows wheels:** host default is **Python 3.14.6** (`C:\Python314\python.exe`). Locked `asyncpg==0.30.0` has Windows wheels for **cp313**, not **cp314**. Poetry downloads the sdist and attempts a local compile → fails without MSVC.
2. **IPv6 resolution failure** for `pypi.org` may cause intermittent client hangs if a tool prefers AAAA first; prefer IPv4 / ensure dual-stack works. Secondary risk, not the install error observed.
3. **`poetry` not on PATH** — use `python -m poetry` or install the Poetry shim; easy to confuse with “Poetry broken.”
4. Agent/sandbox cache redirection under `%TEMP%\cursor-sandbox-cache\...` can affect Poetry venv location when commands run inside Cursor; run restore commands in a normal elevated user PowerShell / Git Bash outside sandbox when installing for real.

### Recommended fix order (non-destructive)

1. Install **Python 3.13** (official installer or `pyenv`/`chocolatey`).
2. `py -3.13 -m pip install poetry` (or reuse existing Poetry and `poetry env use 3.13`).
3. Retry `poetry install` — should use prebuilt wheels.
4. Only if you must stay on 3.14: install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and accept slower/fragile native builds (not recommended for this repo).

---

## 5. Is Docker required for local development?

**Official docs say yes as the default path** (`docs/development.md` lists Docker & Compose as prerequisites; bootstrap starts `postgres` + `redis` via Compose).

**Practically:**

| Goal | Docker required? |
|------|------------------|
| Match documented happy path | **Yes** (simplest) |
| Run Next.js UI against remote Railway API | **No** |
| Run API process only (`uvicorn`) | **No** (Docker not required for the Python process) |
| Local Postgres + Redis without installing them natively | **Yes** (Compose is the repo’s intended method) |
| Integration tests using `testcontainers` | **Yes** (needs Docker daemon) |
| Production-like full stack (`api` + `postgres` + `redis` containers) | **Yes** |

**Verdict:** Docker is **strongly recommended** and required for the **documented** local stack and testcontainers. It is **not** strictly required to run the API binary if Postgres (and optionally Redis) are provided another way.

---

## 6. Can the backend run without Docker?

**Yes, with caveats.**

### Supported without Docker

1. Install Python 3.13 + Poetry deps on the host.
2. Provide Postgres via:
   - Native Windows PostgreSQL 16, **or**
   - Remote `DATABASE_URL` / Supabase session pooler.
3. Leave `REDIS_URL` unset → Redis client stays disabled (health reports Redis as disabled/not configured).
4. Optionally set `DURABLE_PERSISTENCE=false` to force in-memory factories (dev/experiment only; not a substitute for real DB work).
5. Start API:

   ```bash
   python -m poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. Liveness: `GET /api/v1/health/live` does not require Postgres/Redis.  
   Readiness/full health: expects infrastructure probes (Postgres; Redis only when configured).

### Still needed without Docker

- Working Poetry venv (Python 3.13).
- Root `.env`.
- Reachable Postgres for durable features, migrations (`alembic upgrade head`), and most integration paths.
- Frontend separately needs Node + `.env.local`.

### Bootstrap behavior without Docker

`scripts/bootstrap.sh` prints a warning and continues if Docker is missing — it does **not** hard-fail. You must supply Postgres yourself.

---

## 7. Ordered command plan (do not run destructive steps blindly)

> Run these in a **normal** PowerShell or Git Bash as your user. Prefer **not** deleting volumes/DBs until you confirm there is nothing to keep. No `docker compose down -v`, no `poetry env remove` of shared envs, and no force-pushes are required for restore.

### Phase A — Fix Python / Poetry install (critical)

```powershell
# A1. Verify current interpreter (expect 3.14 today — problem)
py -0p
python --version

# A2. Install Python 3.13.x from python.org OR Chocolatey, then:
py -3.13 --version

# A3. Ensure Poetry available for 3.13
py -3.13 -m pip install --user poetry
# OR: existing Poetry, then bind the project env:
# poetry env use $(py -3.13 -c "import sys; print(sys.executable)")

# A4. From repo root
cd "C:\Users\P7 PROVIDER\Desktop\QuantForg"
py -3.13 -m poetry env use 3.13
py -3.13 -m poetry install

# A5. Pre-commit (optional but bootstrap does this)
py -3.13 -m poetry run pre-commit install
```

### Phase B — Environment files

```powershell
cd "C:\Users\P7 PROVIDER\Desktop\QuantForg"
Copy-Item .env.example .env
# Edit .env: SECRET_KEY, POSTGRES_*, optional SUPABASE_*, leave EXECUTION_ENABLED=false

cd frontend
Copy-Item .env.example .env.local
# Edit .env.local: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
#                 NEXT_PUBLIC_APP_ENV=development
cd ..
```

### Phase C — Local services (preferred: Docker)

```powershell
# C1. Install Docker Desktop for Windows, reboot if prompted, confirm:
docker version
docker compose version

# C2. Start infrastructure only (matches bootstrap)
docker compose up -d postgres redis

# C3. Wait until healthy, then migrate
py -3.13 -m poetry run alembic upgrade head
```

**Alternative without Docker:** install PostgreSQL 16 locally, create role/db matching `.env`, skip Redis or install Redis for Windows/Memurai, then run migrations as above.

### Phase D — Run backend

```powershell
cd "C:\Users\P7 PROVIDER\Desktop\QuantForg"
py -3.13 -m poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Equivalent if Make installed: make run
```

Verify:

```powershell
curl.exe http://localhost:8000/api/v1/health/live
curl.exe http://localhost:8000/api/v1/version
curl.exe http://localhost:8000/api/v1/health
```

### Phase E — Run frontend

```powershell
cd "C:\Users\P7 PROVIDER\Desktop\QuantForg\frontend"
pnpm install   # already done once; re-run only if needed
pnpm dev
# or: npm run dev
```

Open `http://localhost:3000`.

### Phase F — Optional full Compose stack

```powershell
docker compose up -d
docker compose ps
docker compose logs -f api
```

### Phase G — Optional quality gate

```powershell
py -3.13 -m poetry run ruff check app core tests
py -3.13 -m poetry run mypy app core
py -3.13 -m poetry run pytest
# Integration/testcontainers need Docker running
```

### Phase H — Optional MT5 gateway (Windows only)

```powershell
# Add gateway vars from deploy/mt5_gateway/gateway.env.example into process env or .env
# Install / login MetaTrader 5 if using non-mock mode
py -3.13 -m poetry run quantforg-mt5-gateway
```

### Bootstrap script equivalent (Git Bash)

```bash
cd "/c/Users/P7 PROVIDER/Desktop/QuantForg"
# After Python 3.13 is on PATH as python3.13 (or adjust script expectations):
./scripts/bootstrap.sh
```

Note: stock `bootstrap.sh` checks `command -v python3.13`. On Windows you may need that shim on PATH or run the manual Phase A–C commands instead.

---

## 8. Current machine snapshot (2026-07-17)

| Item | Observed |
|------|----------|
| OS | Windows 10 (build 19045) |
| Git | 2.55.0.windows.2 |
| Python default | **3.14.6** (`C:\Python314\python.exe`) |
| Other Pythons | 3.14 only via `py -0p` — **no 3.13** |
| Poetry | 2.4.1 via `python -m poetry`; `poetry` exe **not** on PATH |
| Node | v24.18.0 |
| npm | 11.16.0 |
| pnpm | 11.13.1 |
| Docker | **Not installed** |
| Make | **Not found** |
| Chocolatey | 2.7.3 |
| Git Bash | Present |
| Proxy | None |
| PyPI IPv4 | OK |
| PyPI IPv6 | Broken resolve |
| Root `.env` | Missing |
| `frontend/.env.local` | Missing |
| Frontend `node_modules` | Installed (per user) |
| Backend venv deps | Not successfully installed (asyncpg build fail on 3.14) |

---

## 9. Success criteria

Restore is complete when all of the following are true:

- [ ] `py -3.13 -m poetry run python -V` → Python 3.13.x
- [ ] `py -3.13 -m poetry install` completes without compiling asyncpg from source
- [ ] `.env` and `frontend/.env.local` exist and are edited for local URLs/secrets
- [ ] Postgres accepting connections (Docker or native/remote)
- [ ] `alembic upgrade head` succeeds against that DB
- [ ] `GET /api/v1/health/live` → 200
- [ ] `GET /api/v1/health` reflects Postgres healthy (Redis disabled or healthy)
- [ ] Frontend loads on `:3000` and can reach the chosen API base URL
- [ ] (Recommended) Docker Desktop installed for Compose + future testcontainers

---

## 10. Explicit non-actions (per guardrails)

- Do **not** change `pyproject.toml` / lockfile to “support 3.14” as a shortcut without an intentional project decision.
- Do **not** modify application code, schemas, APIs, or UI for machine restore.
- Do **not** upgrade packages unless install remains blocked after Python 3.13 is in use.
- Do **not** commit `.env`, `.env.local`, or real credentials.

---

## Quick reference — missing vs done

| # | Item | Status |
|---|------|--------|
| 1 | Clone + Git | Done |
| 2 | Node / npm / pnpm + frontend install | Done |
| 3 | Poetry available | Done (module form) |
| 4 | Python 3.13 | **Missing** |
| 5 | Backend `poetry install` | **Blocked** (3.14 / asyncpg) |
| 6 | Docker Desktop | **Missing** |
| 7 | Root `.env` | **Missing** |
| 8 | Frontend `.env.local` | **Missing** |
| 9 | Postgres service | **Missing** (until Docker or native/remote) |
| 10 | Redis service | Optional / **Missing** |
| 11 | Make | Optional / **Missing** |
| 12 | Supabase / market-data / MT5 secrets | As needed / **Missing** |

---

*Generated by local infrastructure inspection only. No project source files were modified except this checklist.*
