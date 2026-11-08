
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Classification:
    category: str
    confidence: Confidence
    is_recurring: bool = False


class TransactionClassifier:
    """Classify transactions without discarding unknown records."""

    @staticmethod
    def _normalize(value) -> str:
        """Convert missing values and text to a consistent format."""
        if pd.isna(value):
            return ""

        return str(value).strip().lower()

    def classify(self, transaction: dict) -> Classification:
        """Return a classification for a single transaction."""

        operation = self._normalize(transaction.get("operation"))
        purpose = self._normalize(transaction.get("purpose"))

        # Recognized incoming transactions
        if operation == "interest":
            return Classification(
                category="interest_income",
                confidence=Confidence.HIGH,
            )

        if operation == "transfer in from another bank":
            return Classification(
                category="incoming_transfer",
                confidence=Confidence.HIGH,
            )

        if operation == "cash deposit":
            return Classification(
                category="cash_deposit",
                confidence=Confidence.HIGH,
            )

        # Recognized expense purposes
        if "insurance" in purpose:
            return Classification(
                category="insurance",
                confidence=Confidence.MEDIUM,
            )

        if "household" in purpose:
            return Classification(
                category="household_bills",
                confidence=Confidence.MEDIUM,
            )

        if "loan payment" in purpose:
            return Classification(
                category="loan_payment",
                confidence=Confidence.HIGH,
            )

        # Other outgoing transaction types
        if operation == "bank fee":
            return Classification(
                category="bank_fee",
                confidence=Confidence.HIGH,
            )

        if operation == "cash withdrawal":
            return Classification(
                category="cash_withdrawal",
                confidence=Confidence.HIGH,
            )

        if operation == "transfer out to another bank":
            return Classification(
                category="outgoing_transfer",
                confidence=Confidence.HIGH,
            )
        if operation == "card withdrawal":
            return Classification(
                category="card_withdrawal",
                confidence=Confidence.HIGH,
            )

        # Keep unfamiliar transactions rather than guessing
        return Classification(
            category="unknown",
            confidence=Confidence.LOW,
        )
