
from datetime import date

from app.services.dashboard_service import DashboardService


def test_dashboard_returns_both_scenarios():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert "safe_to_spend" in result
    assert "conservative_safe_to_spend" in result

    typical = result["safe_to_spend"]
    conservative = result["conservative_safe_to_spend"]

    assert typical["status"] == "estimated"
    assert conservative["status"] == "estimated"

    assert (
        conservative["safe_to_spend"]
        <= typical["safe_to_spend"]
    )


def test_conservative_scenario_unavailable_without_anchor():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert (
        result["conservative_safe_to_spend"]["status"]
        == "unavailable"
    )
