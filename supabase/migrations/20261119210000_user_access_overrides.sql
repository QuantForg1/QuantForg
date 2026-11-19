-- Admin per-user feature access overrides (absent row = default access).
create table if not exists public.user_access_overrides (
  user_id uuid not null references public.users(id) on delete cascade,
  feature text not null check (feature in ('robot_trading','signals','ai_assistant','broker_connect')),
  allowed boolean not null,
  reason text not null default '' check (length(reason) <= 500),
  set_by uuid references public.users(id) on delete set null,
  updated_at timestamptz not null default now(),
  primary key (user_id, feature)
);
alter table public.user_access_overrides enable row level security;
comment on table public.user_access_overrides is 'Admin per-user feature access overrides (absent row = default access). Server-side only.';
