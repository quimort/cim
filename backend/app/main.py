from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.routers import (
    accounts,
    allocation,
    asset_classes,
    categories,
    instruments,
    movements,
    net_worth,
    positions,
)
from app.services.errors import ConflictError, DomainRuleError, NotFoundError

_DESCRIPTION = """
A personal web app to track net worth and investments across accounts,
instruments, and currencies.

**The ledger is the source of truth.** Every purchase, sale, deposit, transfer,
and so on is recorded as an append-only row in `movement`. Positions, cost
basis, and net worth are never stored — they are derived from the ledger.
A movement is never edited or physically deleted: corrections are either a
compensating movement or an annulment (`DELETE` sets `voided_at`, it does not
remove the row). **There is no `PUT` on movements, ever.**

**Money is never a float.** Amounts travel over JSON as **strings**
(`"1234.56"`), never as numbers, so JSON's floating-point representation can
never introduce rounding error. Every amount also carries its own currency —
the code never assumes EUR.

**Two orthogonal classification axes** sit on `instrument`:
`asset_class` (`tradable` / `cash` / `loan`) determines **how the instrument is
valued** and is a closed, seeded reference table — see `/asset-classes`, which
is read-only. `category` is the **user-managed** grouping axis (ETF, crypto,
real estate, ...) — see `/categories`, which supports full CRUD. The two never
touch: valuation never depends on how you've chosen to group something.

**Ownership** anchors on `account.owner_id`. Every account and movement query
is scoped to the current owner; a resource that belongs to someone else
answers `404`, not `403`, so its existence is never leaked.
""".strip()

_TAGS_METADATA = [
    {"name": "health", "description": "Liveness check."},
    {
        "name": "accounts",
        "description": (
            "Where money or assets live (bank, broker, exchange). Each has a "
            "fixed currency and is owned by the current user. No hard delete: "
            "deactivate via `PATCH {\"is_active\": false}`."
        ),
    },
    {
        "name": "asset-classes",
        "description": (
            "Read-only reference table: the valuation dispatch key "
            "(`tradable` / `cash` / `loan`). Adding a class means writing a "
            "valuation strategy in code and shipping a migration, so there is "
            "no create/update/delete here."
        ),
    },
    {
        "name": "categories",
        "description": (
            "The open, user-managed grouping axis (ETF, crypto, real estate, "
            "...). Full CRUD; delete is a soft-delete so instruments and "
            "historical reports keep resolving."
        ),
    },
    {
        "name": "instruments",
        "description": (
            "A tradable, a cash position, or a loan. `asset_class` and "
            "`currency` are fixed at creation; `category_id` may change anytime."
        ),
    },
    {
        "name": "movements",
        "description": (
            "The append-only ledger. `POST` records; there is no `PUT`, ever. "
            "`DELETE` annuls (sets `voided_at`) rather than removing the row. "
            "A transfer between two owned accounts is created via "
            "`POST /movements/transfer` and always produces two linked rows."
        ),
    },
    {
        "name": "positions",
        "description": (
            "Derived, read-only: current tradable holdings, FIFO cost basis, "
            "market value, and unrealized P&L. Nothing is stored — every request "
            "replays the ledger."
        ),
    },
    {
        "name": "net-worth",
        "description": (
            "Derived, read-only: total net worth in EUR, as of any date "
            "(`?date=`), and its evolution over time (`/net-worth/series`)."
        ),
    },
    {
        "name": "allocation",
        "description": (
            "Derived, read-only: net worth broken down by `asset_class`, "
            "`category`, `currency`, or `account` (`?by=`)."
        ),
    },
]

app = FastAPI(
    title="Capital and investment manager",
    version="0.1.0",
    description=_DESCRIPTION,
    openapi_tags=_TAGS_METADATA,
    # The proxy only forwards /api/* to the backend; anything else is the SPA.
    # FastAPI's defaults (/docs, /openapi.json) would therefore be unreachable
    # in the deployed stack — and the frontend generates its TypeScript types
    # from this schema, so it has to be served where the proxy can see it.
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
)


@app.get("/api/health", tags=["health"], summary="Check the API is up")
def health() -> dict[str, str]:
    """Health endpoint. Smoke-tests that the app starts up."""
    return {"status": "ok"}


# The service layer knows nothing about HTTP; it raises domain errors and these
# handlers assign the status codes. That is what keeps the routers thin.
_ERROR_STATUS: dict[type[Exception], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    DomainRuleError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=_ERROR_STATUS[type(exc)],
        content={"detail": str(exc)},
    )


for _error_type in _ERROR_STATUS:
    app.add_exception_handler(_error_type, _handle_domain_error)

app.include_router(accounts.router, prefix="/api")
app.include_router(asset_classes.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(instruments.router, prefix="/api")
app.include_router(movements.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(net_worth.router, prefix="/api")
app.include_router(allocation.router, prefix="/api")
