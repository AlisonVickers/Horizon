from datetime import date
import pytest
import httpx
import pandas as pd
from fastapi.testclient import TestClient

from api_adapter.ei_reference import EIReference, EIReferenceError
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


def test_layoff_ei_scenario_uses_rate_and_duration(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "This customer was laid off. EI pays 55% of their usual income for 6 months. Do they make it?"
    })
    assert response.status_code == 200
    result = response.json()
    data = result["data"]
    assert data["question_kind"] == "job_loss_scenario"
    assert data["income_replacement_rate"] == 0.55
    assert data["benefit_duration_months"] == 6
    assert data["income_after"] == pytest.approx(data["income"] * 0.55)
    assert data["outlasts_benefit"] == (
        data["buffer"] > 0 and
        data["buffer"] >= max(data["spending"] - data["income_after"], 0) * 6
    )
    assert "resilience_scenario" in result["tool_trace"]
    assert "eligibility" in result["message"].lower()


def test_furnace_repair_costs_one_month_of_spending(client):
    response = client.post("/accounts/61163/assistant", json={
        "prompt": "my furnace dies, and the repair costs a full month of my typical spending."
    })
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["question_kind"] == "repair_scenario"
    assert result["data"]["one_off_cost"] == pytest.approx(result["data"]["spending"])
    assert result["data"]["buffer_after_cost"] == pytest.approx(
        result["data"]["buffer"] - result["data"]["spending"]
    )
    assert "repair" in result["message"].lower()
    assert "resilience_scenario" in result["tool_trace"]


@pytest.mark.parametrize("prompt", [
    "I lost my job and my pay is reduced by 55% for 6 months.",
    "I lost my job and EI pays 120% for 6 months.",
])
def test_job_loss_requires_unambiguous_valid_inputs(client, prompt):
    result = client.post("/accounts/61163/assistant", json={"prompt": prompt}).json()
    assert result["data"]["question_kind"] == "job_loss_scenario"
    assert "resilience_scenario" not in result["tool_trace"]
    assert "please" in result["message"].lower()


@pytest.mark.parametrize("prompt", [
    "The furnace needs repair",
    "The repair costs 6 months of income",
    "The repair costs $400 or $500",
])
def test_repair_requires_unambiguous_cost(client, prompt):
    result = client.post("/accounts/61163/assistant", json={"prompt": prompt}).json()
    assert result["data"]["question_kind"] == "repair_scenario"
    assert "resilience_scenario" not in result["tool_trace"]
    assert "please" in result["message"].lower()


def test_fixed_dollar_repair_scenario(client):
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "The furnace repair costs $1,200."
    }).json()
    assert result["data"]["one_off_cost"] == 1200
    assert "$1,200" in result["message"]
    assert "resilience_scenario" in result["tool_trace"]


def test_combined_scenario_is_not_silently_partially_calculated(client):
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "I was laid off, EI pays 55% for 6 months, and my furnace repair costs $400."
    }).json()
    assert result["data"]["question_kind"] == "combined_scenario"
    assert "separately" in result["message"]
    assert "resilience_scenario" not in result["tool_trace"]


@pytest.mark.parametrize(("buffer", "outlasts"), [(5999.0, False), (6000.0, True), (6001.0, True)])
def test_job_loss_period_uses_unrounded_shortfall(client, buffer, outlasts):
    profile = {
        "income": 2000.0, "spending": 2100.0,
        "household_bills": 500.0, "buffer": buffer,
    }
    _, data, _ = service._resilience_question(
        61163, "I was laid off; EI pays 55% for 6 months", profile, "job_loss_scenario"
    )
    assert data["outlasts_benefit"] is outlasts
    assert data["scenario"]["outlasts_benefit"] is outlasts


def test_scenario_result_is_not_overwritten_by_gemini(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    def unexpected_call(*args, **kwargs):
        raise AssertionError("Scenario calculations must not be rewritten")
    monkeypatch.setattr(httpx, "post", unexpected_call)
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "I was laid off; EI pays 55% for 6 months"
    }).json()
    assert "eligibility" in result["message"].lower()
    assert result["data"]["gemini_status"] == "not_needed"


def test_ei_question_uses_account_district_and_local_reference(client):
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "I was laid off. How much EI can I receive with 1,820 insurable hours?"
    }).json()
    ref = result["data"]["ei_reference"]
    assert ref["district_id"] == int(
        service._accounts.loc[service._accounts["account_id"] == 61163, "district_id"].iloc[0]
    )
    assert ref["unemployment_rate_year"] == 2023
    assert ref["insurable_hours"] == 1820
    assert ref["weeks_payable"] > 0
    assert result["data"]["income_after"] == pytest.approx(
        min(result["data"]["income"] * 12 / 52 * ref["benefit_rate"], ref["max_weekly_benefit"]) * 52 / 12
    )
    assert "historical proxy" in result["message"]
    assert "before tax" in result["message"]
    assert {"account_district", "ei_reference", "resilience_scenario"} <= set(result["tool_trace"])


@pytest.mark.parametrize("prompt", [
    "I was laid off. How does EI work?",
    "I was laid off, will I make it?",
    "I lost my job and EI pays 55% of my income.",
])
def test_ei_without_hours_gives_estimate_and_range(client, prompt):
    result = client.post("/accounts/61163/assistant", json={
        "prompt": prompt
    }).json()
    assert result["data"]["ei_reference"]["weeks_payable"] is None
    low, high = result["data"]["ei_reference"]["weeks_payable_range"]
    assert 0 < low <= high
    assert f"{low}–{high} weeks" in result["message"]
    assert "insurable hours" in result["message"]
    assert "historical proxy" in result["message"]
    assert "?" not in result["message"]
    assert "ei_range_estimate" in result["tool_trace"]
    assert "resilience_scenario" not in result["tool_trace"]
    assert result["data"]["income_after"] == pytest.approx(
        result["data"]["income"] * .55 if "55%" in prompt else
        min(result["data"]["income"] * 12 / 52 * .55, 729) * 52 / 12
    )


def test_reference_does_not_claim_eligibility_when_table_has_zero_weeks(client):
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "How does EI work with 420 insurable hours?"
    }).json()
    assert result["data"]["ei_reference"]["weeks_payable"] == 0
    assert "does not determine actual EI eligibility" in result["message"]
    assert "resilience_scenario" not in result["tool_trace"]


def test_missing_ei_reference_is_explicit(client, monkeypatch, tmp_path):
    monkeypatch.setattr(service, "data_dir", tmp_path / "parquet")
    result = client.post("/accounts/61163/assistant", json={
        "prompt": "How does EI work with 900 insurable hours?"
    }).json()
    assert "cannot use the local EI reference" in result["message"]
    assert "resilience_scenario" not in result["tool_trace"]


def test_reference_boundaries_and_accounts(tmp_path):
    data = tmp_path / "parquet"
    external = tmp_path / "external"
    data.mkdir()
    external.mkdir()
    pd.DataFrame([
        {"district_id": 1, "district_name": "A", "region": "R", "unemployment_rate_2023": 6.04},
        {"district_id": 2, "district_name": "B", "region": "R", "unemployment_rate_2023": 16.0},
    ]).to_parquet(data / "districts.parquet")
    pd.DataFrame([
        {"section": "rules", "item": "benefit_rate", "value": 0.55},
        {"section": "rules", "item": "max_weekly_benefit", "value": 729},
        {"section": "weeks_payable", "insurable_hours_min": 700, "insurable_hours_max": 99999, "unemp_rate_min_pct": 0, "unemp_rate_max_pct": 6, "value": 14},
        {"section": "weeks_payable", "insurable_hours_min": 700, "insurable_hours_max": 99999, "unemp_rate_min_pct": 15.1, "unemp_rate_max_pct": 16, "value": 30},
        {"section": "weeks_payable", "insurable_hours_min": 700, "insurable_hours_max": 99999, "unemp_rate_min_pct": 16, "unemp_rate_max_pct": 100, "value": 32},
    ]).to_csv(external / "ei_regular_benefits.csv", index=False)
    accounts = pd.DataFrame([{"account_id": 1, "district_id": 1}, {"account_id": 2, "district_id": 2}])
    reference = EIReference(data, accounts)
    assert reference.lookup(1, 700)["weeks_payable"] == 14
    assert reference.lookup(2, 700)["weeks_payable"] == 30
    assert reference.lookup(2)["weeks_payable_range"] == [30, 30]
    with pytest.raises(EIReferenceError):
        reference.lookup(1, 699)
