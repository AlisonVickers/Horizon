
import pandas as pd

from app.services.income_detector import IncomeDetector


def test_detects_biweekly_income():
    # Simulate ten deposits, exactly 14 days apart.
    dates = pd.date_range(
        start="2025-03-07",
        periods=10,
        freq="14D",
    )

    transactions = pd.DataFrame({
        "date": dates,
        "signed_amount": [1500.0] * len(dates),
        "operation": ["transfer in from another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["PAYROLL"] * len(dates),
    })

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "biweekly"
    assert patterns[0].typical_amount == 1500.0
    assert patterns[0].observations == 10


def test_detects_weekly_income():
    dates = pd.date_range(
        start="2025-10-03",
        periods=8,
        freq="7D",
    )

    transactions = pd.DataFrame({
        "date": dates,
        "signed_amount": [1200.0] * len(dates),
        "operation": ["transfer in from another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["WEEKLY"] * len(dates),
    })

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "weekly"
    assert patterns[0].typical_amount == 1200.0
    assert patterns[0].observations == 8
def test_detects_custom_income_frequency():
    dates = pd.date_range(
        start="2025-10-01",
        periods=8,
        freq="10D",
    )

    transactions = pd.DataFrame({
        "date": dates,
        "signed_amount": [1800.0] * len(dates),
        "operation": ["transfer in from another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["CUSTOM"] * len(dates),
    })

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "custom"
    assert patterns[0].typical_amount == 1800.0
    assert patterns[0].observations == 8

def test_detects_semimonthly_income():
    dates = pd.to_datetime([
        "2025-09-01",
        "2025-09-15",
        "2025-10-01",
        "2025-10-15",
        "2025-11-01",
        "2025-11-15",
        "2025-12-01",
        "2025-12-15",
    ])

    transactions = pd.DataFrame({
        "date": dates,
        "signed_amount": [2500.0] * len(dates),
        "operation": ["transfer in from another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["SEMIMONTHLY"] * len(dates),
    })

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "semimonthly"
    assert patterns[0].typical_amount == 2500.0
    assert patterns[0].observations == 8

def test_detects_custom_income_interval():
    dates = pd.date_range(
        start="2025-10-01",
        periods=8,
        freq="10D",
    )

    transactions = pd.DataFrame({
        "date": dates,
        "signed_amount": [1800.0] * len(dates),
        "operation": ["transfer in from another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["CUSTOM"] * len(dates),
    })

    patterns = IncomeDetector().detect(transactions)

    assert len(patterns) == 1
    assert patterns[0].frequency == "custom"
    assert patterns[0].interval_days == 10.0
    assert patterns[0].typical_amount == 1800.0
