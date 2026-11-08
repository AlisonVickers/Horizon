
from app.services.transaction_classifier import (
    TransactionClassifier,
    Confidence,
)


def test_incoming_transfer():
    classifier = TransactionClassifier()

    result = classifier.classify({
        "operation": "transfer in from another bank",
        "purpose": None,
    })

    assert result.category == "incoming_transfer"
    assert result.confidence == Confidence.HIGH
    assert result.is_recurring is False


def test_unknown_transaction():
    classifier = TransactionClassifier()

    result = classifier.classify({
        "operation": "unrecognized operation",
        "purpose": None,
    })

    assert result.category == "unknown"
    assert result.confidence == Confidence.LOW


def test_missing_description():
    classifier = TransactionClassifier()

    result = classifier.classify({
        "operation": None,
        "purpose": None,
    })

    assert result.category == "unknown"


def test_insurance():
    classifier = TransactionClassifier()

    result = classifier.classify({
        "operation": "payment",
        "purpose": "insurance payment",
    })

    assert result.category == "insurance"
