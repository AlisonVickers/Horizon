import pytest

from app.services.scenario_service import ScenarioService


PROFILE = {
    "income": 1000.0,
    "spending": 600.0,
    "household_bills": 200.0,
    "loan_payment": 100.0,
    "everyday_spending": 300.0,
}


def test_applies_multiple_supported_shocks():
    result = ScenarioService().apply(
        PROFILE,
        [
            {"name": "job_loss_ei", "value": 55},
            {"name": "rent_up_pct", "value": 15},
            {"name": "pay_cut_pct", "value": 20},
            {"name": "new_car_payment", "value": 250},
        ],
    )

    assert result == {
        "income": 440.0,
        "spending": 880.0,
        "one_off_costs": 0.0,
    }


def test_rejects_unknown_shock():
    with pytest.raises(ValueError, match="Unsupported scenario shock: unknown"):
        ScenarioService().apply(PROFILE, [{"name": "unknown", "value": 1}])
