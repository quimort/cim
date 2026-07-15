# Capital and investment manager

Personal web application to record and visualize net worth and investments.
Immutable append-only ledger, derived valuation, multi-currency, exact decimals.

**Before touching code, read [`CLAUDE.md`](./CLAUDE.md)** — it contains the
project's design decisions and invariant guardrails.

## Stack

PostgreSQL → SQLAlchemy/Alembic → FastAPI/Pydantic → OpenAPI → TS types → React/Vite.
Everything in Docker. Reverse proxy (Caddy) as the sole external-facing entry point;
backend and DB on an isolated internal network.

## Structure

```
CIM/
├── CLAUDE.md              # design decisions and guardrails (READ FIRST)
├── docker-compose.yml     # orchestrates proxy + backend + db
├── Caddyfile              # reverse proxy
├── .env.example           # secrets template (real .env is not committed)
├── backend/
│   ├── app/
│   │   ├── models/        # SQLAlchemy (DB only)
│   │   ├── schemas/       # Pydantic (API contracts, amounts as str)
│   │   ├── routers/       # endpoints (HTTP only, no domain logic)
│   │   └── services/      # financial logic: FIFO, accrual, consolidation
│   └── scripts/           # price/FX batch job (writes directly to Postgres)
└── frontend/              # React + TS + Vite
```

## Development startup

```bash
cp .env.example .env        # and fill in the password
docker compose up --build
# App at https://localhost (Caddy serves the frontend and proxies /api)
```

## Quality loop (backend)

```bash
cd backend
poetry install --with dev
poetry run ruff check .         # lint
poetry run ruff format .        # formatting
poetry run mypy app scripts     # types
poetry run pytest -v            # tests
```

These same gates run in CI (`.github/workflows/ci.yml`) on every push and PR.

## Frontend dev workflow

Local development runs Vite's dev server against a locally-run backend
(Node 22 — the same version as the Docker image and CI):

```bash
# 1. Backend on :8000 (reads DATABASE_URL from the root .env)
cd backend
poetry run uvicorn app.main:app --reload --port 8000

# 2. Frontend dev server on :5173 (proxies /api to :8000 — the backend
#    has no CORS on purpose; the browser only ever talks same-origin)
cd frontend
npm install
npm run dev
```

Quality loop (also a CI job):

```bash
npm run lint        # eslint
npm run typecheck   # tsc -b
npm run build       # tsc -b && vite build
```

**API types are generated, never hand-written.** `src/api/schema.ts` comes
from the backend's OpenAPI schema and is committed (CI and Docker builds
don't have a backend to generate against). After any Pydantic schema change:

```bash
npm run gen:api     # regenerates src/api/schema.ts from localhost:8000
```

then commit the diff. Never edit `schema.ts` by hand — it is lint-ignored
and fully derived.

## Market data batch

`backend/scripts/update_prices.py` fetches quotes (yfinance / CoinGecko) and
FX rates (Frankfurter/ECB) and writes them directly to Postgres. Idempotent —
safe to re-run. See [`backend/scripts/README.md`](./backend/scripts/README.md)
for usage and scheduling (cron / systemd timer).


## Status

Phase 1 — record and view. Backend complete: data model, migrations, write
endpoints (accounts, instruments, categories, movements), derived read
endpoints (positions, net worth, allocation), and the price/FX batch script.
Frontend in place: movement entry (incl. transfers), accounts/instruments/
categories management, positions table, net-worth dashboard with evolution
chart, and allocation donut. Next: end-to-end wire-up & polish (task 1h).
