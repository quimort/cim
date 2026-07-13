"""API contract for the ``asset_class`` reference table.

Read-only by design: an asset class is the valuation dispatch key, so adding one
means writing a valuation strategy. There is deliberately no Create or Update
shape — the codes ship as migrations, not as API calls.
"""

from pydantic import Field

from app.schemas.common import ResponseSchema


class AssetClassRead(ResponseSchema):
    code: str = Field(description="The valuation dispatch key, e.g. 'tradable'.")
    label: str = Field(description="Human-readable display name.")
    description: str | None = Field(description="What this class means and how it's valued.")
    sort_order: int = Field(description="Preferred display order, ascending.")
