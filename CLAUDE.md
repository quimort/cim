# CLAUDE.md — Capital and investment manager

This file defines the project's design decisions, conventions, and guardrails.
Read it in full before writing code. Sections marked **RULE** are
invariants that must not be broken without an explicit discussion.

---

## What this is

A personal web application to manage capital and investments (net worth,
not day-to-day personal finance). Dual purpose: (1) a real tool for
personal use, (2) a portfolio project that demonstrates technical judgment.

**Priority in case of conflict: real usefulness wins over polish.**

Current phase: **1 — record and view**. Phase 2 (decide: rebalancing,
FIRE projections, taxation) will come later and will be built as new
*services* that read the same model, without touching the ledger.

---

## Data architecture — the core

### RULE: the ledger is the single source of truth, and it is immutable
- Everything is recorded as append-only **movements** in a `movement` table.
- Positions, FIFO cost, P&L, and net worth are **NEVER stored**
  as state. They are **derived** from the ledger in the service layer.
- A movement is never edited or physically deleted. Corrections = a
  compensating movement or soft-delete (annulment flag), never a real UPDATE or DELETE.

### RULE: never floats for money
- Python: `Decimal`, never `float`.
- Postgres: `NUMERIC`/`DECIMAL`, never `FLOAT`/`REAL`.
- Crypto amounts need high precision (>= 8 decimals).

### RULE: multi-currency from day one
- Every amount is stored in its **native currency**, together with its currency.
- Conversion to EUR (base currency) is always **derived**, using the exchange
  rate for the corresponding date. The "frozen" EUR value is never stored.
- There is an `exchange_rate` table (time series) even though today there's only EUR.
- Code **always reads the currency**, never assumes EUR.

### Entities
- `account` — where the money/asset lives (bank, broker, exchange). Has a currency.
- `instrument` — a single table with an `asset_class` discriminator
  (`tradable` | `cash` | `loan`). Loan-specific fields
  (`maturity_date`, `expected_interest`, `status`) are NULL for the rest.
  The `asset_class` determines **how it's valued**, not how it's recorded.
  Also carries a nullable `category_id` — see the two axes below.
- `asset_class` — a **seeded reference table**. `instrument.asset_class` is a FK
  to `asset_class.code`.
- `category` — the **user-managed** grouping taxonomy (full CRUD).
- `movement` — the atomic, immutable event. The heart of the system.
- `price` — time series of quotes (populated by the batch script).
- `exchange_rate` — time series of currency pairs (populated by the batch script).

### RULE: asset_class and category are two different axes
- `asset_class` answers **how is this valued** — it is the dispatch key of the
  valuation services (FIFO for `tradable`, ledger balance for `cash`, principal
  plus accrued interest for `loan`). Each code corresponds to a piece of Python.
  The set of codes is therefore **closed and code-level**: the table exists so the
  DB can enforce it by FK and the UI can read labels, *not* so new classes can be
  invented at runtime. `/asset-classes` is read-only; adding a class means writing
  a valuation strategy and shipping a migration. The `AssetClass` enum stays the
  dispatch key, and `tests/test_asset_class_sync.py` asserts the enum, the seed
  constant, and the migration's copy all agree — drift fails CI, not production.
- `category` answers **how do I want to see it grouped** (ETF, crypto, real
  estate). Open, user-managed, never touches valuation. It carries **no link back
  to `asset_class`** — the two are orthogonal (a REIT is `tradable` and grouped
  as `real estate`), and coupling them would force nonsense mappings.
- Categories are **soft-deleted** (`is_active`), never removed: instruments point
  at them and historical allocation reports must keep resolving.

### Movement types (closed enum)
`purchase`, `sale`, `dividend`, `interest`, `fee`, `deposit`, `withdrawal`,
`transfer_out`, `transfer_in`, `principal_repayment`.

### RULE: transfers = two linked movements
A transfer between own accounts is TWO rows (`transfer_out` at the origin,
`transfer_in` at the destination) joined by `transfer_id`. This preserves
the "one movement = one account" rule and lets each account balance on its own.

### RULE: ingestion fields ready even though unused today
`movement` carries `source` (default `manual`) and `external_id` (nullable).
A `UNIQUE(source, external_id)` constraint for future import idempotency.
In phase 1 they're always `manual`/NULL, but the code reads them rather than assuming them.

### RULE: multi-tenant-ready — ownership anchored in `account.owner_id`
- `account` carries an `owner_id`. Every other entity (`movement`, position,
  derived views) reaches ownership by joining through its `account`, never
  by duplicating an owner field elsewhere.
- No query in `services/` or `routers/` may assume global access. Every
  read or write path that touches `account`/`movement` must be scoped to
  the current owner — even in phase 1 with a single user.
- This is single-user *in practice* today, not single-user *in the schema*.
  Don't take shortcuts (unscoped `SELECT *`, admin-style endpoints without
  an owner filter) that would need to be undone to support a second user.

---

## Stack

- **Backend**: Python + FastAPI + Pydantic. SQLAlchemy (ORM) + Alembic (migrations).
- **DB**: PostgreSQL.
- **Frontend**: React + TypeScript + Vite.
- **Infra**: Docker Compose. Reverse proxy (Caddy) + backend + Postgres + batch script.
- **Backend dependency management**: Poetry (one manager only, no mixing).

### RULE: end-to-end typing
Pydantic models are the contract. They generate OpenAPI, and from OpenAPI
the frontend's TypeScript types are generated (`frontend/src/api`). A change in a
Pydantic schema is reflected in TS. Never hand-write the API's TS types.

### RULE: amounts as strings in the API's JSON
A `Decimal` is serialized as a **string** (`"1234.56"`), not a number, so that
JSON serialization doesn't introduce floating-point errors. It's parsed to
`Decimal` on the backend and to a precision type (e.g. BigNumber) on the frontend.

---

## API shape

Three families of endpoints:

1. **Write** (masters + ledger):
   - `/accounts` — CRUD (editable: rename, deactivate).
   - `/instruments` — CRUD (editable). Filterable by `?asset_class=`, `?category_id=`.
   - `/categories` — CRUD (editable; DELETE is a soft-delete via `is_active`).
   - `/movements` — **append + read + annulment**. GET, POST, soft-DELETE.
     **RULE: NEVER implement PUT on movements.**

1b. **Reference** (read-only, seeded by migration):
   - `/asset-classes` — GET only. See "asset_class and category are two different axes".

2. **Derived** (read-only, computed from the ledger, no POST/PUT):
   - `/positions` — current positions, FIFO cost, unrealized P&L.
   - `/net-worth` — total in EUR. `?date=YYYY-MM-DD` answers for any past day.
   - `/net-worth/series` — time evolution for charts.
   - `/allocation` — breakdown by asset_class / currency / account.

3. **Market data**: written by the batch script **directly to Postgres**,
   NOT via HTTP. The API only reads it when computing valuations.

---

## Code organization

RULE: strict layer separation in the backend.
- `models/` — SQLAlchemy. Only talk to the DB.
- `schemas/` — Pydantic. API contracts (amounts as str).
- `routers/` — endpoints. Only translate HTTP <-> services. No domain logic.
- `services/` — **all domain logic**: FIFO valuation, interest
  accrual, multi-currency consolidation. This is what phase 2 extends.
- `db.py` — session and connection.

The golden rule: if it's financial logic, it goes in `services/`, not `routers/`.

---

## Security and secrets

- **RULE: the real `.env` is NEVER committed.** Only `.env.example` with no values.
  `.gitignore` excludes `.env` from the very first commit.
- The database is **Supabase** (managed, externally-hosted Postgres) — an
  accepted, intentional exception to "no external exposure": it is reached
  only over TLS (`sslmode=require`) via the Supabase session pooler, and
  credentials live only in the uncommitted `.env`.
- The backend exposes no public port — only the reverse proxy is public-facing.
  ("No exposing to the internet" now scopes to the backend/proxy boundary,
  not the database, since the database is Supabase by design.)

---

## Workflow — plan before executing

RULE: for any non-trivial task (touches more than ~3 files, involves a
refactor, or introduces new domain logic), follow this cycle:

1. **Explore** — read the relevant files and the current state before proposing anything.
2. **Plan** — present an explicit execution plan: which files are
   created/touched, what tests are added, what design decisions it implies. Check
   the plan against the rules in this document (immutable ledger, no
   floats, multi-currency, layer separation, etc.).
3. **Approve** — wait for the user's sign-off on the plan before touching code.
4. **Execute** — implement following the approved plan, and close with the quality
   loop (tests, lint, types) passing.

For trivial tasks (a typo, a one-line tweak, renaming something), the full
cycle isn't necessary — use judgment.

Configuration note (not a rule the model can self-apply, it belongs on the
client side): this project is meant to be used with Claude Code's Opus-Plan
mode — planning with the most capable model, execution with a faster one — and
with plan mode (explicit approval before editing). That's toggled in `/model`,
not here. See README.

## Working conventions

- Domain language (table names, fields, movement types): **English**
  (`account`, `movement`, `purchase`). Code and technical comments should be
  consistent English throughout — business vocabulary is English and consistent.
- Every new backend feature with logic is accompanied by its test in `tests/`.
- Before considering a task done: tests pass, the linter passes, types
  (mypy / tsc) pass. That's the loop: write -> verify -> fix.
- Schema migrations: ALWAYS via Alembic, never manual changes to the DB.

---

## What NOT to do (summary of guardrails)

- No `float` for money. Ever.
- No real `PUT`/`DELETE` on movements.
- No storing positions/net worth as state.
- No assuming EUR — always read the currency.
- No amounts as numbers in JSON — strings.
- No domain logic in `routers/`.
- No committing `.env`.
- No mixing two dependency managers.
- No exposing the backend directly to the internet (Supabase is the accepted
  managed-DB exception, reached only over TLS with the session pooler).
- No query that assumes global access — ownership always traces back to
  `account.owner_id`.
