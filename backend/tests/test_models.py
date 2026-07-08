from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Account, ExchangeRate, Instrument, Movement, Price
from app.models.enums import AssetClass, MovementType


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_account(session: Session, name: str = "Test broker", owner_id: int = 1) -> Account:
    account = Account(name=name, type="broker", currency="EUR", owner_id=owner_id)
    session.add(account)
    session.flush()
    return account


def _make_instrument(session: Session) -> Instrument:
    instrument = Instrument(
        name="Some ETF",
        symbol="ETF0",
        asset_class=AssetClass.TRADABLE,
        currency="EUR",
    )
    session.add(instrument)
    session.flush()
    return instrument


def test_movement_roundtrip_preserves_decimal_precision(session: Session) -> None:
    account = _make_account(session)
    instrument = _make_instrument(session)

    movement = Movement(
        occurred_at=datetime.now(UTC),
        account_id=account.id,
        instrument_id=instrument.id,
        type=MovementType.PURCHASE,
        quantity=Decimal("1.23456789"),
        price=Decimal("100.12345678"),
        fee=Decimal("0.99"),
        currency="EUR",
    )
    session.add(movement)
    session.commit()

    fetched = session.get(Movement, movement.id)
    assert fetched is not None
    assert fetched.quantity == Decimal("1.23456789")
    assert fetched.price == Decimal("100.12345678")
    assert fetched.source == "manual"
    assert fetched.voided_at is None


def test_account_owner_id_defaults_to_single_user(session: Session) -> None:
    account = Account(name="Default owner", type="bank", currency="EUR")
    session.add(account)
    session.commit()

    fetched = session.get(Account, account.id)
    assert fetched is not None
    assert fetched.owner_id == 1


def test_account_name_is_unique_per_owner(session: Session) -> None:
    _make_account(session, name="Checking", owner_id=1)
    session.commit()

    # Same name under a different owner is fine — this is the multi-tenant point.
    _make_account(session, name="Checking", owner_id=2)
    session.commit()

    # Same name under the same owner is rejected.
    session.add(Account(name="Checking", type="bank", currency="EUR", owner_id=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_movement_type_check_constraint_rejects_invalid_value(session: Session) -> None:
    account = _make_account(session)

    movement = Movement(
        occurred_at=datetime.now(UTC),
        account_id=account.id,
        type="not_a_real_type",
        quantity=Decimal("1"),
        currency="EUR",
    )
    session.add(movement)
    with pytest.raises(IntegrityError):
        session.commit()


def test_instrument_asset_class_check_constraint_rejects_invalid_value(session: Session) -> None:
    instrument = Instrument(
        name="Broken",
        asset_class="not_a_real_class",
        currency="EUR",
    )
    session.add(instrument)
    with pytest.raises(IntegrityError):
        session.commit()


def test_movement_source_external_id_unique_constraint(session: Session) -> None:
    account = _make_account(session)

    def make(external_id: str | None) -> Movement:
        return Movement(
            occurred_at=datetime.now(UTC),
            account_id=account.id,
            type=MovementType.DEPOSIT,
            quantity=Decimal("100"),
            currency="EUR",
            source="kraken",
            external_id=external_id,
        )

    session.add(make("trade-1"))
    session.commit()

    session.add(make("trade-1"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # Multiple NULL external_ids (e.g. manual entries) must remain unrestricted.
    session.add(make(None))
    session.add(make(None))
    session.commit()


def test_price_instrument_date_unique_constraint(session: Session) -> None:
    instrument = _make_instrument(session)

    session.add(
        Price(
            instrument_id=instrument.id,
            date=datetime.now(UTC).date(),
            value=Decimal("10.5"),
            currency="EUR",
        )
    )
    session.commit()

    session.add(
        Price(
            instrument_id=instrument.id,
            date=datetime.now(UTC).date(),
            value=Decimal("11"),
            currency="EUR",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_exchange_rate_date_pair_unique_constraint(session: Session) -> None:
    today = datetime.now(UTC).date()
    session.add(
        ExchangeRate(date=today, base_currency="EUR", quote_currency="USD", rate=Decimal("1.1"))
    )
    session.commit()

    session.add(
        ExchangeRate(date=today, base_currency="EUR", quote_currency="USD", rate=Decimal("1.2"))
    )
    with pytest.raises(IntegrityError):
        session.commit()
