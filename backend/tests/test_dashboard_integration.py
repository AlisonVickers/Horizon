
from datetime import date

from app.services.dashboard_service import DashboardService


def test_dashboard_includes_spending_estimates():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert "variable_spending" in result
    assert "safe_to_spend" in result

    assert result["variable_spending"]["status"] == "estimated"
    assert result["safe_to_spend"]["status"] == "estimated"

    assert result["safe_to_spend"]["safe_to_spend"] >= 0


def test_safe_to_spend_unavailable_without_balance_anchor():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert result["projected_balance"] is None
    assert result["safe_to_spend"]["status"] == "unavailable"


def test_safety_buffer_reduces_allowance():
    low_buffer = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        safety_buffer=500,
    )

    high_buffer = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        safety_buffer=2000,
    )

    assert (
        high_buffer["safe_to_spend"]["safe_to_spend"]
        <= low_buffer["safe_to_spend"]["safe_to_spend"]
    )
    