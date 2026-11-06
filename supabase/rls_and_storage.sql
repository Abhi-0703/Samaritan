-- Samaritan: lock the database and the audio bucket down (plan.md Phase 3).
-- Run once in the Supabase SQL editor, after the Alembic migrations have created the tables.
-- Safe to run again.
--
-- The API connects with the database owner role and the service-role key, both of which bypass these rules.
-- The anon and authenticated roles (the keys that can end up in a browser) get nothing: row level security is on
-- for every table and no policy lets them in, and their table privileges are removed as a second lock.

-- 1. Row level security on every table in the public schema, including ones added later by migrations
--    (run this file again after adding tables).
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
end $$;

-- 2. No privileges for the browser-facing roles, now and for tables created later.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;

-- 3. A private bucket for call audio. Files are only reachable through the short-lived signed URLs the API creates.
--    25 MB matches MAX_UPLOAD_MB. storage.objects already has row level security on and no policies for anon.
insert into storage.buckets (id, name, public, file_size_limit)
values ('call-audio', 'call-audio', false, 26214400)
on conflict (id) do update set public = false, file_size_limit = 26214400;
