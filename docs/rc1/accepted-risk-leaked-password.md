# Accepted Operational Risk — Leaked Password Protection

**Status:** Accepted Operational Risk  
**Date:** 2026-07-20  
**Project:** QuantForg Supabase `otqyhlmwaifokrczryrc` (eu-central-1)  
**Organization plan:** **Free** (verified via Supabase MCP `get_organization`)

## Finding

Supabase Auth advisor `auth_leaked_password_protection` reports leaked-password protection is **disabled**.

Per Supabase docs: leaked password protection is available on the **Pro Plan and above**.

This organization plan is **Free**. The feature **cannot be enabled** on the current plan.

## Decision

Do not leave this ambiguous.

| Field | Value |
| --- | --- |
| Classification | Accepted Operational Risk |
| Critical release blocker? | No — formally accepted for V1.0 on Free plan |
| Residual risk | Users may register/reuse passwords present in HaveIBeenPwned corpora |
| Impact | Elevated credential-stuffing risk on email/password accounts |
| Mitigation | Auth rate limits; JWT sessions; bcrypt hashing; upgrade to Pro + enable HIBP when budget allows |
| Owner | QuantForg platform owner (Supabase org admin) |
| Revisit trigger | Upgrade to Supabase Pro or higher |
