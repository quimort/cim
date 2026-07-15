# Price/FX batch script (task 1f)

`update_prices.py` fetches market quotes and FX rates and writes them
**directly to Postgres** via SQLAlchemy — never through the HTTP API. It never
stores anything derived (positions, net worth): it only feeds the `price` and
`exchange_rate` time series that the valuation services already read.

## What it does

- For every active instrument with `price_source` set, fetches daily closes
  from the configured provider (`yfinance` or `coingecko`) and writes them to
  `price`.
- Fetches FX rates for every non-EUR currency in use (from active instruments
  and accounts) from the [Frankfurter API](https://www.frankfurter.dev/)
  (ECB reference rates, EUR base, no API key) and writes them to
  `exchange_rate`.
- Gap-fills: each run fetches from the last stored day (inclusive) through
  today, so a missed run heals itself; instruments/pairs with no history yet
  get a bounded lookback (`--lookback-days`, default 30).
- **Idempotent**: re-running never duplicates a day's price or rate — running
  it twice in a row leaves the row count unchanged.
- One instrument (or the FX step) failing never aborts the run — the
  successful parts still commit, and the failure is logged and counted.

## Setting up an instrument to be priced

`price_source` and `provider_ref` are plain fields on `instrument`, settable
via the existing API:

```bash
curl -X PATCH https://localhost/api/instruments/<id> \
  -H 'Content-Type: application/json' \
  -d '{"price_source": "yfinance", "provider_ref": "VWCE.DE"}'
```

- `price_source: "yfinance"` — `provider_ref` is the Yahoo Finance ticker
  (e.g. `"VWCE.DE"`, `"AAPL"`).
- `price_source: "coingecko"` — `provider_ref` is the CoinGecko coin id (e.g.
  `"bitcoin"`, not the ticker symbol `"BTC"`; look it up at
  `https://api.coingecko.com/api/v3/coins/list`).
- Both fields require `asset_class = tradable` and must be set together
  (or both left `null`). An instrument with `price_source = null` is skipped.

## Investment funds (fondos de inversión)

Funds need **no special provider**. Yahoo carries them as `MUTUALFUND` quotes,
and the daily `Close` of a fund symbol *is* its NAV — so a fund is just
`price_source: "yfinance"` like any ETF. The catch is that Yahoo does not price
a fund under its ISIN: it uses an opaque `0P…` symbol. Find it with:

```bash
poetry run python -m scripts.resolve_symbol IE00B03HD316
# SYMBOL           TYPE         CCY   NAME
# 0P000015J7.F     MUTUALFUND   EUR   Vanguard Global Stock Index Fund EUR Hedged Acc
```

Then tag the instrument with `price_source: "yfinance"` and
`provider_ref: "0P000015J7.F"`. The batch itself never does this lookup — it
always reads a concrete `provider_ref` — so a scheduled run stays deterministic
and gains no extra network dependency.

Three things to get right for funds:

- **Keep the ISIN in `symbol`.** Convention: `symbol` holds the ISIN (the
  identifier a human recognises), `provider_ref` holds the Yahoo `0P…` code (the
  one a machine needs). The `0P…` code is meaningless on its own, so without this
  you lose track of which fund a row actually is.
- **Match the share class currency.** The same fund is sold in several classes:
  Vanguard Global Stock Index is EUR-hedged at NAV ≈45.41 *and* USD at ≈72.29.
  `instrument.currency` must be the currency of the class you actually hold, or
  the EUR conversion will silently misvalue the position. `resolve_symbol` prints
  the currency of each candidate for exactly this reason.
- **A lagging NAV is normal, not a bug.** Funds publish one NAV per day after a
  cutoff, so a fund's newest price is typically a few days older than a stock's
  (e.g. NAV of the 10th while equities are already priced to the 14th). Valuation
  reads "the latest price on or before the as-of date", so net worth just uses
  the most recent NAV — nothing to fix.

## Running it

Locally (from `backend/`, so `app.*` imports and the root `.env` resolve):

```bash
poetry run python -m scripts.update_prices               # normal run
poetry run python -m scripts.update_prices --dry-run -v  # preview, no writes
poetry run python -m scripts.update_prices --lookback-days 60
```

Via Docker Compose (reuses the backend image; not started by `up`):

```bash
docker compose run --rm batch
```

Exit code is `0` if every instrument and the FX step succeeded, `1` otherwise
— a partial failure still commits what succeeded, so a scheduler should alert
on non-zero rather than blindly retry the whole run.

## Scheduling

### cron (on the Docker host)

```cron
15 23 * * 1-5  cd /path/to/cim && docker compose run --rm batch >> /var/log/cim-prices.log 2>&1
```

Weekdays at 23:15 — after US market close and the ECB's ~16:00 CET reference
rate publication. Running over the weekend is harmless (idempotent) but
writes nothing new for stocks/FX; if you hold crypto and want daily coverage
regardless, use `* * *` instead of `1-5`.

### systemd timer

`/etc/systemd/system/cim-prices.service`:

```ini
[Unit]
Description=CIM price/FX batch

[Service]
Type=oneshot
WorkingDirectory=/path/to/cim
ExecStart=/usr/bin/docker compose run --rm batch
```

`/etc/systemd/system/cim-prices.timer`:

```ini
[Unit]
Description=Run the CIM price/FX batch on weekdays at 23:15

[Timer]
OnCalendar=Mon..Fri 23:15
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now cim-prices.timer
journalctl -u cim-prices -f   # logs
```

`Persistent=true` runs a missed timer as soon as the machine is back up
(e.g. after it was off overnight) — the gap-fill window then catches up.
