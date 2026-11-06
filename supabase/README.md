# Supabase setup (Phase 3)

Samaritan keeps its data in Supabase Postgres and its call audio in a private Supabase Storage bucket. The API code is the same as locally; only `DATABASE_URL` and `STORAGE_BACKEND` change. Nothing in this folder runs by itself: you create the project, and the commands below are run by hand.

## 1. Create the project (you)

1. At supabase.com, create a project on the free plan. Prefer the region **Mumbai (ap-south-1)**. Save the database password somewhere safe.
2. In the project, open **Connect** and copy the **Session pooler** connection string (port 5432). Render's free tier is IPv4 only, and the direct connection is IPv6 only, so use the pooler string. Replace `[YOUR-PASSWORD]` with the real password.
3. From **Project Settings > API**, copy the project URL and the **service_role** key. The service-role key can read and write everything, so it goes only into `api/.env` and the host's environment variables, never into the web app or git.

## 2. Fill in `api/.env`

```
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
SUPABASE_BUCKET=call-audio
```

The code adds the right driver and turns off prepared statements, which the pooler does not support in transaction mode. Check the exact host in the Connect dialog; the `aws-0` part differs between projects.

## 3. Create the tables, then lock everything down

From the repository root, with the API's virtualenv:

```bash
cd api && .venv/bin/python -m app.migrate
```

Then paste `supabase/rls_and_storage.sql` into the Supabase **SQL editor** and run it. It turns on row level security for every table with no policies, removes the `anon` and `authenticated` roles' privileges, and creates the private `call-audio` bucket. Running it twice is harmless. Run it again after any migration that adds a table.

## 4. Put data in (only after you approve each step)

Every script below is a dry run until you add `--yes`, and prints where it would write.

```bash
api/.venv/bin/python scripts/seed.py                                 # dry run
api/.venv/bin/python scripts/seed.py --yes                           # 9 rules and 6 agents
api/.venv/bin/python scripts/seed.py --yes --from-local              # plus the processed test-set calls, redated into the last 14 days
api/.venv/bin/python scripts/migrate_local_to_supabase.py --yes      # a straight copy of everything local, audio included
api/.venv/bin/python scripts/reset_demo.py --yes                     # later: back to the seeded state
```

Only calls the pipeline really processed are copied, with their cached transcripts, so nothing is re-transcribed and no credits are spent. Reviewer decisions and rule switches travel with them.

## 5. Check it

- Start the API against Supabase and run `python3 scripts/smoke.py`.
- In the Supabase dashboard, the `call-audio` bucket should show as private, and the anon key should be refused by every table.
