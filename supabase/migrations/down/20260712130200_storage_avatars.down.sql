-- DOWN: 20260712130200_storage_avatars
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'storage' AND table_name = 'objects'
  ) THEN
    DROP POLICY IF EXISTS avatars_delete_own ON storage.objects;
    DROP POLICY IF EXISTS avatars_update_own ON storage.objects;
    DROP POLICY IF EXISTS avatars_insert_own ON storage.objects;
    DROP POLICY IF EXISTS avatars_select_own ON storage.objects;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'storage' AND table_name = 'buckets'
  ) THEN
    DELETE FROM storage.objects WHERE bucket_id = 'avatars';
    DELETE FROM storage.buckets WHERE id = 'avatars';
  END IF;
END $$;
