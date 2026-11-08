from datetime import date
import pytest
import httpx
from fastapi.testclient import TestClient

from api_adapter.main import app, service
from api_adapter.service import AdapterAccountService


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(service, "state_path", tmp_path / "astro_state.json")
    monkeypatch.setattr(service, "_budget_requests", {})
    monkeypatch.setattr(service, "_budget_preferences", {})
    return TestClient(app)


def test_requested_amount_ignores_dates():
    assert AdapterAccountService._requested_amount(
        "Can I afford $400 in December 2026?"
    ) == 400
    assert AdapterAccountService._requested_amount("Can I afford $1,200 in June?") == 1200


def test_requested_dates():
    current = date(2026, 12, 31)
    assert AdapterAccountService._requested_date(
        "Can I afford $400 in December 2026?", current
    ) == date(2026, 12, 1)
    assert AdapterAccountService._requested_date("a trip next month", current) == date(2027, 1, 1)


def test_trip_without_cost_asks_for_cost(client):
    response = client.post(
        "/accounts/61163/assistant", json={"prompt": "Can I afford a trip next month?"}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["question_kind"] == "purchase"
    assert result["data"]["requested_amount"] is None
    assert "cost" in result["message"].lower()
    assert "balance_projection" not in result["tool_trace"]


def test_trip_with_cost_uses_next_month_and_projection(client):
    response = client.post(
        "/accounts/61163/assistant", json={"prompt": "Can I afford a $400 trip next month?"}
    )
    assert response.status_code == 200
    result = response.json()
    as_of = date.fromisoformat(result["data"]["data_as_of"])
    expected = date(as_of.year + (as_of.month == 12), as_of.month % 12 + 1, 1)
    assert result["data"]["requested_date"] == expected.isoformat()
    assert result["data"]["requested_amount"] == 400
    assert "balance_projection" in result["tool_trace"]
    assert "runway_calculator" in result["tool_trace"]
    assert "$400" in result["message"]
    assert "latest account data" in result["message"]
    assert result["data"]["conclusion"] == "informational"


def test_different_questions_get_relevant_engine_responses(client):
    def ask(prompt):
        response = client.post("/accounts/61163/assistant", json={"prompt": prompt})
        assert response.status_code == 200
        return response.json()["message"]

    bills = ask("How much do I spend on bills?")
    income = ask("What is my income?")
    unknown = ask("What is the weather?")
    assert "fixed costs" in bills
    assert "income" in income
    assert "can't answer" in unknown
    assert len({bills, income, unknown}) == 3


def test_unrelated_future_question_is_not_a_balance_forecast(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "What is the weather next month?"
    })
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["question_kind"] == "other"
    assert "can't answer" in result["message"]
    assert "balance_projection" not in result["tool_trace"]


def test_explicit_budget_request_with_target_creates_budget(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "Create a budget to help me save $500 per paycheck"
    })
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["requested_savings_amount"] == 500
    assert result["data"]["requested_savings_cadence"] == "paycheck"
    assert result["data"]["budget_plan"][-1]["name"] == "Requested savings (paycheck)"
    assert "budget_planner" in result["tool_trace"]
    assert client.get("/accounts/61163/budgets").json()["goals"]


def test_budget_state_persists_by_account(tmp_path):
    data_dir = tmp_path / "parquet"
    service = AdapterAccountService(data_dir)
    service._budget_requests = {20111: ["create a budget"]}
    service._budget_preferences = {20111: {"amount": None, "cadence": "month"}}
    service._save_state()
    restored = AdapterAccountService(data_dir)
    assert restored._budget_requests == {20111: ["create a budget"]}


def test_specific_question_returns_engine_calculation(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "Can I afford a $400 trip in December 2026?"
    })
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["requested_date"] == "2026-12-01"
    assert "balance_projection" in result["tool_trace"]


def test_past_request_is_not_silently_moved(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "Can I afford a $400 trip in January 2020?"
    })
    assert response.status_code == 422
    assert "available forecast" in response.json()["detail"]


def test_gemini_rewrite_rejects_unverified_numbers():
    profile = {"income": 1000.0}
    details = {"requested_amount": 400.0, "conclusion": "informational"}
    assert AdapterAccountService._valid_gemini_text(
        '{"answer":"You bring in $1,000 and the purchase is $400.","conclusion":"informational"}',
        profile, "You bring in $1,000.", details,
    )
    assert not AdapterAccountService._valid_gemini_text(
        '{"answer":"You bring in $1,000 and the purchase is $900.","conclusion":"informational"}',
        profile, "You bring in $1,000.", details,
    )


def test_gemini_response_is_used_when_valid(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text":
            '{"answer":"Here is your income estimate.","conclusion":"informational"}'
        }]}}]}
    ))
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "What is my income?"
    }).json()
    assert result["message"] == "Here is your income estimate."
    assert result["data"]["gemini_status"] == "used"
    assert "gemini" in result["tool_trace"]


def test_gemini_failure_returns_specific_engine_response(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(503))
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "What is my income?"
    }).json()
    assert "typical income" in result["message"]
    assert result["data"]["gemini_status"] == "error"
    assert "gemini_error" in result["tool_trace"]
