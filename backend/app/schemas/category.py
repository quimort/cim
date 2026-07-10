"""API contracts for the ``category`` resource — the user-managed grouping axis."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import RequestSchema, ResponseSchema


class CategoryCreate(RequestSchema):
    name: str = Field(min_length=1, max_length=100, description="Unique display name.")
    description: str | None = Field(default=None, min_length=1, max_length=200)


class CategoryUpdate(RequestSchema):
    """PATCH semantics: only the provided fields change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = Field(
        default=None, description="Set to false to deactivate. There is no hard delete."
    )


class CategoryRead(ResponseSchema):
    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
