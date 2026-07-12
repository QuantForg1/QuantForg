-- Storage bucket bootstrap (run via migrations; reversible by deleting bucket metadata)
-- Version: 20260712130200
-- Creates avatars bucket policies documentation as SQL comments.
-- Actual bucket creation uses storage.buckets when Storage schema exists.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'storage' AND table_name = 'buckets'
  ) THEN
    INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
    VALUES (
      'avatars',
      'avatars',
      false,
      5242880,
      ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    )
    ON CONFLICT (id) DO NOTHING;

    -- Authenticated users may manage objects under their auth uid folder only.
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'storage' AND tablename = 'objects'
        AND policyname = 'avatars_select_own'
    ) THEN
      CREATE POLICY avatars_select_own ON storage.objects
        FOR SELECT TO authenticated
        USING (
          bucket_id = 'avatars'
          AND (storage.foldername(name))[1] = auth.uid()::text
        );
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'storage' AND tablename = 'objects'
        AND policyname = 'avatars_insert_own'
    ) THEN
      CREATE POLICY avatars_insert_own ON storage.objects
        FOR INSERT TO authenticated
        WITH CHECK (
          bucket_id = 'avatars'
          AND (storage.foldername(name))[1] = auth.uid()::text
        );
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'storage' AND tablename = 'objects'
        AND policyname = 'avatars_update_own'
    ) THEN
      CREATE POLICY avatars_update_own ON storage.objects
        FOR UPDATE TO authenticated
        USING (
          bucket_id = 'avatars'
          AND (storage.foldername(name))[1] = auth.uid()::text
        )
        WITH CHECK (
          bucket_id = 'avatars'
          AND (storage.foldername(name))[1] = auth.uid()::text
        );
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'storage' AND tablename = 'objects'
        AND policyname = 'avatars_delete_own'
    ) THEN
      CREATE POLICY avatars_delete_own ON storage.objects
        FOR DELETE TO authenticated
        USING (
          bucket_id = 'avatars'
          AND (storage.foldername(name))[1] = auth.uid()::text
        );
    END IF;
  END IF;
END $$;
