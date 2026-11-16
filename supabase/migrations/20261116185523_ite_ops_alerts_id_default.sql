-- Operator alerts were never persisted: id had no default and the writer omits it (every insert 400).
ALTER TABLE public.ite_ops_alerts ALTER COLUMN id SET DEFAULT gen_random_uuid();
