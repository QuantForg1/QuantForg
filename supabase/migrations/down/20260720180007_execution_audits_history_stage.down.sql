-- Rollback: restore stage check without history
ALTER TABLE public.execution_audits
  DROP CONSTRAINT IF EXISTS execution_audits_stage_check;

ALTER TABLE public.execution_audits
  ADD CONSTRAINT execution_audits_stage_check CHECK (
    stage IN (
      'validation',
      'risk',
      'safety',
      'submit',
      'manage',
      'cancel',
      'replay'
    )
  );
