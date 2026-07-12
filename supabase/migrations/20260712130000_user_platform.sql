-- =============================================================================
-- QuantForg migration: User Platform tables
-- Version: 20260712130000
-- Reversible: see supabase/migrations/down/20260712130000_user_platform.down.sql
-- Depends on: public.users, public.set_updated_at, public.forbid_mutation
-- =============================================================================

-- ---------------------------------------------------------------------------
-- user_profiles (1:1 with users — not an auth identity table)
-- ---------------------------------------------------------------------------
CREATE TABLE public.user_profiles (
  user_id              uuid PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
  avatar_url           text NOT NULL DEFAULT '',
  avatar_path          text NOT NULL DEFAULT '',
  full_name            text NOT NULL DEFAULT '',
  username             text,
  bio                  text NOT NULL DEFAULT '' CHECK (length(bio) <= 1000),
  country_code         char(2),
  timezone             text NOT NULL DEFAULT 'UTC',
  preferred_language   text NOT NULL DEFAULT 'en' CHECK (length(preferred_language) BETWEEN 2 AND 16),
  trading_experience   text NOT NULL DEFAULT 'beginner'
                         CHECK (trading_experience IN (
                           'beginner', 'intermediate', 'advanced', 'professional'
                         )),
  risk_level           text NOT NULL DEFAULT 'moderate'
                         CHECK (risk_level IN (
                           'conservative', 'moderate', 'aggressive', 'custom'
                         )),
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT user_profiles_username_format CHECK (
    username IS NULL OR username ~ '^[a-zA-Z0-9_]{3,32}$'
  ),
  CONSTRAINT user_profiles_country_format CHECK (
    country_code IS NULL OR country_code ~ '^[A-Z]{2}$'
  )
);

CREATE UNIQUE INDEX user_profiles_username_uidx
  ON public.user_profiles (lower(username))
  WHERE username IS NOT NULL;

CREATE TRIGGER user_profiles_set_updated_at
  BEFORE UPDATE ON public.user_profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.user_profiles IS
  'Extended profile for a platform user (not Supabase Auth identity).';

-- ---------------------------------------------------------------------------
-- user_settings
-- ---------------------------------------------------------------------------
CREATE TABLE public.user_settings (
  user_id                    uuid PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
  theme                      text NOT NULL DEFAULT 'system'
                               CHECK (theme IN ('light', 'dark', 'system')),
  notifications_enabled      boolean NOT NULL DEFAULT true,
  email_marketing            boolean NOT NULL DEFAULT false,
  email_security             boolean NOT NULL DEFAULT true,
  email_product              boolean NOT NULL DEFAULT true,
  security_login_alerts      boolean NOT NULL DEFAULT true,
  security_require_reauth    boolean NOT NULL DEFAULT false,
  session_timeout_minutes    integer NOT NULL DEFAULT 10080
                               CHECK (session_timeout_minutes BETWEEN 5 AND 525600),
  created_at                 timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at                 timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TRIGGER user_settings_set_updated_at
  BEFORE UPDATE ON public.user_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.user_settings IS 'Per-user UI, email, and security preferences.';

-- ---------------------------------------------------------------------------
-- user_devices / user_sessions (settings: connected devices & active sessions)
-- ---------------------------------------------------------------------------
CREATE TABLE public.user_devices (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  device_label    text NOT NULL DEFAULT '',
  user_agent      text NOT NULL DEFAULT '' CHECK (length(user_agent) <= 512),
  last_seen_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX user_devices_user_id_idx ON public.user_devices (user_id);

CREATE TRIGGER user_devices_set_updated_at
  BEFORE UPDATE ON public.user_devices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.user_sessions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  device_id        uuid REFERENCES public.user_devices (id) ON DELETE SET NULL,
  ip_address       text NOT NULL DEFAULT '',
  user_agent       text NOT NULL DEFAULT '' CHECK (length(user_agent) <= 512),
  is_active        boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  last_active_at   timestamptz NOT NULL DEFAULT timezone('utc', now()),
  revoked_at       timestamptz,
  updated_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT user_sessions_revoked_consistency CHECK (
    (is_active = false AND revoked_at IS NOT NULL)
    OR (is_active = true AND revoked_at IS NULL)
  )
);

CREATE INDEX user_sessions_user_id_idx ON public.user_sessions (user_id);
CREATE INDEX user_sessions_active_idx ON public.user_sessions (user_id)
  WHERE is_active;

CREATE TRIGGER user_sessions_set_updated_at
  BEFORE UPDATE ON public.user_sessions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
CREATE TABLE public.organizations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL CHECK (length(trim(name)) > 0),
  slug            text NOT NULL CHECK (length(trim(slug)) > 0),
  org_type        text NOT NULL DEFAULT 'personal'
                    CHECK (org_type IN ('personal', 'team')),
  owner_user_id   uuid NOT NULL REFERENCES public.users (id) ON DELETE RESTRICT,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX organizations_slug_uidx ON public.organizations (lower(slug));
CREATE INDEX organizations_owner_idx ON public.organizations (owner_user_id);

CREATE TRIGGER organizations_set_updated_at
  BEFORE UPDATE ON public.organizations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.organization_members (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   uuid NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  user_id           uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  role              text NOT NULL DEFAULT 'member'
                      CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  status            text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'invited', 'suspended', 'left')),
  joined_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT organization_members_unique UNIQUE (organization_id, user_id)
);

CREATE INDEX organization_members_user_idx ON public.organization_members (user_id);

CREATE TRIGGER organization_members_set_updated_at
  BEFORE UPDATE ON public.organization_members
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.organization_invitations (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   uuid NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  email             text NOT NULL CHECK (length(trim(email)) > 0),
  role              text NOT NULL DEFAULT 'member'
                      CHECK (role IN ('admin', 'member', 'viewer')),
  invited_by        uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  token_hash        text NOT NULL CHECK (length(token_hash) >= 32),
  status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
  expires_at        timestamptz NOT NULL,
  accepted_at       timestamptz,
  created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at        timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX organization_invitations_org_idx
  ON public.organization_invitations (organization_id);
CREATE UNIQUE INDEX organization_invitations_pending_email_uidx
  ON public.organization_invitations (organization_id, lower(email))
  WHERE status = 'pending';

CREATE TRIGGER organization_invitations_set_updated_at
  BEFORE UPDATE ON public.organization_invitations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- activity_events (Activity Center — append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE public.activity_events (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  category      text NOT NULL
                  CHECK (category IN ('login', 'security', 'profile', 'api', 'organization')),
  action        text NOT NULL CHECK (length(trim(action)) > 0 AND length(action) <= 64),
  message       text NOT NULL DEFAULT '' CHECK (length(message) <= 1000),
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  ip_address    text NOT NULL DEFAULT '',
  user_agent    text NOT NULL DEFAULT '' CHECK (length(user_agent) <= 512),
  created_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at    timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX activity_events_user_idx ON public.activity_events (user_id, created_at DESC);
CREATE INDEX activity_events_category_idx ON public.activity_events (user_id, category);

CREATE TRIGGER activity_events_forbid_update
  BEFORE UPDATE ON public.activity_events
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

CREATE TRIGGER activity_events_forbid_delete
  BEFORE DELETE ON public.activity_events
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

-- ---------------------------------------------------------------------------
-- notifications + preferences
-- ---------------------------------------------------------------------------
CREATE TABLE public.notifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  category      text NOT NULL
                  CHECK (category IN (
                    'system', 'security', 'organization', 'trading', 'product'
                  )),
  title         text NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= 200),
  body          text NOT NULL DEFAULT '' CHECK (length(body) <= 2000),
  is_read       boolean NOT NULL DEFAULT false,
  read_at       timestamptz,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT notifications_read_consistency CHECK (
    (is_read = true AND read_at IS NOT NULL)
    OR (is_read = false AND read_at IS NULL)
  )
);

CREATE INDEX notifications_user_idx ON public.notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON public.notifications (user_id)
  WHERE is_read = false;

CREATE TRIGGER notifications_set_updated_at
  BEFORE UPDATE ON public.notifications
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.notification_preferences (
  user_id     uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  category    text NOT NULL
                CHECK (category IN (
                  'system', 'security', 'organization', 'trading', 'product'
                )),
  in_app      boolean NOT NULL DEFAULT true,
  email       boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  PRIMARY KEY (user_id, category)
);

CREATE TRIGGER notification_preferences_set_updated_at
  BEFORE UPDATE ON public.notification_preferences
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- storage_objects (avatar / profile asset metadata; files in Supabase Storage)
-- ---------------------------------------------------------------------------
CREATE TABLE public.storage_objects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  bucket          text NOT NULL DEFAULT 'avatars',
  object_path     text NOT NULL CHECK (length(trim(object_path)) > 0),
  content_type    text NOT NULL DEFAULT 'application/octet-stream',
  size_bytes      bigint NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
  purpose         text NOT NULL DEFAULT 'avatar'
                    CHECK (purpose IN ('avatar', 'profile_asset')),
  public_url      text NOT NULL DEFAULT '',
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT storage_objects_bucket_path_uidx UNIQUE (bucket, object_path)
);

CREATE INDEX storage_objects_user_idx ON public.storage_objects (user_id);

CREATE TRIGGER storage_objects_set_updated_at
  BEFORE UPDATE ON public.storage_objects
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
