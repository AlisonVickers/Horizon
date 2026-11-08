
from datetime import date

from app.services.smart_alert import SmartAlertService
from app.services.dashboard_service import DashboardService


def test_detects_low_balance_after_spending():
    result = SmartAlertService().analyze(
        starting_balance=1000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=900,
        safety_buffer=500,
    )

    assert result["status"] == "estimated"
    assert any(
        alert["type"] == "projected_low_balance"
        for alert in result["alerts"]
    )


def test_no_alert_when_balance_is_sufficient():
    result = SmartAlertService().analyze(
        starting_balance=10000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=900,
        safety_buffer=500,
    )

    assert result["alerts"] == []


def test_starting_below_buffer():
    result = SmartAlertService().analyze(
        starting_balance=200,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        monthly_variable_outflow=100,
        safety_buffer=500,
    )

    assert result["alerts"][0]["type"] == "starting_low_balance"


def test_dashboard_includes_smart_alerts():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert "smart_alerts" in result
    assert result["smart_alerts"]["status"] == "estimated"
    assert "typical" in result["smart_alerts"]
    assert "conservative" in result["smart_alerts"]


def test_unanchored_dashboard_alerts_unavailable():
    result = DashboardService().get_dashboard(
        account_id=61163,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert result["smart_alerts"]["status"] == "unavailable"
