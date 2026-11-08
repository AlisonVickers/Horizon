from datetime import date

from api_adapter.service import AdapterAccountService


DATA_DIR = "data/parquet"


def test_requested_amount_ignores_year():
    prompt = "Can I afford $400 in December 2026?"

    assert AdapterAccountService._requested_amount(prompt) == 400
    assert AdapterAccountService._requested_amount("Can I afford $1,200 in June?") == 1200


def test_requested_date_parses_month_and_year():
    current = date(2026, 1, 15)

    assert AdapterAccountService._requested_date(
        "Can I afford $400 in December 2026?", current
    ) == date(2026, 12, 1)


def test_budget_request_persists_by_account(tmp_path):
    state_path = tmp_path / "astro_state.json"
    service = AdapterAccountService(DATA_DIR)
    service.state_path = state_path
    service._budget_requests = {20111: ["create a budget"]}
    service._budget_preferences = {20111: {"amount": None, "cadence": "month"}}
    service._save_state()

    restored = AdapterAccountService(DATA_DIR)
    restored.state_path = state_path
    restored._budget_requests, restored._budget_preferences = restored._load_state()

    assert restored._budget_requests == {20111: ["create a budget"]}


def test_explicit_budget_request_with_target_creates_budget(tmp_path):
    service = AdapterAccountService(DATA_DIR)
    service.state_path = tmp_path / "astro_state.json"
    response = service.assistant(
        61163,
        "Create a budget to help me save $500 per paycheck",
    )

    assert response["data"]["requested_savings_amount"] == 500
    assert response["data"]["requested_savings_cadence"] == "paycheck"
    assert response["data"]["budget_plan"][-1]["name"] == "Requested savings (paycheck)"
    assert "budget_planner" in response["tool_trace"]


def test_specific_question_returns_engine_calculation(tmp_path):
    service = AdapterAccountService(DATA_DIR)
    service.state_path = tmp_path / "astro_state.json"
    response = service.assistant(61163, "Can I afford a $400 trip in December 2026?")

    assert response["data"]["requested_amount"] == 400
    assert response["data"]["requested_date"] == "2026-12-01"
    assert "balance_projection" in response["tool_trace"]
    assert "runway_calculator" in response["tool_trace"]


def test_gemini_rewrite_rejects_unverified_numbers():
    profile = {"income": 1000.0}
    details = {"requested_amount": 400.0}

    assert AdapterAccountService._valid_gemini_text(
        '{"answer":"You bring in $1,000 and the purchase is $400.","conclusion":"informational"}',
        profile,
        "You bring in $1,000.",
        {**details, "conclusion": "informational"},
    )
    assert not AdapterAccountService._valid_gemini_text(
        '{"answer":"You bring in $1,000 and the purchase is $900.","conclusion":"informational"}',
        profile,
        "You bring in $1,000.",
        {**details, "conclusion": "informational"},
    )
