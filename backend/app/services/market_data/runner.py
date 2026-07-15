"""Orchestrates one price/FX batch run (task 1f).

Fully injectable: the CLI entrypoint (``scripts/update_prices.py``) wires real
fetchers; tests wire fakes. One instrument's failure never aborts the run —
the session is rolled back, the failure is recorded in the summary, and the
loop continues. Each instrument (and the FX step) commits independently.
"""

import logging
from collections.abc import Mapping
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PriceSource
from app.models.instrument import Instrument
from app.services.market_data import gaps, upsert
from app.services.market_data.types import FxFetcher, QuoteFetcher, RunSummary

logger = logging.getLogger(__name__)


def run_update(
    db: Session,
    *,
    quote_fetchers: Mapping[PriceSource, QuoteFetcher],
    fx_fetcher: FxFetcher,
    today: date,
    lookback_days: int = gaps.DEFAULT_LOOKBACK_DAYS,
    dry_run: bool = False,
) -> RunSummary:
    summary = RunSummary()

    active_instruments = db.execute(select(Instrument).where(Instrument.is_active)).scalars().all()
    for instrument in active_instruments:
        if instrument.price_source is None:
            summary.instruments_skipped += 1
            logger.debug("skipping instrument %s: no price_source", instrument.id)
            continue
        _update_instrument(db, instrument, quote_fetchers, today, lookback_days, dry_run, summary)

    _update_fx(db, fx_fetcher, today, lookback_days, dry_run, summary)
    return summary


def _update_instrument(
    db: Session,
    instrument: Instrument,
    quote_fetchers: Mapping[PriceSource, QuoteFetcher],
    today: date,
    lookback_days: int,
    dry_run: bool,
    summary: RunSummary,
) -> None:
    try:
        if instrument.price_source is None or instrument.provider_ref is None:
            raise ValueError(f"instrument {instrument.id} has no price_source/provider_ref")
        fetcher = quote_fetchers[PriceSource(instrument.price_source)]
        last = gaps.last_price_date(db, instrument.id)
        start, end = gaps.fetch_window(last, today, lookback_days)
        quotes = fetcher(instrument.provider_ref, instrument.currency, start, end)
        written = upsert.upsert_prices(db, instrument.id, instrument.currency, quotes)
        if dry_run:
            db.rollback()
        else:
            db.commit()
        summary.prices_written += written
        summary.instruments_ok += 1
    except Exception:
        db.rollback()
        logger.exception("failed to update prices for instrument %s", instrument.id)
        summary.instruments_failed += 1
        summary.failures.append(f"instrument {instrument.id} ({instrument.provider_ref})")


def _update_fx(
    db: Session,
    fx_fetcher: FxFetcher,
    today: date,
    lookback_days: int,
    dry_run: bool,
    summary: RunSummary,
) -> None:
    currencies = gaps.currencies_in_use(db)
    if not currencies:
        return
    try:
        last_dates = [gaps.last_fx_date(db, currency, "EUR") for currency in currencies]
        # The widest window across all pairs: if every pair has history, start
        # at the earliest of them; if any pair is new, fall back to the full
        # lookback. One fetch then covers every pair; over-fetching for
        # already-current pairs is harmless (upsert is a no-op for them).
        known = [d for d in last_dates if d is not None]
        last = min(known) if len(known) == len(last_dates) else None
        start, end = gaps.fetch_window(last, today, lookback_days)
        rates = fx_fetcher(currencies, start, end)
        written = upsert.upsert_fx(db, rates)
        if dry_run:
            db.rollback()
        else:
            db.commit()
        summary.fx_rows_written += written
    except Exception:
        db.rollback()
        logger.exception("failed to update FX rates")
        summary.fx_failed = True
        summary.failures.append("fx rates")
