from enum import StrEnum


class MovementType(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    PRINCIPAL_REPAYMENT = "principal_repayment"


class AssetClass(StrEnum):
    TRADABLE = "tradable"
    CASH = "cash"
    LOAN = "loan"


class LoanStatus(StrEnum):
    ACTIVE = "active"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
