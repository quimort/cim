"""Find the Yahoo symbol to put in ``instrument.provider_ref``.

Mostly for investment funds (fondos): you know the ISIN, but Yahoo prices the
fund under an opaque ``0P…`` symbol. Run from ``backend/``:

    poetry run python -m scripts.resolve_symbol IE00B03HD316
    poetry run python -m scripts.resolve_symbol "vanguard ftse all-world"

Pick the row whose ``CURRENCY`` matches the share class you actually hold, then
tag the instrument with ``price_source=yfinance`` and that symbol as
``provider_ref``. Read-only: touches no database.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from app.services.market_data.yfinance_provider import resolve_symbol

logger = logging.getLogger("resolve_symbol")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    candidates = resolve_symbol(args.query, max_results=args.limit)
    if not candidates:
        print(f"No Yahoo symbol found for {args.query!r}.")
        return 1

    print(f"{'SYMBOL':<16} {'TYPE':<12} {'CCY':<5} NAME")
    for candidate in candidates:
        print(
            f"{candidate.symbol:<16} {candidate.quote_type:<12} "
            f"{candidate.currency or '-':<5} {candidate.name}"
        )
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="An ISIN (e.g. IE00B03HD316) or a fund/ticker name.")
    parser.add_argument(
        "--limit", type=int, default=6, help="Maximum candidates to show (default: 6)."
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
