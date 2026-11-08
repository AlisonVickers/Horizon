
from datetime import date

from app.services.payday_spending import PaydaySpendingService
from app.services.dashboard_service import DashboardService


def test_calculates_allowance_before_payday():
    result = PaydaySpendingService().calculate(
        starting_balance=2000,
        events=[
            {
                "date": "2026-01-05",
                "amount": -400,
                "event_type": "expense",
            },
            {
                "date": "2026-01-15",
                "amount": 1500,
                "event_type": "income",
            },
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
        safety_buffer=500,
    )

    assert result["status"] == "estimated"
    assert result["next_payday"] == "2026-01-15"
    assert result["days_until_payday"] == 14
    assert result["spendable_until_payday"] == 1100.0


def test_excludes_next_paycheck_from_allowance():
    result = PaydaySpendingService().calculate(
        starting_balance=1000,
        events=[
            {
                "date": "2026-01-10",
                "amount": 10000,
                "event_type": "income",
            },
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
        safety_buffer=500,
    )

    assert result["spendable_until_payday"] == 500.0


def test_unavailable_without_payday():
    result = PaydaySpendingService().calculate(
        starting_balance=1000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
    )

    assert result["status"] == "unavailable"


def test_dashboard_includes_payday_spending():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert "payday_spending" in result
    assert "status" in result["payday_spending"]


def test_unanchored_dashboard_payday_unavailable():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert result["payday_spending"]["status"] == "unavailable"
