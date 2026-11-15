-- Application-managed MFA recovery codes (hashed only).
-- Access is backend/service-role only; no public Data API exposure.

create table if not exists public.auth_mfa_recovery_codes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  code_hash text not null,
  created_at timestamptz not null default timezone('utc', now()),
  used_at timestamptz null,
  constraint auth_mfa_recovery_codes_hash_unique unique (user_id, code_hash)
);

create index if not exists auth_mfa_recovery_codes_user_idx
  on public.auth_mfa_recovery_codes (user_id);

alter table public.auth_mfa_recovery_codes enable row level security;

-- Deny all for anon/authenticated; service role bypasses RLS.
drop policy if exists "auth_mfa_recovery_codes_deny_all" on public.auth_mfa_recovery_codes;
create policy "auth_mfa_recovery_codes_deny_all"
  on public.auth_mfa_recovery_codes
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

revoke all on table public.auth_mfa_recovery_codes from anon, authenticated;
grant select, insert, update, delete on table public.auth_mfa_recovery_codes to service_role;
