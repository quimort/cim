from fastapi import FastAPI

app = FastAPI(
    title="Capital and investment manager",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health endpoint. Smoke-tests that the app starts up."""
    return {"status": "ok"}


# The accounts, instruments, movements, and derived routers get registered
# here as they're implemented:
#   from app.routers import accounts, instruments, movements
#   app.include_router(accounts.router, prefix="/api")
