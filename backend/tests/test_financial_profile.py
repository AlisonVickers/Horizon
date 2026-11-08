
from app.services.financial_profile import FinancialProfileService


def test_profile_61163():
    profile = FinancialProfileService().build(61163)

    assert profile["status"] == "available"
    assert profile["account_id"] == 61163
    assert profile["months_of_history"] > 0

    assert profile["typical_monthly_income"] >= 0
    assert profile["typical_monthly_spending"] >= 0
    assert profile["typical_fixed_costs"] >= 0
    assert profile["household_bills"] >= 0

    assert profile["method"] == "tangerine_judging_definitions"


def test_profile_without_active_loan():
    profile = FinancialProfileService().build(61163)

    assert profile["active_loan_payment"] >= 0


def test_profile_contains_buffer():
    profile = FinancialProfileService().build(61163)

    assert isinstance(profile["savings_buffer"], float)
