from fastapi import FastAPI

app = FastAPI(
    title="Gestor de capital e inversiones",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Endpoint de salud. Sirve de humo para verificar que la app arranca."""
    return {"status": "ok"}


# Los routers de cuentas, instrumentos, movimientos y derivados se registran
# aquí a medida que se implementan:
#   from app.routers import cuentas, instrumentos, movimientos
#   app.include_router(cuentas.router, prefix="/api")
