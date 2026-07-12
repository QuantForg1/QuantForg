# DATABASE_VERIFICATION_REPORT

**Status:** PASSED
**Date:** 2026-07-12
**Project:** `otqyhlmwaifokrczryrc`
**Apply method:** `supabase db push` (session pooler)

## Migrations

| Version | Remote |
|--------:|:------:|
| `20260712120000` | applied |
| `20260712120100` | applied |
| `20260712120200` | applied |
| `20260712130000` | applied |
| `20260712130100` | applied |
| `20260712130200` | applied |

**Pending migrations:** none

Newly applied in this finalize run:

- `20260712130000_user_platform.sql`
- `20260712130100_user_platform_rls.sql`
- `20260712130200_storage_avatars.sql`

## Platform tables (11/11)

- `activity_events`
- `notification_preferences`
- `notifications`
- `organization_invitations`
- `organization_members`
- `organizations`
- `storage_objects`
- `user_devices`
- `user_profiles`
- `user_sessions`
- `user_settings`

## RLS

All platform tables RLS enabled + forced: **True**

| Table | Enabled | Forced |
|-------|:-------:|:------:|
| `activity_events` | True | True |
| `notification_preferences` | True | True |
| `notifications` | True | True |
| `organization_invitations` | True | True |
| `organization_members` | True | True |
| `organizations` | True | True |
| `storage_objects` | True | True |
| `user_devices` | True | True |
| `user_profiles` | True | True |
| `user_sessions` | True | True |
| `user_settings` | True | True |

## Policies (26)

**activity_events** (2)
- `activity_events_insert_own`
- `activity_events_select_own`

**notification_preferences** (1)
- `notification_preferences_all_own`

**notifications** (3)
- `notifications_insert_own`
- `notifications_select_own`
- `notifications_update_own`

**organization_invitations** (3)
- `organization_invitations_insert_admin`
- `organization_invitations_select`
- `organization_invitations_update_admin`

**organization_members** (3)
- `organization_members_insert_admin`
- `organization_members_select`
- `organization_members_update_admin`

**organizations** (3)
- `organizations_insert_owner`
- `organizations_select_member`
- `organizations_update_admin`

**storage_objects** (1)
- `storage_objects_all_own`

**user_devices** (1)
- `user_devices_all_own`

**user_profiles** (3)
- `user_profiles_insert_own`
- `user_profiles_select_own`
- `user_profiles_update_own`

**user_sessions** (3)
- `user_sessions_insert_own`
- `user_sessions_select_own`
- `user_sessions_update_own`

**user_settings** (3)
- `user_settings_insert_own`
- `user_settings_select_own`
- `user_settings_update_own`

## Indexes (27)

**activity_events** (3)
- `activity_events_category_idx`
- `activity_events_pkey`
- `activity_events_user_idx`

**notification_preferences** (1)
- `notification_preferences_pkey`

**notifications** (3)
- `notifications_pkey`
- `notifications_unread_idx`
- `notifications_user_idx`

**organization_invitations** (3)
- `organization_invitations_org_idx`
- `organization_invitations_pending_email_uidx`
- `organization_invitations_pkey`

**organization_members** (3)
- `organization_members_pkey`
- `organization_members_unique`
- `organization_members_user_idx`

**organizations** (3)
- `organizations_owner_idx`
- `organizations_pkey`
- `organizations_slug_uidx`

**storage_objects** (3)
- `storage_objects_bucket_path_uidx`
- `storage_objects_pkey`
- `storage_objects_user_idx`

**user_devices** (2)
- `user_devices_pkey`
- `user_devices_user_id_idx`

**user_profiles** (2)
- `user_profiles_pkey`
- `user_profiles_username_uidx`

**user_sessions** (3)
- `user_sessions_active_idx`
- `user_sessions_pkey`
- `user_sessions_user_id_idx`

**user_settings** (1)
- `user_settings_pkey`

## Triggers (12)

**activity_events**
- `activity_events_forbid_delete (DELETE)`
- `activity_events_forbid_update (UPDATE)`

**notification_preferences**
- `notification_preferences_set_updated_at (UPDATE)`

**notifications**
- `notifications_set_updated_at (UPDATE)`

**organization_invitations**
- `organization_invitations_set_updated_at (UPDATE)`

**organization_members**
- `organization_members_set_updated_at (UPDATE)`

**organizations**
- `organizations_set_updated_at (UPDATE)`

**storage_objects**
- `storage_objects_set_updated_at (UPDATE)`

**user_devices**
- `user_devices_set_updated_at (UPDATE)`

**user_profiles**
- `user_profiles_set_updated_at (UPDATE)`

**user_sessions**
- `user_sessions_set_updated_at (UPDATE)`

**user_settings**
- `user_settings_set_updated_at (UPDATE)`

## Constraints

- Primary keys: 11
- Foreign keys: 14
- Unique: 2
- Check: 129
- Total inventoried: 156

## Helper functions

- `public.current_app_user_id()`
- `public.forbid_mutation()`
- `public.is_org_admin()`
- `public.is_org_member()`
- `public.set_updated_at()`

## Storage

Avatars bucket: `[{'id': 'avatars', 'public': False}]`

## Verdict

| Check | Result |
|-------|--------|
| Migrations applied (6/6) | PASS |
| Pending migrations | PASS (none) |
| Platform tables | PASS (11/11) |
| RLS enabled+forced | PASS |
| Policies | PASS (26) |
| Indexes | PASS (27) |
| Triggers | PASS (12) |
| Constraints | PASS (156) |
| Private avatars bucket | PASS |
