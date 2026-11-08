
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_trip_scenario_api():
    response = client.post(
        "/api/accounts/61163/simulate",
        json={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "scenario_type": "one_time_expense",
            "amount": 1200,
            "scenario_date": "2026-01-20",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "estimated"
    assert data["change_in_lowest_balance"] == -1200.0


def test_income_reduction_api():
    response = client.post(
        "/api/accounts/61163/simulate",
        json={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "scenario_type": "income_reduction",
            "income_reduction_percent": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "estimated"


def test_rejects_invalid_scenario():
    response = client.post(
        "/api/accounts/61163/simulate",
        json={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "scenario_type": "unknown",
        },
    )

    assert response.status_code == 400


def test_rejects_negative_amount():
    response = client.post(
        "/api/accounts/61163/simulate",
        json={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "scenario_type": "one_time_expense",
            "amount": -100,
            "scenario_date": "2026-01-20",
        },
    )

    assert response.status_code == 422


def test_unanchored_scenario_unavailable():
    response = client.post(
        "/api/accounts/61163/simulate",
        json={
            "start_date": "2026-02-01",
            "end_date": "2026-03-31",
            "scenario_type": "income_reduction",
            "income_reduction_percent": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
