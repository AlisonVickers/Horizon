
from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_forecast_success():
    response = client.get(
        "/api/accounts/61163/forecast",
        params={
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["account_id"] == 61163
    assert data["forecast_type"] == "historical_pattern_simulation"
    assert data["data_as_of"] == "2025-12-31"

    assert data["start_date"] == "2026-02-01"
    assert data["end_date"] == "2026-02-28"

    assert all(
        "2026-02-01" <= event["date"] <= "2026-02-28"
        for event in data["events"]
    )

    assert any(
        event["date"] == "2026-02-28"
        and event["category"] == "statement fee"
        for event in data["events"]
    )


def test_invalid_date_range():
    response = client.get(
        "/api/accounts/61163/forecast",
        params={
            "start_date": "2026-02-28",
            "end_date": "2026-02-01",
        },
    )

    assert response.status_code == 422


def test_invalid_account_id():
    response = client.get("/api/accounts/-1/forecast")

    assert response.status_code == 422


def test_dashboard_returns_financial_summary():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["account_id"] == 61163
    assert data["forecast_type"] == "historical_pattern_simulation"
    assert data["data_as_of"] == "2025-12-31"

    assert data["balance"]["historical_month_end_balance"] == 39745.45
    assert data["balance"]["is_live"] is False

    assert data["cashflow"]["predicted_recurring_income"] == 13818.14
    assert data["cashflow"]["predicted_recurring_expenses"] == 3241.75
    assert data["cashflow"]["event_count"] == 6

    assert len(data["events"]) == 6


def test_dashboard_rejects_invalid_date_range():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-02-28",
            "end_date": "2026-02-01",
        },
    )

    assert response.status_code == 422


def test_dashboard_rejects_negative_account_id():
    response = client.get(
        "/api/accounts/-1/dashboard"
    )

    assert response.status_code == 422


def test_dashboard_rejects_excessive_date_range():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2027-02-01",
        },
    )

    assert response.status_code == 422

def test_dashboard_includes_projected_balance():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    assert response.status_code == 200

    data = response.json()
    projection = data["projected_balance"]

    assert projection is not None
    assert projection["starting_balance"] == 39745.45
    assert projection["projected_ending_balance"] == 50321.84
    assert projection["lowest_projected_balance"] == 36512.89
    assert len(projection["timeline"]) == 6

    assert (
        projection["projection_scope"]
        == "detected_recurring_events_only"
    )


def test_dashboard_does_not_assume_february_starting_balance():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["projected_balance"] is None

def test_dashboard_triggers_low_balance_warning():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "safety_buffer": 40000,
        },
    )

    assert response.status_code == 200

    alerts = response.json()["balance_alerts"]

    assert alerts["status"] == "warning"
    assert alerts["safety_buffer"] == 40000.0
    assert alerts["alerts"][0]["type"] == (
        "starting_balance_below_buffer"
    )
    assert alerts["alerts"][0]["shortfall"] == 254.55


def test_dashboard_default_safety_buffer():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    assert response.status_code == 200

    alerts = response.json()["balance_alerts"]

    assert alerts["status"] == "ok"
    assert alerts["safety_buffer"] == 500.0
    assert alerts["alerts"] == []


def test_dashboard_rejects_negative_safety_buffer():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={"safety_buffer": -100},
    )

    assert response.status_code == 422

def test_dashboard_triggers_low_balance_warning():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "safety_buffer": 40000,
        },
    )

    assert response.status_code == 200

    alerts = response.json()["balance_alerts"]

    assert alerts["status"] == "warning"
    assert alerts["safety_buffer"] == 40000.0
    assert alerts["alerts"][0]["type"] == (
        "starting_balance_below_buffer"
    )
    assert alerts["alerts"][0]["shortfall"] == 254.55


def test_dashboard_default_safety_buffer():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    assert response.status_code == 200

    alerts = response.json()["balance_alerts"]

    assert alerts["status"] == "ok"
    assert alerts["safety_buffer"] == 500.0
    assert alerts["alerts"] == []


def test_dashboard_rejects_negative_safety_buffer():
    response = client.get(
        "/api/accounts/61163/dashboard",
        params={"safety_buffer": -100},
    )

    assert response.status_code == 422

