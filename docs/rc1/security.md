# RC1 — Security status

## Verified

| Control | Status |
| --- | --- |
| JWT auth on API | Present (`AdminUser` / auth deps) |
| Auth rate limiting | `AuthRateLimitMiddleware` |
| Security headers | `SecurityHeaders` + Next.js headers |
| CORS / TrustedHost | Configured in `app/main.py` |
| Audit payload sanitization | Strips password/token/secret keys |
| Gateway tokens | Server-side only; never in browser |
| `execution_audits` RLS | Forced + 2 policies on production |
| Unique stage chain | `(user_id, request_id, stage)` |
| Anon EXECUTE on SECURITY DEFINER helpers | Revoked (`rls_auto_enable`, RLS helpers) |

## Remaining

| Item | Notes |
| --- | --- |
| ITE tables RLS enabled without policies | INFO advisors — deny-all until policies added |
| Authenticated EXECUTE WARN on RLS helpers | Expected for policy evaluation |
| Leaked password protection | Enable in Supabase Auth dashboard |
| CSRF | API is Bearer JWT; classic CSRF not applicable to same pattern |

## Secrets rule

Never commit `.env`, service-role keys, or gateway tokens. Audits redacted at write time.
