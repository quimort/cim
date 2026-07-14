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

## Market data batch

`backend/scripts/update_prices.py` fetches quotes (yfinance / CoinGecko) and
FX rates (Frankfurter/ECB) and writes them directly to Postgres. Idempotent —
safe to re-run. See [`backend/scripts/README.md`](./backend/scripts/README.md)
for usage and scheduling (cron / systemd timer).

## Working with Claude Code

Before assigning tasks, enable the plan→execute flow on the client (this
is NOT configured in `CLAUDE.md` — it lives in Claude Code's config):

1. **Opus-Plan mode**: in Claude Code, run `/model` and choose the option that
   plans with Opus and executes with Sonnet ("use Opus in plan mode, Sonnet for
   everything else"). This way plan reasoning uses the most capable model and
   implementation drops to a faster, cheaper one.
   - The effort level (low/medium/high/xhigh) is a separate setting, also
     in `/model` (effort slider). Check your installation for which models and
     levels are available — names and versions change.
2. **Plan mode (explicit approval)**: `Shift+Tab` (or `/plan`) makes Claude
   show you the plan and wait for your sign-off before touching files. Recommended
   for tasks that introduce domain logic.

The process discipline (explore → plan → approve → execute) is written
in `CLAUDE.md` and the model follows it regardless; the *model selection* for
each phase is set here, on the client.

## Status

Phase 1 — record and view. Skeleton in place: health endpoint + its test.
Next: SQLAlchemy models (account, instrument, movement, price,
exchange_rate) and the first Alembic migration.
