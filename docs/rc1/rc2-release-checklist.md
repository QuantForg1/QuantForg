# RC2 Production Release Checklist

Baseline RC1: `0a3ee7d`. Certification commit message: `RC2 final certification`.

## 1. Execution audit lifecycle

| Item | Mark | Evidence |
| --- | --- | --- |
| validation stage wired | PASS | validation use case |
| risk stage wired | PASS | risk engine |
| safety stage wired | PASS | execution safety |
| submit stage wired | PASS | SubmitExecutionUseCase |
| manage stage wired | PASS | manage → `audit_stage=manage` |
| cancel stage wired | PASS | CancelExecutionUseCase + DI |
| history stage wired | PASS | success → HISTORY |
| replay stage wired | PASS | idempotent replay |
| unique (user,request,stage) | PASS | DB unique index |
| history CHECK on production | PASS | constraint includes `history` |

## 2. Supabase security

| Item | Mark | Evidence |
| --- | --- | --- |
| execution_audits RLS + policies | PASS | forced RLS |
| ITE RLS deny policies | PASS | 46 policies; 0 tables RLS-without-policy |
| Anon EXECUTE revoked on definer helpers | PASS | RC1 |
| JWT / roles | PASS | API JWT; service_role backend |
| Secrets redaction in audits | PASS | sanitize_payload |
| Authenticated EXECUTE on RLS helpers | WARN | needed for RLS; advisor WARN remains |
| Leaked-password protection | WARN | **Accepted Operational Risk** on Free plan — see accepted-risk-leaked-password.md |

## 3. CI / quality

| Item | Mark | Evidence |
| --- | --- | --- |
| Unit tests (full marker suite) | PASS | 615 passed, cov 71.81% |
| Frontend lint / typecheck / build | PASS | exit 0 |
| Frontend job added to CI workflow | PASS | `.github/workflows/ci.yml` |
| Our changed files ruff/black/mypy | PASS | green |
| Full repo ruff/black on risk_engine | WARN | pre-existing E501 / black drift reported locally |
| Integration tests (local) | FAIL | asyncpg missing in local venv; Redis not running |
| Integration tests (GitHub Actions services) | WARN | not verified in this session — confirm after push |
| tzdata dependency | PASS | added for Windows/IANA zones |

## 4. Performance

| Item | Mark | Evidence |
| --- | --- | --- |
| Latency instrumentation | PASS | audits + probes |
| Production CPU/memory/RUM/pg_stat profile | WARN | see `performance-report.md` |

## 5. Device certification

| Item | Mark | Evidence |
| --- | --- | --- |
| Mobile CSS + dialog + data-desk | PASS | globals, dialog, app-shell |
| Physical/device lab matrix | WARN | not executed on hardware |

## 6. Operations

| Item | Mark | Evidence |
| --- | --- | --- |
| Frontend www.quantforg.com | PASS | HTTP 200 |
| Railway `/health` + `/api/v1/health` | PASS | HTTP 200 |
| api.quantforg.com | PASS | Retired (NXDOMAIN); Railway is canonical — see api-hostname.md |
| Gateway / MT5 / Cloudflare live from here | WARN | not probed with gateway URL this pass |
| `/ops/rc1-telemetry` code path | PASS | shipped |
| Execution / reject telemetry | PASS | telemetry aggregates |

## Gate decision

**Critical FAIL remaining:** Supabase leaked-password protection disabled.

**Additional note:** `api.quantforg.com` is retired (NXDOMAIN). Railway is the canonical API. Leaked-password is Accepted Operational Risk on Free plan.
