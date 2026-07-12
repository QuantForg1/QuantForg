# Security

**Release:** QuantForg v1.0.0-rc.1  

## Threat model (RC1 scope)

QuantForg RC1 is an API platform with authentication, broker/MT5 adapters, simulation engines, and observability. **Live trade execution is disabled by default.** Primary risks: credential leakage, auth bypass, injection via API inputs, and accidental execution enablement.

## Controls in place

| Control | Implementation |
|---------|----------------|
| Auth | Supabase-backed email/OAuth flows; session middleware |
| Secrets | `.env` gitignored; `.env.example` placeholders only |
| Production validators | Reject `DEBUG`/`RELOAD` and insecure `SECRET_KEY` / DB passwords when `APP_ENV=production` |
| Credential encryption | `core/security/credential_encryption.py` with key versioning |
| Security headers | `SecurityHeaders` middleware |
| Host / CORS | `TrustedHostMiddleware`, configurable CORS origins |
| RLS | Supabase SQL policies on domain and ops tables |
| Execution gate | `EXECUTION_ENABLED=false` default; MT5 adapter refuses live send when disabled |
| Audit trail | Append-oriented `audit_logs` + Audit Center |

## Secret handling

- Never commit `.env`, service role keys, or MT5 passwords.  
- Rotate `SECRET_KEY` and credential encryption keys on schedule.  
- Prefer Supabase service role only on trusted backend paths.  
- CI uses disposable test secrets only.

## Dependency posture

- Poetry-managed runtime: FastAPI, Pydantic v2, SQLAlchemy asyncio, asyncpg, Redis, Supabase, cryptography.  
- Dev tooling: ruff (includes bandit `S` rules), mypy, pytest.  
- **Known gap:** `poetry.lock` not committed — pin for GA to freeze the SBOM.  
- Dual `httpx` / `httpx2` present — consolidate before GA.

## RC1 audit snapshot

- No `TODO`/`FIXME` markers in `app/`, `core/`, `tests/`, `scripts/`.  
- No hardcoded cloud API keys or PEM private keys found in source.  
- Default dev passwords exist in settings/Compose — blocked in production env validation.

## Explicitly out of scope (RC1)

- Enabling live execution  
- AI model endpoints or data exfiltration via AI advisors  
- Hardening for multi-tenant public SaaS beyond current RLS  

## Incident pointers

See `BACKUP_RECOVERY.md` for backup/restore and incident response steps. Report vulnerabilities privately to engineering (do not open public issues with secrets).
