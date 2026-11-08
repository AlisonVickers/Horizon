
import pandas as pd

from app.services.expense_detector import ExpenseDetector


def make_expenses(dates, amount=100.0):
    return pd.DataFrame({
        "date": dates,
        "signed_amount": [-amount] * len(dates),
        "operation": ["transfer out to another bank"] * len(dates),
        "partner_bank": ["TEST"] * len(dates),
        "partner_account": ["BILL001"] * len(dates),
        "purpose": ["test bill"] * len(dates),
    })


def test_weekly_expense():
    dates = pd.date_range(
        "2025-10-03", periods=8, freq="7D"
    )

    patterns = ExpenseDetector().detect(
        make_expenses(dates)
    )

    assert len(patterns) == 1
    assert patterns[0].frequency == "weekly"


def test_biweekly_expense():
    dates = pd.date_range(
        "2025-09-05", periods=8, freq="14D"
    )

    patterns = ExpenseDetector().detect(
        make_expenses(dates)
    )

    assert len(patterns) == 1
    assert patterns[0].frequency == "biweekly"


def test_month_end_expense():
    dates = pd.date_range(
        "2025-07-31", periods=6, freq="ME"
    )

    patterns = ExpenseDetector().detect(
        make_expenses(dates, amount=25.0)
    )

    assert len(patterns) == 1
    assert patterns[0].frequency == "monthly"
    assert patterns[0].day_of_month is None


def test_semimonthly_expense():
    dates = pd.to_datetime([
        "2025-09-01", "2025-09-15",
        "2025-10-01", "2025-10-15",
        "2025-11-01", "2025-11-15",
        "2025-12-01", "2025-12-15",
    ])

    patterns = ExpenseDetector().detect(
        make_expenses(dates)
    )

    assert len(patterns) == 1
    assert patterns[0].frequency == "semimonthly"


def test_custom_interval_expense():
    dates = pd.date_range(
        "2025-10-01", periods=8, freq="10D"
    )

    patterns = ExpenseDetector().detect(
        make_expenses(dates)
    )

    assert len(patterns) == 1
    assert patterns[0].frequency == "custom"
    assert patterns[0].interval_days == 10.0
