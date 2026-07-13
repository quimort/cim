"""Shared FastAPI dependencies.

``get_current_owner_id`` is the seam for multi-tenancy. Today it returns a
constant, but every owned query already filters on its result, so enabling real
authentication later means changing this function — not the queries.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db

# The single owner of phase 1. Matches the server_default on account.owner_id.
DEFAULT_OWNER_ID = 1


def get_current_owner_id() -> int:
    """Phase 1: a constant. Becomes the authenticated user's id."""
    return DEFAULT_OWNER_ID


DbSession = Annotated[Session, Depends(get_db)]
CurrentOwnerId = Annotated[int, Depends(get_current_owner_id)]
