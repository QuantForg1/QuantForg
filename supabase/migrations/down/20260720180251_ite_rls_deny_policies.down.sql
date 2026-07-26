-- Rollback: drop explicit deny policies (RLS remains enabled)
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'ite_certification_approvals',
    'ite_certification_canary_snapshots',
    'ite_certification_certificates',
    'ite_certification_reports',
    'ite_ops_active_config',
    'ite_ops_alerts',
    'ite_ops_audit_log',
    'ite_ops_config_versions',
    'ite_ops_health_snapshots',
    'ite_ops_mode_transitions',
    'ite_reliability_health_snapshots',
    'ite_reliability_heartbeats',
    'ite_reliability_incidents',
    'ite_reliability_metrics_snapshots',
    'ite_reliability_recovery_events',
    'ite_reliability_timeline',
    'ite_reliability_traces',
    'ite_research_monte_carlo',
    'ite_research_optimizations',
    'ite_research_promotions',
    'ite_research_simulations',
    'ite_research_trades',
    'ite_research_walkforward'
  ];
BEGIN
  FOREACH t IN ARRAY tables
  LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON public.%I',
      t || '_authenticated_deny',
      t
    );
    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON public.%I',
      t || '_anon_deny',
      t
    );
  END LOOP;
END $$;
