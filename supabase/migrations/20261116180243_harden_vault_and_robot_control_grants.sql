-- Broker credential vault: only the backend (owner/service_role) reads or writes.
-- The browser never touches it (no frontend reference); encrypted payloads are
-- not exposed to user JWTs through the REST API.
REVOKE ALL ON TABLE public.broker_credentials FROM anon, authenticated;
-- Robot control: users read their own rows only; writes are backend-only.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.robot_account_controls FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.robot_control_events FROM anon, authenticated;
