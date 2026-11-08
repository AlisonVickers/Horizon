
from datetime import date

from app.services.cashflow_forecast import CashflowForecastService
from app.services.expense_detector import ExpensePattern


def test_month_end_forecast():
    expense = ExpensePattern(
        category="statement fee",
        typical_amount=9.19,
        day_of_month=None,
        frequency="monthly",
        confidence="high",
        observations=12,
        source_key="fee",
        last_observed_date="2025-12-31",
        month_end=True,
    )

    events = CashflowForecastService().forecast(
        income_patterns=[],
        expense_patterns=[expense],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )

    assert [event.date for event in events] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]

    assert all(event.amount == -9.19 for event in events)
