"""EUR conversion: pair lookup by date, inverse fallback, and hard failure."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.services.errors import DomainRuleError
from app.services.valuation import convert_to_eur, rate_to_eur
from tests.factories import make_fx


def test_latest_rate_on_or_before_as_of_wins(session: Session) -> None:
    make_fx(session, day="2026-01-05", base="USD", quote="EUR", rate="0.9")
    make_fx(session, day="2026-01-15", base="USD", quote="EUR", rate="0.95")

    # The 01-15 row is in the future of the as-of date and must be ignored.
    assert rate_to_eur(session, "USD", date(2026, 1, 10)) == Decimal("0.9")
    assert convert_to_eur(session, Decimal("100"), "USD", date(2026, 1, 10)) == Decimal("90.0")

    # At a later as-of date the newer row takes over.
    assert rate_to_eur(session, "USD", date(2026, 1, 20)) == Decimal("0.95")


def test_inverse_pair_fallback(session: Session) -> None:
    # Only EUR->USD exists; USD->EUR must be derived as 1/rate.
    make_fx(session, day="2026-01-05", base="EUR", quote="USD", rate="1.25")

    assert rate_to_eur(session, "USD", date(2026, 1, 10)) == Decimal("0.8")


def test_direct_pair_preferred_over_inverse(session: Session) -> None:
    make_fx(session, day="2026-01-05", base="USD", quote="EUR", rate="0.9")
    make_fx(session, day="2026-01-05", base="EUR", quote="USD", rate="1.25")

    assert rate_to_eur(session, "USD", date(2026, 1, 10)) == Decimal("0.9")


def test_eur_is_identity_without_any_rows(session: Session) -> None:
    assert rate_to_eur(session, "EUR", date(2026, 1, 1)) == Decimal(1)


def test_missing_rate_raises(session: Session) -> None:
    # A rate that only exists after the as-of date is as good as absent.
    make_fx(session, day="2026-02-01", base="USD", quote="EUR", rate="0.9")

    with pytest.raises(DomainRuleError, match="USD->EUR"):
        rate_to_eur(session, "USD", date(2026, 1, 10))
