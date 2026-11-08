
from datetime import date

import pandas as pd
import pytest

from app.services.variable_spending import VariableSpendingEstimator


def make_transactions(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "operation", "signed_amount"],
    )


def test_estimates_median_monthly_withdrawals():
    df = make_transactions([
        ("2025-01-10", "cash withdrawal", -300.0),
        ("2025-02-10", "cash withdrawal", -600.0),
        ("2025-03-10", "cash withdrawal", -900.0),
        ("2025-03-15", "transfer out to another bank", -500.0),
    ])

    result = VariableSpendingEstimator().estimate(
        df, as_of=date(2025, 3, 31), lookback_months=3
    )

    assert result["status"] == "estimated"
    assert result["monthly_estimate"] == 600.0
    assert result["daily_estimate"] == 19.71


def test_includes_zero_withdrawal_months():
    df = make_transactions([
        ("2025-01-10", "cash withdrawal", -300.0),
        ("2025-03-10", "cash withdrawal", -900.0),
    ])

    result = VariableSpendingEstimator().estimate(
        df, as_of=date(2025, 3, 31), lookback_months=3
    )

    assert result["monthly_estimate"] == 300.0
    assert result["monthly_totals"][1]["amount"] == 0.0


def test_excludes_future_transactions():
    df = make_transactions([
        ("2025-01-10", "cash withdrawal", -300.0),
        ("2025-02-10", "cash withdrawal", -600.0),
        ("2025-03-10", "cash withdrawal", -900.0),
    ])

    result = VariableSpendingEstimator().estimate(
        df, as_of=date(2025, 2, 28), lookback_months=2
    )

    assert result["monthly_estimate"] == 450.0


def test_empty_transactions_return_unavailable():
    df = make_transactions([])

    result = VariableSpendingEstimator().estimate(
        df, as_of=date(2025, 12, 31)
    )

    assert result["status"] == "unavailable"
    assert result["monthly_estimate"] is None


def test_rejects_invalid_lookback():
    df = make_transactions([])

    with pytest.raises(ValueError):
        VariableSpendingEstimator().estimate(
            df, as_of=date(2025, 12, 31), lookback_months=0
        )

def test_partial_history_reports_low_coverage():
    df = make_transactions([
        ("2025-11-10", "cash withdrawal", -300.0),
        ("2025-12-10", "cash withdrawal", -600.0),
    ])

    result = VariableSpendingEstimator().estimate(
        df,
        as_of=date(2025, 12, 31),
        lookback_months=12,
    )

    assert result["status"] == "low_coverage"
    assert result["covered_months"] == 2
    assert result["coverage_ratio"] == pytest.approx(
        round(2 / 12, 3)
    )
    assert result["monthly_estimate"] == 450.0


def test_full_history_reports_adequate_coverage():
    df = make_transactions([
        ("2025-01-10", "cash withdrawal", -300.0),
        ("2025-12-10", "cash withdrawal", -600.0),
    ])

    result = VariableSpendingEstimator().estimate(
        df,
        as_of=date(2025, 12, 31),
        lookback_months=12,
    )

    assert result["status"] == "estimated"
    assert result["covered_months"] == 12
    assert result["coverage_ratio"] == 1.0
