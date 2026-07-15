"""Price/FX batch (task 1f): fetches quotes and FX rates, writes directly to Postgres.

Public entrypoint for the CLI script:

    from app.services.market_data import run_update

The API process never imports this package — yfinance/pandas only load in the
batch process, never at API runtime.
"""

from app.services.market_data.runner import run_update
from app.services.market_data.types import FxRate, Quote, RunSummary

__all__ = ["FxRate", "Quote", "RunSummary", "run_update"]
