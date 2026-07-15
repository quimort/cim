"""CLI wiring tests (task 1f): argument parsing and exit-code mapping.

``run_update`` is monkeypatched — it's fully exercised in
``test_update_prices_runner.py``. Instantiating ``SessionLocal``/``httpx.Client``
doesn't touch the network (SQLAlchemy engines and httpx clients connect
lazily), so this test never reaches the real database.
"""

import pytest

from app.services.market_data.types import RunSummary
from scripts import update_prices


def _summary(**overrides: object) -> RunSummary:
    summary = RunSummary()
    for key, value in overrides.items():
        setattr(summary, key, value)
    return summary


def test_main_exits_zero_on_a_clean_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        update_prices.runner, "run_update", lambda *a, **k: _summary(instruments_ok=1)
    )
    assert update_prices.main(["--dry-run"]) == 0


def test_main_exits_one_on_any_instrument_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        update_prices.runner,
        "run_update",
        lambda *a, **k: _summary(instruments_failed=1, failures=["instrument 1"]),
    )
    assert update_prices.main(["--dry-run"]) == 1


def test_main_exits_one_on_fx_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        update_prices.runner,
        "run_update",
        lambda *a, **k: _summary(fx_failed=True, failures=["fx rates"]),
    )
    assert update_prices.main(["--dry-run"]) == 1


def test_lookback_days_argument_is_parsed() -> None:
    args = update_prices._parse_args(["--lookback-days", "60"])
    assert args.lookback_days == 60
    assert args.dry_run is False


def test_dry_run_and_verbose_flags_are_parsed() -> None:
    args = update_prices._parse_args(["--dry-run", "--verbose"])
    assert args.dry_run is True
    assert args.verbose is True


def test_defaults() -> None:
    args = update_prices._parse_args([])
    assert args.lookback_days == 30
    assert args.dry_run is False
    assert args.verbose is False
