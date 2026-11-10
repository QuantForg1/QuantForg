-- Read-only Live Market Chat schema audit (safe on production).
SELECT 'tables' AS section, c.relname AS name, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('live_market_chat_messages', 'live_market_chat_reports')
ORDER BY 2;

SELECT 'columns' AS section, table_name AS name, column_name || ' ' || data_type AS detail
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('live_market_chat_messages', 'live_market_chat_reports')
ORDER BY table_name, ordinal_position;

SELECT 'indexes' AS section, tablename AS name, indexname AS detail
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('live_market_chat_messages', 'live_market_chat_reports')
ORDER BY 2, 3;

SELECT 'policies' AS section, tablename AS name, policyname || ' cmd=' || cmd AS detail
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('live_market_chat_messages', 'live_market_chat_reports')
ORDER BY 2, 3;

SELECT 'grants' AS section, table_name AS name, grantee || ':' || privilege_type AS detail
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('live_market_chat_messages', 'live_market_chat_reports')
  AND grantee IN ('anon', 'authenticated', 'service_role')
ORDER BY 2, 3;

SELECT 'realtime' AS section, tablename AS name, 'in_supabase_realtime' AS detail
FROM pg_publication_tables
WHERE pubname = 'supabase_realtime'
  AND schemaname = 'public'
  AND tablename = 'live_market_chat_messages';

SELECT 'triggers' AS section, event_object_table AS name, trigger_name AS detail
FROM information_schema.triggers
WHERE event_object_schema = 'public'
  AND event_object_table IN ('live_market_chat_messages', 'live_market_chat_reports')
ORDER BY 2, 3;

SELECT 'migration_history' AS section, version AS name, name AS detail
FROM supabase_migrations.schema_migrations
WHERE version LIKE '20261110%'
   OR name ILIKE '%live_market_chat%'
ORDER BY version;
