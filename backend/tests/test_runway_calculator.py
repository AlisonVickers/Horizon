
import pytest

from app.services.runway_calculator import RunwayCalculator


def test_standard_shortfall():
    result = RunwayCalculator.calculate(
        buffer=6000,
        monthly_spending=3000,
        monthly_income=2000,
    )
    assert result["runway_months"] == 6.0


def test_job_loss_with_55_percent_replacement():
    result = RunwayCalculator.calculate(
        buffer=6000,
        monthly_spending=3000,
        monthly_income=2000 * 0.55,
    )
    assert result["runway_months"] == 3.2


def test_emergency_repair_reduces_buffer():
    result = RunwayCalculator.calculate(
        buffer=6000,
        monthly_spending=3000,
        monthly_income=2000,
        one_off_costs=2000,
    )
    assert result["runway_months"] == 4.0


def test_no_shortfall():
    result = RunwayCalculator.calculate(
        buffer=6000,
        monthly_spending=2000,
        monthly_income=3000,
    )
    assert result["status"] == "no_shortfall"
    assert result["runway_months"] == 120.0


def test_depleted_buffer():
    result = RunwayCalculator.calculate(
        buffer=1000,
        monthly_spending=3000,
        monthly_income=1000,
        one_off_costs=1500,
    )
    assert result["runway_months"] == 0.0


def test_invalid_cost():
    with pytest.raises(ValueError):
        RunwayCalculator.calculate(
            buffer=6000,
            monthly_spending=3000,
            monthly_income=2000,
            one_off_costs=-100,
        )
