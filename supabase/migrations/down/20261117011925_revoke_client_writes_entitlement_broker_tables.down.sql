-- WARNING: restores the insecure pre-audit grants. Use only for an emergency rollback.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.licenses, public.broker_accounts,
  public.mt5_connections, public.users, public.billing_orders, public.billing_trials,
  public.notifications TO authenticated, anon;
