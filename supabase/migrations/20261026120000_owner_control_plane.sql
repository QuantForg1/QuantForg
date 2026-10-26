-- Owner control plane: versioned runtime policy and self-service role lock.
-- Direct/service connections may change roles. Authenticated JWTs may not.

CREATE TABLE IF NOT EXISTS public.trading_runtime_config (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version INTEGER NOT NULL CHECK (version >= 1),
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID
);

COMMENT ON TABLE public.trading_runtime_config IS
  'Singleton versioned trading policy. Worker reads this row. '
  'Hard caps stay in application code.';

ALTER TABLE public.trading_runtime_config ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.trading_runtime_config FROM anon, authenticated;
GRANT ALL ON TABLE public.trading_runtime_config TO service_role;

CREATE OR REPLACE FUNCTION public.forbid_self_service_role_change()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  jwt_role text;
BEGIN
  jwt_role := current_setting('request.jwt.claim.role', true);
  IF jwt_role IS NULL OR jwt_role = '' OR jwt_role = 'service_role' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.role IS NOT DISTINCT FROM OLD.role THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'INSERT' AND NEW.role IN ('trader', 'viewer', 'support') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'role_change_forbidden' USING ERRCODE = '42501';
END;
$fn$;

DROP TRIGGER IF EXISTS users_forbid_self_service_role_change ON public.users;
CREATE TRIGGER users_forbid_self_service_role_change
  BEFORE INSERT OR UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.forbid_self_service_role_change();
