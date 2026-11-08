
import pytest

from app.domain.runway import RunwayCalculator


def test_normal_runway():
    result = RunwayCalculator.calculate(
        B=6000,
        one_off_costs=1000,
        spending_after_shock=2500,
        income_after_shock=1000,
    )

    assert result.buffer_left == 5000
    assert result.gap == 1500
    assert result.runway_months == pytest.approx(3.333333)
    assert result.is_capped is False


def test_depleted_buffer():
    result = RunwayCalculator.calculate(
        B=1000,
        one_off_costs=1500,
        spending_after_shock=2000,
        income_after_shock=1000,
    )

    assert result.runway_months == 0.0


def test_no_monthly_deficit():
    result = RunwayCalculator.calculate(
        B=5000,
        one_off_costs=0,
        spending_after_shock=2000,
        income_after_shock=3000,
    )

    assert result.runway_months == 120.0
    assert result.is_capped is True


def test_runway_cap():
    result = RunwayCalculator.calculate(
        B=20000,
        one_off_costs=0,
        spending_after_shock=1010,
        income_after_shock=1000,
    )

    assert result.runway_months == 120.0


def test_invalid_negative_input():
    with pytest.raises(ValueError):
        RunwayCalculator.calculate(
            B=-100,
            one_off_costs=0,
            spending_after_shock=1000,
            income_after_shock=500,
        )
