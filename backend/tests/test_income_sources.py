import pandas as pd

from app.services.income_detector import IncomeDetector


def make_transactions(bank, account, start="2023-07-14", months=6):
    start_date = pd.Timestamp(start)

    dates = [
        start_date + pd.DateOffset(months=i)
        for i in range(months)
    ]

    return pd.DataFrame({
        "date": dates,
        "signed_amount": [2000.0] * months,
        "operation": ["transfer in from another bank"] * months,
        "partner_bank": [bank] * months,
        "partner_account": [account] * months,
    })


def test_fully_unsourced_income_is_excluded():
    transactions = make_transactions(None, None)

    assert IncomeDetector().detect(transactions) == []


def test_identified_income_is_detected():
    transactions = make_transactions("IJ", "978094")

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "monthly"
    assert patterns[0].typical_amount == 2000.0
    assert patterns[0].day_of_month == 14
    assert patterns[0].source_quality == "complete"

def test_partially_identified_income_is_detected():
    transactions = make_transactions(
        bank="IJ",
        account=None,
    )

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "monthly"
    assert patterns[0].source_key == "IJ|"
    assert patterns[0].source_quality == "partial"
    assert patterns[0].confidence == "low"
