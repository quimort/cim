"""Pydantic API contracts.

Single import surface for routers and tests: ``from app.schemas import ...``.
"""

from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.schemas.asset_class import AssetClassRead
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.common import CurrencyCode, ErrorDetail, MoneyStr
from app.schemas.exchange_rate import ExchangeRateRead
from app.schemas.instrument import InstrumentCreate, InstrumentRead, InstrumentUpdate
from app.schemas.movement import (
    MovementCreate,
    MovementRead,
    TransferCreate,
    TransferRead,
)
from app.schemas.price import PriceRead

__all__ = [
    "AccountCreate",
    "AccountRead",
    "AccountUpdate",
    "AssetClassRead",
    "CategoryCreate",
    "CategoryRead",
    "CategoryUpdate",
    "CurrencyCode",
    "ErrorDetail",
    "ExchangeRateRead",
    "InstrumentCreate",
    "InstrumentRead",
    "InstrumentUpdate",
    "MoneyStr",
    "MovementCreate",
    "MovementRead",
    "PriceRead",
    "TransferCreate",
    "TransferRead",
]
