# Setup and migration guide

This guide is for moving an **existing** repo (already deployed on Render, data on Neon) to the new layout
without losing history or data.

## 0. How the cutover is made safe

- The migration is **additive**. It only adds new tables; `users`, `usage` and the old `user_data` blobs are
  never modified or dropped. The old app keeps working against the same database until you switch.
- The new app never writes to `user_data`, so your old data stays intact as a rollback copy.
- Rehearse everything on a **Neon branch** (a copy of your database) before touching production.

## 1. Back up production

```bash
pg_dump "$NEON_URL" > backup-$(date +%F).sql          # full dump (needs the postgresql client tools)
```
Also export each account from the old app's Account page ("Download my data"). In Neon you can additionally
create a branch from `main` as a point-in-time copy.

## 2. Restructure the repo (keeps git history)

From the root of your existing repo:

```bash
git checkout -b v2-rewrite
mkdir -p backend frontend
git mv index.html workouts.html progress.html calendar.html achievements.html login.html account.html frontend/
git mv nav.js ui.css anatomy.js goals.js frontend/
git mv static frontend/static                          # manifest + icons
git mv requirements.txt backend/requirements.txt
git mv admin.py backend/admin_old.py
git rm main.py
git commit -m "Restructure into backend/ and frontend/"
```
`git mv` makes git record these as renames, so `git log --follow` still shows each file's full history.

## 3. Add the new code

Unzip `calorie-tracker-v2.zip` somewhere else (for example `/tmp/ct`), then copy its contents **over** the repo:

```bash
cp -r /tmp/ct/backend/. backend/
cp /tmp/ct/frontend/index.html /tmp/ct/frontend/progress.html frontend/   # the two edited pages
cp /tmp/ct/{Dockerfile,docker-compose.yml,render.yaml,README.md,SETUP.md,.gitignore} .
mkdir -p .github/workflows && cp /tmp/ct/.github/workflows/ci.yml .github/workflows/
git rm -f backend/admin_old.py                          # replaced by backend/scripts/admin.py
git add -A
git commit -m "Normalized schema, Alembic, tests, CI, adaptive TDEE, estimate cache"
```
(The other frontend files are unchanged, so you keep your originals.) Two commits make a clearer story than
one: restructure first, behaviour second.

## 4. Run it locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # set JWT_SECRET and GEMINI_API_KEY
alembic upgrade head
python -m app.main                                     # http://127.0.0.1:8000
pytest --cov=app && ruff check .
```

## 5. Rehearse on a Neon branch

1. In Neon, create a branch from `main` and copy its connection string.
2. Point your local `.env` at it: `DATABASE_URL=postgresql://...branch-string...`
3. Run:
```bash
alembic upgrade head
python scripts/import_legacy.py --dry-run     # preview
python scripts/import_legacy.py               # real import into the branch
python -m app.main                            # log in with your real account and check your data
```
Check: food log, calendar markers, weights, workouts, custom foods, achievements. If something looks wrong,
delete the branch and fix it; production is untouched.

## 6. Cut over production

Do this when nobody (including you) is logging.

1. Open a pull request for `v2-rewrite` and let **CI go green** (it also tests the migration on Postgres).
2. **Render service type:** your existing service uses the Python runtime and the new `render.yaml` keeps it
   (Render can't switch a service to Docker). In the Render dashboard make sure the service has
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
   - the same environment variables as before (`DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `INVITE_CODE`, `COOKIE_SECURE=1`).
3. Merge to `main`. Render deploys; on start it runs `alembic upgrade head` against Neon, which adds the new
   tables next to the old ones.
4. **Immediately** import your data (this is the only moment old and new data can diverge):
```bash
cd backend
DATABASE_URL="postgresql://...production Neon string..." python scripts/import_legacy.py --dry-run
DATABASE_URL="postgresql://...production Neon string..." python scripts/import_legacy.py
```
   If you or a friend logged anything between the deploy and the import, those entries were saved to the new
   tables. The import skips users who already have new data (it tells you); in that case re-run with `--force`
   only for a user whose new data you are happy to replace.
5. Log in on the live site and check your data. Everyone is signed out once (the session cookie format is
   unchanged, but the first request after deploy is the easiest time to confirm login works).

### Rollback

Redeploy the previous commit in Render. The old app reads `user_data`, which was never touched. Anything logged
*after* the cutover lives only in the new tables, so roll back quickly or export it first with
`python scripts/admin.py export you@example.com`.

## 7. After it is stable

- Remove the old blobs when you are sure: `DROP TABLE user_data;` (a new Alembic migration is the proper way).
- Admin commands moved: `python backend/scripts/admin.py list|show|reset|export|delete`. Put
  `ADMIN_DATABASE_URL=postgresql://...` in `backend/.env` to target production.
- Optional: add Redis (`REDIS_URL`) once you run more than one worker so login throttling is shared.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Icons or manifest 404 | `static/` not moved to `frontend/static/` |
| `ModuleNotFoundError: app` | run commands from `backend/` |
| Everyone logged out after each deploy | `JWT_SECRET` not set in Render |
| "GEMINI_API_KEY is not set" | add it to `.env` / Render env |
| `alembic check` fails in CI | model changed without a migration: `alembic revision --autogenerate -m "..."` |
| Import says "already migrated" | that user already has new-schema rows; use `--force` deliberately |
