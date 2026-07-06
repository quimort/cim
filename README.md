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
cartera/
├── CLAUDE.md              # design decisions and guardrails (READ FIRST)
├── docker-compose.yml     # orchestrates proxy + backend + db
├── Caddyfile              # reverse proxy
├── .env.example           # secrets template (real .env is not committed)
├── backend/
│   └── app/
│       ├── models/        # SQLAlchemy (DB only)
│       ├── schemas/       # Pydantic (API contracts, amounts as str)
│       ├── routers/       # endpoints (HTTP only, no domain logic)
│       └── services/      # financial logic: FIFO, accrual, consolidation
├── frontend/              # React + TS + Vite
└── scripts/               # price batch job (writes directly to Postgres)
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
uv sync --all-extras
uv run ruff check .         # lint
uv run ruff format .        # formatting
uv run mypy app             # types
uv run pytest -v            # tests
```

These same gates run in CI (`.github/workflows/ci.yml`) on every push and PR.

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
