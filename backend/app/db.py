from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
