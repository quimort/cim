"""CLI entrypoint for the price/FX batch (task 1f).

Writes directly to Postgres via SQLAlchemy — never through the HTTP API, per
CLAUDE.md's "market data" API family. Run from ``backend/`` so ``app.*``
imports and the root ``.env`` resolve:

    poetry run python -m scripts.update_prices [--dry-run] [--lookback-days N] [--verbose]

Safe to re-run: writes are idempotent (see ``app.services.market_data.upsert``).
Exit code is 0 if every instrument and the FX step succeeded, 1 otherwise —
successful parts are still committed on a partial failure, so cron/systemd
just needs to alert on non-zero, not retry the whole run.
"""

import argparse
import functools
import logging
import sys
from collections.abc import Sequence
from datetime import date

import httpx

from app.db import SessionLocal
from app.models.enums import PriceSource
from app.services.market_data import coingecko, frankfurter, runner, yfinance_provider
from app.services.market_data.types import QuoteFetcher

logger = logging.getLogger("update_prices")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    with httpx.Client(timeout=30) as client, SessionLocal() as db:
        quote_fetchers: dict[PriceSource, QuoteFetcher] = {
            PriceSource.YFINANCE: yfinance_provider.fetch_quotes,
            PriceSource.COINGECKO: functools.partial(coingecko.fetch_quotes, client),
        }
        fx_fetcher = functools.partial(frankfurter.fetch_fx_rates, client)

        summary = runner.run_update(
            db,
            quote_fetchers=quote_fetchers,
            fx_fetcher=fx_fetcher,
            today=date.today(),
            lookback_days=args.lookback_days,
            dry_run=args.dry_run,
        )

    logger.info(
        "prices_written=%d fx_rows_written=%d instruments_ok=%d "
        "instruments_skipped=%d instruments_failed=%d",
        summary.prices_written,
        summary.fx_rows_written,
        summary.instruments_ok,
        summary.instruments_skipped,
        summary.instruments_failed,
    )
    for failure in summary.failures:
        logger.error("failed: %s", failure)

    return 0 if summary.ok else 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Days to backfill for an instrument/pair with no stored history (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and log what would be written, without committing.",
    )
    parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
