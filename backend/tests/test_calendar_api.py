
from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_calendar_returns_three_months():
    response = client.get(
        "/api/accounts/61163/calendar",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "estimated"
    assert len(data["months"]) == 3
    assert data["months"][0]["month"] == "2026-01"


def test_calendar_rejects_invalid_dates():
    response = client.get(
        "/api/accounts/61163/calendar",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-01-01",
        },
    )

    assert response.status_code == 400


def test_calendar_rejects_negative_buffer():
    response = client.get(
        "/api/accounts/61163/calendar",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "safety_buffer": -100,
        },
    )

    assert response.status_code == 422
