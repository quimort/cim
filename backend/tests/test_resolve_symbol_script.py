"""CLI wiring for the symbol resolver: arg parsing and exit-code mapping.

``resolve_symbol`` itself is exercised in ``test_market_data_providers.py``;
here it is monkeypatched, so no network is touched.
"""

import pytest

from app.services.market_data.yfinance_provider import SymbolCandidate
from scripts import resolve_symbol as cli

_FUND = SymbolCandidate(
    symbol="0P000015J7.F",
    quote_type="MUTUALFUND",
    exchange="FRA",
    name="Vanguard Global Stock Index Fund EUR Hedged Acc",
    currency="EUR",
)


def test_exits_zero_and_prints_the_symbol_when_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "resolve_symbol", lambda query, max_results: [_FUND])

    assert cli.main(["IE00B03HD316"]) == 0

    out = capsys.readouterr().out
    assert "0P000015J7.F" in out
    assert "MUTUALFUND" in out
    assert "EUR" in out


def test_exits_one_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "resolve_symbol", lambda query, max_results: [])

    assert cli.main(["nonsense"]) == 1
    assert "No Yahoo symbol found" in capsys.readouterr().out


def test_a_candidate_without_a_currency_still_prints(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    unknown = SymbolCandidate(
        symbol="XYZ", quote_type="EQUITY", exchange="NMS", name="Xyz", currency=None
    )
    monkeypatch.setattr(cli, "resolve_symbol", lambda query, max_results: [unknown])

    assert cli.main(["XYZ"]) == 0
    assert "XYZ" in capsys.readouterr().out


def test_defaults_and_limit_are_parsed() -> None:
    assert cli._parse_args(["IE00B03HD316"]).limit == 6
    args = cli._parse_args(["IE00B03HD316", "--limit", "3"])
    assert args.query == "IE00B03HD316"
    assert args.limit == 3
