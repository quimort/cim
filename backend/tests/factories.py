"""Terse ORM row builders for service-level tests.

Endpoint tests build data through HTTP; valuation tests exercise the service
layer directly, so they insert rows straight into the session. Amounts are
passed as strings and converted to ``Decimal`` — never floats.
"""

import itertools
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.enums import MovementType
from app.models.exchange_rate import ExchangeRate
from app.models.instrument import Instrument
from app.models.movement import Movement
from app.models.price import Price

_counter = itertools.count(1)


def ts(day: str) -> datetime:
    """A tz-aware UTC timestamp at noon of ``day`` ('YYYY-MM-DD')."""
    return datetime.fromisoformat(f"{day}T12:00:00+00:00").astimezone(UTC)


def make_account(session: Session, *, owner_id: int = 1, currency: str = "EUR") -> Account:
    account = Account(
        owner_id=owner_id,
        name=f"account-{next(_counter)}",
        type="bank",
        currency=currency,
    )
    session.add(account)
    session.commit()
    return account


def make_instrument(
    session: Session,
    *,
    asset_class: str = "tradable",
    currency: str = "EUR",
    expected_interest: str | None = None,
    maturity_date: date | None = None,
    category_id: int | None = None,
    price_source: str | None = None,
    provider_ref: str | None = None,
) -> Instrument:
    instrument = Instrument(
        name=f"instrument-{next(_counter)}",
        asset_class=asset_class,
        currency=currency,
        expected_interest=Decimal(expected_interest) if expected_interest is not None else None,
        maturity_date=maturity_date,
        category_id=category_id,
        price_source=price_source,
        provider_ref=provider_ref,
    )
    session.add(instrument)
    session.commit()
    return instrument


def make_category(session: Session, *, name: str | None = None) -> Category:
    category = Category(name=name if name is not None else f"category-{next(_counter)}")
    session.add(category)
    session.commit()
    return category


def make_movement(
    session: Session,
    account: Account,
    *,
    type: MovementType,
    quantity: str,
    occurred_at: datetime,
    instrument: Instrument | None = None,
    price: str | None = None,
    fee: str | None = None,
    currency: str | None = None,
    transfer_id: uuid.UUID | None = None,
    voided: bool = False,
) -> Movement:
    movement = Movement(
        occurred_at=occurred_at,
        account_id=account.id,
        instrument_id=instrument.id if instrument is not None else None,
        type=type.value,
        quantity=Decimal(quantity),
        price=Decimal(price) if price is not None else None,
        fee=Decimal(fee) if fee is not None else None,
        currency=currency if currency is not None else account.currency,
        transfer_id=transfer_id,
        voided_at=datetime.now(UTC) if voided else None,
    )
    session.add(movement)
    session.commit()
    return movement


def make_price(
    session: Session, instrument: Instrument, *, day: str, value: str, currency: str | None = None
) -> Price:
    price = Price(
        instrument_id=instrument.id,
        date=date.fromisoformat(day),
        value=Decimal(value),
        currency=currency if currency is not None else instrument.currency,
    )
    session.add(price)
    session.commit()
    return price


def make_fx(session: Session, *, day: str, base: str, quote: str, rate: str) -> ExchangeRate:
    row = ExchangeRate(
        date=date.fromisoformat(day),
        base_currency=base,
        quote_currency=quote,
        rate=Decimal(rate),
    )
    session.add(row)
    session.commit()
    return row
