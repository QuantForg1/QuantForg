-- Community foundation. Client roles cannot read or write these tables.

CREATE TABLE IF NOT EXISTS public.community_profiles (
  user_id uuid PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
  visibility text NOT NULL DEFAULT 'private',
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT community_profiles_visibility_check
    CHECK (visibility IN ('private', 'public'))
);

CREATE TABLE IF NOT EXISTS public.community_posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  body text NOT NULL,
  visibility text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT community_posts_body_check CHECK (char_length(body) BETWEEN 1 AND 2000),
  CONSTRAINT community_posts_visibility_check CHECK (visibility IN ('private', 'public'))
);

CREATE TABLE IF NOT EXISTS public.community_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id uuid NOT NULL REFERENCES public.community_posts (id) ON DELETE CASCADE,
  author_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT community_comments_body_check CHECK (char_length(body) BETWEEN 1 AND 1000)
);

CREATE TABLE IF NOT EXISTS public.community_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  target_type text NOT NULL,
  target_id uuid NOT NULL,
  reason text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  resolved_by uuid REFERENCES public.users (id),
  resolution text,
  CONSTRAINT community_reports_resolution_check
    CHECK (resolution IS NULL OR resolution IN ('removed', 'dismissed')),
  CONSTRAINT community_reports_type_check
    CHECK (target_type IN ('post', 'comment', 'profile')),
  CONSTRAINT community_reports_reason_check CHECK (char_length(reason) BETWEEN 1 AND 500)
);

CREATE INDEX IF NOT EXISTS community_reports_open
  ON public.community_reports (created_at)
  WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS public.community_blocks (
  blocker_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  blocked_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (blocker_id, blocked_id),
  CONSTRAINT community_blocks_no_self CHECK (blocker_id <> blocked_id)
);

CREATE INDEX IF NOT EXISTS community_posts_author_time
  ON public.community_posts (author_id, created_at DESC);

ALTER TABLE public.community_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_blocks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.community_profiles FROM anon, authenticated;
REVOKE ALL ON public.community_posts FROM anon, authenticated;
REVOKE ALL ON public.community_comments FROM anon, authenticated;
REVOKE ALL ON public.community_reports FROM anon, authenticated;
REVOKE ALL ON public.community_blocks FROM anon, authenticated;
