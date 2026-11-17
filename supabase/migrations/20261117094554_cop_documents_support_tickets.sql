-- Durable store for customer-operations documents (support tickets first).
-- Tickets were written to the container filesystem and lost on every deploy
-- (Railway service has no volume; 17 Nov 2026). Server-side only: RLS on,
-- no client grants (client table access was revoked on 17 Nov).
CREATE TABLE IF NOT EXISTS public.cop_documents (
  collection text NOT NULL,
  id text NOT NULL,
  doc jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS cop_documents_collection_created_idx
  ON public.cop_documents (collection, created_at);
ALTER TABLE public.cop_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.cop_documents FROM anon, authenticated;
