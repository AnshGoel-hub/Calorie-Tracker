# Calorie Tracker

An adaptive calorie and training tracker built for Indian diets and lifters. It logs food, water, weight and
workouts, and it **learns your real maintenance calories** from your weight trend and intake, then adjusts your
daily target.

## What makes it different

| | |
|---|---|
| **Adaptive TDEE engine** | Energy balance on a smoothed weight trend, shrunk toward the Mifflin-St Jeor formula when data is thin. Pure functions in `app/services/tdee.py`, backtested on simulated users. |
| **Indian-food-first estimates** | Katori/roti/plate units, plus Gemini estimates for foods, fruit and homemade recipes (ingredient list). Results are validated server-side and stored in a shared cache. |
| **Training-aware** | Workouts, per-muscle weekly sets and a 3D muscle model live next to the nutrition data. |

### Engine results (`python scripts/backtest_tdee.py`, 300 simulated users each)

| Scenario | Engine error | Formula-only error |
|---|---|---|
| Formula off by 15%, 5% under-reporting | 165 kcal | 390 kcal |
| Heavy under-reporting (-15%) | 246 kcal | 390 kcal |
| Sparse logging (half the days) | 202 kcal | 390 kcal |
| Noisy scale (sd 1.0 kg) | 192 kcal | 390 kcal |

These are simulated users (weight follows energy balance by construction), so they validate the algorithm, not
real-world accuracy. Real-user validation is on the roadmap.

## Architecture

```
frontend/ (static HTML/JS)          backend/app/
  index, workouts, progress, ...      api/        HTTP layer: auth, data (legacy), v1, account, pages
        |                             services/   business logic: estimates, tdee, insights, legacy adapter
        v                             models.py   SQLAlchemy schema      core/  config, db, security, logging
   FastAPI  ---->  PostgreSQL (SQLite for dev)    migrations/  Alembic
        \--------> Redis (optional: shared login throttling)
        \--------> Gemini API (estimates, behind a cache + daily quota)
```

### Key decisions and trade-offs

- **Normalized schema instead of a JSON blob per user.** Rows can be queried (the TDEE engine aggregates intake in
  SQL), indexed, and synced individually. Cost: a compatibility adapter (`services/legacy.py`) keeps the old
  frontend working until it moves to `/api/v1`.
- **Optimistic concurrency, not last-write-wins.** `PUT /api/v1/entries/{id}` carries the version the client saw;
  a stale write gets `409` with the current copy. Deletes are tombstones, so `GET /api/v1/sync?since=` can tell
  other devices what was removed.
- **CSRF via Origin check + SameSite=Lax cookies.** State-changing requests with a foreign `Origin` are rejected.
  No frontend changes needed. Browsers always send `Origin` on cross-site POSTs.
- **Login throttling behind an interface** (`core/ratelimit.py`): in-memory by default, Redis when `REDIS_URL` is
  set so limits hold across workers. Redis outages fail open rather than lock everyone out.
- **Gemini calls are server-side only.** The server builds the prompt (user text is passed as quoted data),
  validates every number (kcal range, macro sums, unit weights), retries once, and caches by
  `(normalised name, type, ingredients)`. Only cache misses use the daily quota; `GET /api/v1/insights/cache`
  reports the hit rate.
- **Migrations are the only way the schema changes.** CI applies them to Postgres, runs `alembic check` (no drift
  from the models) and round-trips downgrade/upgrade.

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set JWT_SECRET, GEMINI_API_KEY
alembic upgrade head
python -m app.main              # http://127.0.0.1:8000
```

Move `manifest.webmanifest` and the icon PNGs from the old `static/` folder into `frontend/static/`.

With Docker: `docker compose up --build` (Postgres + Redis + app).

### Migrating existing users

```bash
alembic upgrade head                      # keeps users/usage/user_data, adds the new tables
python scripts/import_legacy.py --dry-run
python scripts/import_legacy.py
```

### Tests and quality gates

```bash
pytest --cov=app        # 60 tests, ~96% coverage; CI fails under 90%
ruff check .
python scripts/backtest_tdee.py
```

### Admin

`python scripts/admin.py --help` (list, show, reset password, export, delete). Set `ADMIN_DATABASE_URL` in
`backend/.env` to target production.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/signup`, `/api/login`, `/api/logout` | Auth (invite code at signup, throttled login) |
| GET/POST | `/api/data`, `/api/workouts` | Legacy snapshot documents (deprecated) |
| GET/POST | `/api/v1/entries`, PUT/DELETE `/api/v1/entries/{id}` | Food entries with optimistic concurrency |
| GET | `/api/v1/sync?since=` | Change feed (entries incl. tombstones, day logs) |
| POST | `/api/v1/estimate` | Gemini estimate (validated, cached) |
| GET | `/api/v1/insights/tdee`, POST `.../apply` | Adaptive maintenance estimate and target |
| GET | `/api/v1/insights/cache` | Estimate-cache hit rate |
| POST/GET | `/api/account/*` | Change password, export, delete |

## Roadmap

1. Move the frontend to `/api/v1` (offline-first with the sync feed) and then to React/Next.js; retire `/api/data`.
2. Sync workouts incrementally (currently entries and day logs only).
3. Serve the built-in exercise catalogue and a verified Indian food catalogue from the database.
4. Validate the TDEE engine on real users; add a Kalman filter variant and compare.
5. Load test (k6) and publish p95 latency; add Prometheus metrics.
