
from datetime import date

import pytest

from app.services.safe_to_spend import SafeToSpendService


def test_safe_to_spend_with_no_events():
    result = SafeToSpendService().calculate(
        starting_balance=5000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        monthly_variable_outflow=0,
        safety_buffer=500,
    )

    assert result["safe_to_spend"] == 4500.0


def test_upcoming_bill_reduces_safe_to_spend():
    result = SafeToSpendService().calculate(
        starting_balance=5000,
        events=[
            {"date": "2026-01-02", "amount": -2000}
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        monthly_variable_outflow=0,
        safety_buffer=500,
    )

    assert result["safe_to_spend"] == 2500.0


def test_future_income_does_not_hide_earlier_shortfall():
    result = SafeToSpendService().calculate(
        starting_balance=1000,
        events=[
            {"date": "2026-01-02", "amount": -800},
            {"date": "2026-01-03", "amount": 5000},
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        monthly_variable_outflow=0,
        safety_buffer=500,
    )

    assert result["safe_to_spend"] == 0.0
    assert result["lowest_adjusted_balance"] == 200.0


def test_variable_outflow_reduces_allowance():
    result = SafeToSpendService().calculate(
        starting_balance=5000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        monthly_variable_outflow=3044,
        safety_buffer=500,
    )

    assert result["safe_to_spend"] == 3500.0


def test_unavailable_estimate_blocks_calculation():
    result = SafeToSpendService().calculate(
        starting_balance=5000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        monthly_variable_outflow=0,
        variable_status="unavailable",
    )

    assert result["status"] == "unavailable"
    assert result["safe_to_spend"] is None


def test_rejects_invalid_date_range():
    with pytest.raises(ValueError):
        SafeToSpendService().calculate(
            starting_balance=5000,
            events=[],
            start_date=date(2026, 2, 1),
            end_date=date(2026, 1, 1),
            monthly_variable_outflow=100,
        )
