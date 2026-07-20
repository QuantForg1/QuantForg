# RC1 — Production Checklist

Baseline: `17d5f83`. Hardening commit message: `Release candidate hardening`.

## Database

- [x] `execution_audits` present on production
- [x] Indexes (incl. unique `(user_id, request_id, stage)`)
- [x] RLS forced + policies
- [x] Rollback scripts under `supabase/migrations/down/`
- [x] Anon EXECUTE revoked on `rls_auto_enable` + RLS helpers

## Audit integrity

- [x] Idempotent insert (memory + Postgres `ON CONFLICT DO NOTHING`)
- [x] Stages wired: validation, risk, safety, submit, replay
- [ ] manage/cancel hooks (reserved — Remaining)
- [ ] Close/History as audit stages (use Journal — Remaining by design)

## Ops

- [x] `/ops/rc1-telemetry` + UI panel
- [x] Alerts from live thresholds
- [x] Daily P/L explicitly Not available

## Client

- [x] Mobile CSS certification pass (overflow, touch, dialogs, focus)
- [ ] Full device lab matrix (Remaining — visual QA)

## Security

- [x] Payload secret sanitization in audits
- [x] Auth rate limit middleware
- [ ] Supabase leaked-password protection enable (dashboard — Remaining)
- [ ] ITE tables RLS-without-policy INFO advisories (Remaining)

## Quality gate

- [x] Frontend typecheck / lint / build green (RC1 hardening)
- [x] Targeted unit tests (`execution_audit`, `rc1_ops_telemetry`) green
- [ ] Full backend + integration suite in CI (confirm on push)

## Docs

- [x] `docs/rc1/*` Architecture, API, Gateway, Deployment, Recovery, Runbooks, Operations, this checklist
