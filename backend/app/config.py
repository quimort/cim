from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables / .env."""

    # The real `.env` lives at the repo root, one level up from `backend/`,
    # which is the CWD assumed by uvicorn, alembic, pytest and the batch
    # script alike; a `backend/.env` (if ever created) would override it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://unset:unset@unset.invalid:5432/unset"
    app_env: str = "development"


settings = Settings()
