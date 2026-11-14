# Phase 2 UI release verification + P7 preference identity resolution

**Date (UTC):** 2026-11-14  
**Status:** CLOSED — no preference data mutation required  
**`origin/main` tip:** `55b8513def133536d22fa50760bbd9d64313582d` (PR #252)

## 1. Production source alignment

| Surface | Expected | Observed | Result |
|---|---|---|---|
| GitHub `main` | PR #252 merge | `55b8513d` | PASS |
| Vercel Production – frontend | same frontend source as `main` | GH deployment `7786566309` → SHA `55b8513d`, state **success** | PASS |
| Railway API `/api/v1/version` | latest **backend** commit on `main` | `git_commit=1e75cdf371fb` (PR #249) | PASS |
| Backend delta `1e75cdf3..55b8513d` | none if frontend-only follow-ups | frontend-only (#252); #250/#251 already ancestors of #249 merge line | PASS |
| `/health/live` | 200 | 200 `{"status":"ok"}` | PASS |
| `/health/ready` | 200 | 200 routers complete (108) | PASS |
| `www.quantforg.com` / `/login` | 200 | 200 / 200 | PASS |

CI on `main` @ `55b8513d`: success (`43587202467`).

## 2. Phase 2 acceptance (prior — not re-run)

- Customer post-PR #252 suite: **PASS** (History route, 390/768/1440 shell).
- Owner/Admin suite (Overview → Settings): **PASS** (read-only; LIVE submit off; Policy v16 visible unchanged).

## 3. P7 Risk Preference discrepancy — root cause

### Internal evidence (no secrets)

| Source | Identity | Preference |
|---|---|---|
| Phase 5.1 prod probe `phase51_prod_probe.json` | `user_prefix=7d31c808` | `planned=10.0000`, `source=user_edit` |
| Phase 4.1 closure | P7 save on Owner session | `persisted=true`, `10.0000` |
| Live Owner session 2026-11-14 | `7d31c808-1670-4604-867b-0d4a2bc9e078` · `p7provider@gmail.com` · `role=owner` | `planned_risk_pct=10.0000`, `persisted=true`, `source=user_edit`, `updated_at=2026-11-10 17:12:20+00` |
| Later Customer acceptance session | `8ae4b619-…` · `role=trader` | `planned_risk_pct=20.0`, `persisted=false`, `source=default_copy`, empty preference history |

### Conclusion

**Different accounts.** The historical 10% `user_edit` row belongs to the Owner P7 PROVIDER identity (`7d31c808…`). The trader session (`8ae4b619…`) correctly received the unpersisted platform default copy (ceiling-derived 20%). Empty history on the trader is expected when no `user_risk_settings` row exists for that user.

**Not caused by:** RLS leak, API remapping bug, overwritten Owner prefs, or Owner Policy drift.

### Actions taken / not taken

| Action | Decision |
|---|---|
| Write 10% onto trader `8ae4b619…` | **Rejected** — would invent a preference the customer never saved |
| Change Owner Policy / global ceilings | **Rejected** — Policy v16 intact |
| Mutate Owner `user_risk_settings` | **Rejected** — already correct at 10% |
| Code fix | **None required** — identity mismatch only |
| Data migration | **None** |

## 4. Safety invariants (reconfirmed read-only)

```text
MULTI_ACCOUNT LIVE submit / dispatch remain OFF (Admin multi-account: LIVE SUBMIT OFF)
Owner Policy v16 unchanged
Weltrade LIVE singleton / OMS paths not modified by this docs release
No trades submitted
```

## 5. Next documented phase

See `docs/architecture/MULTI_ACCOUNT_PHASE11_CHECKLIST.md` (demo auth + staging dispatch) and open docs PR for eight-broker LIVE acceptance evidence. Phase 11 execution remains **blocked** until Owner supplies protected `QF_DEMO_*` (or verified LIVE creds per broker) and written staging-dispatch approval. Do not enable multi-account LIVE without those prerequisites.
