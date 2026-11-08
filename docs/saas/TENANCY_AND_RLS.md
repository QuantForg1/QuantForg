# Customer isolation (tenancy) status

## Enforced today

- Application users map to `public.users` with `auth_user_id` → Supabase Auth.
- RLS helpers (`current_app_user_id`) scope licenses, trading accounts, sessions, orders, positions, notifications, profiles, and broker account rows to the owning user.
- Organization membership tables exist with member/admin policies for team surfaces.
- MT5 session guard logic prevents cross-tenant terminal reuse in application services.

## Gaps / required infrastructure (do not shortcut)

1. Most trading tables isolate by **user_id**, not `organization_id`. Org desks are RBAC/membership, not a full org-scoped trading ledger.
2. Independent customer MT5 accounts require each customer to connect **their own** broker credentials through existing secure flows — never share one LIVE terminal across unrelated customers.
3. If multi-tenant LIVE execution on shared host infrastructure is required, additional gateway isolation must be designed and approved — insecure shortcuts are forbidden.

## Product rule

Never expose another customer’s MT5 account, credentials, positions, trades, balance, or history. Authorization checks belong on the server; UI hiding is insufficient.
