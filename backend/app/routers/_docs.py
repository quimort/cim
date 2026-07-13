"""Shared OpenAPI documentation helpers for the routers.

Not a public resource — the leading underscore keeps it out of anyone's mental
model of "the routers", it is purely doc plumbing.
"""

from typing import Any

from app.schemas.common import ErrorDetail


def error_responses(*pairs: tuple[int, str]) -> dict[int | str, dict[str, Any]]:
    """Build a FastAPI ``responses=`` mapping for the domain errors an endpoint can raise.

    Every 4xx the service layer produces has the same shape (``{"detail": str}``,
    see ``ErrorDetail``); this just documents which codes apply to which endpoint
    without repeating that schema by hand everywhere.
    """
    return {code: {"model": ErrorDetail, "description": description} for code, description in pairs}
